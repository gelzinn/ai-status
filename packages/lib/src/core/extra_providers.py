"""Provider-specific, read-only quota and balance integrations.

No provider response or credential is copied into normalized usage caches.
"""
import base64
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import urllib.parse

from .metered import amount_metric, auth_path, json_request, number, options
from .provider_http import QueryError, require_token

NAMES = {'deepseek': 'DeepSeek', 'deepinfra': 'DeepInfra', 'kimi': 'Kimi',
         'minimax': 'MiniMax', 'kilo': 'Kilo', 'lyceum': 'Lyceum', 'novita': 'Novita',
         'moonshot': 'Moonshot', 'grok': 'Grok (xAI)', 'supergrok': 'SuperGrok',
         'grok-bot': 'Grok Bot', 'cursor': 'Cursor', 'nous': 'Nous Research',
         'ollama': 'Ollama Cloud', 'orcarouter': 'OrcaRouter',
         'modelstudio': 'Alibaba Model Studio', 'devin': 'Devin'}


def _auth_path(default):
    """Resolve discovery paths only when no explicit credential file was given."""
    override = os.environ.get('AI_STATUS_AUTH_FILE')
    return auth_path(override or (default() if callable(default) else default))


def _read(default):
    if os.environ.get('AI_STATUS_ACCOUNT_ID') and not os.environ.get('AI_STATUS_AUTH_FILE'):
        return {}
    try:
        path = _auth_path(default)
        if path.stat().st_size > 1024*1024:
            return {}
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, RuntimeError):
        return {}


def _env_root(variable, default):
    value = os.environ.get(variable)
    return Path(value) if value else default()


def _config_root():
    if os.name == 'nt':
        return _env_root('APPDATA', lambda: Path.home() / 'AppData/Roaming')
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support'
    return _env_root('XDG_CONFIG_HOME', lambda: Path.home() / '.config')


def _key(name, variable=None, fallback=None):
    variable = variable or name.upper().replace('-', '_') + '_API_KEY'
    reference = options().get('api_key_env')
    return require_token((os.environ.get(reference) if isinstance(reference, str) else None) or os.environ.get(variable) or fallback,
                         f'Set {variable} or configure an account credential.')


def _bearer(token, extra=None):
    return {'Authorization': f'Bearer {token}', 'Accept': 'application/json', **(extra or {})}


def _access(variable):
    reference = options().get('access_token_env')
    return (os.environ.get(reference) if isinstance(reference, str) else None) or os.environ.get(variable)


def _num(value):
    result = number(value)
    if result is None:
        raise QueryError('Provider returned an invalid or missing usage amount.')
    return result


def _reset(value, milliseconds=False):
    if value is None:
        return None
    numeric = number(value)
    if numeric is not None:
        stamp = numeric / 1000 if milliseconds else numeric
    else:
        try:
            stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
        except (ValueError, OverflowError):
            raise QueryError('Provider returned an invalid reset timestamp.') from None
    if stamp <= 0:
        return None
    return max(0, int(stamp - time.time()))


def _quota(percent, kind, detail, reset=None, milliseconds=False, remaining=False, ratio=False):
    value = _num(percent) * (100 if ratio else 1)
    if value < 0 or (remaining or ratio) and value > 100:
        raise QueryError('Provider returned an invalid quota percentage.')
    return {'type': 'rolling' if kind == 'session' else kind, 'name': detail, 'percentage': 100-value if remaining else value,
            'detail': detail, 'reset_in_seconds': _reset(reset, milliseconds)}


def _money(value, detail, unit='USD', kind='balance', scale=1, limit=None, reset=None):
    metric = amount_metric(_num(value)/scale, unit, detail, kind,
                           limit, _reset(reset))
    metric['name'] = f'{detail} ({unit})'
    return metric


def _block_metric(block, kind, detail):
    limit, used = _num(block.get('limit')), number(block.get('used'))
    if used is None:
        used = limit - _num(block.get('remaining'))
    if limit <= 0 or used < 0:
        raise QueryError('Provider returned an invalid quota counter.')
    reset = next((block[key] for key in ('resetTime', 'resetAt', 'reset_at', 'reset_time') if block.get(key) is not None), None)
    return _quota(used/limit*100, kind, detail, reset)


def parse(name, raw):
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict) or 'error' in data or 'errors' in data:
            raise QueryError('Provider returned no compatible usage data.')
        metrics, plan = _parse(name, data)
        if not metrics:
            raise QueryError('Provider returned no compatible usage metrics.')
        return {'provider': NAMES[name], 'plan': str(plan or ''), 'metrics': metrics}
    except QueryError as exc:
        return {'provider': NAMES[name], 'metrics': [], '_error': str(exc)}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return {'provider': NAMES[name], 'metrics': [], '_error': 'Provider response format changed; no usage could be read.'}


def _parse(name, data):
    metrics, plan = [], data.get('plan') or ''
    if name == 'deepseek':
        if data.get('is_available') is False and not data.get('balance_infos'):
            raise QueryError('DeepSeek account balance is unavailable.')
        for row in data['balance_infos']:
            currency = row.get('currency') or 'USD'
            metrics.append(_money(row['total_balance'], 'Available balance', currency))
            for field, label in [('granted_balance', 'Granted credits'), ('topped_up_balance', 'Purchased credits')]:
                if field in row:
                    metrics.append(_money(row[field], label, currency))
    elif name == 'deepinfra':
        checklist, usage = data['checklist'], data['usage']
        metrics.append(_money(-_num(checklist['stripe_balance'])-_num(checklist['recent']), 'Available prepaid balance'))
        month = datetime.now(timezone.utc).strftime('%Y.%m')
        rows = [row for row in usage['months'] if row.get('period') == month]
        if not rows:
            return metrics, plan
        limit = number(checklist.get('limit'))
        if limit is not None and limit <= 0:
            limit = None
        metrics.append(_money(rows[0]['total_cost'], 'Current-month spend', kind='monthly', scale=100, limit=limit))
    elif name == 'kimi':
        plan = ((data.get('user') or {}).get('membership') or {}).get('level') or ''
        if isinstance(data.get('usage'), dict):
            metrics.append(_block_metric(data['usage'], 'weekly', 'Weekly subscription quota'))
        elif isinstance(data.get('usages'), dict) and isinstance(data['usages'].get('limit_month_total'), dict):
            row = data['usages']['limit_month_total']
            metrics.append(_quota(row['used_ratio'], 'monthly', 'Combined monthly quota',
                                  row.get('reset_time') or row.get('resetTime') or row.get('resetAt') or row.get('reset_at'), ratio=True))
        for row in data.get('limits') or []:
            window = row.get('window') or {}
            duration = _num(window.get('duration'))
            unit = str(window.get('timeUnit') or window.get('time_unit') or '').lower().removeprefix('time_unit_')
            seconds = duration * {'minute': 60, 'minutes': 60, 'hour': 3600, 'hours': 3600, 'second': 1, 'seconds': 1}.get(unit, 0)
            if seconds == 18000:
                metrics.append(_block_metric(row['detail'], 'session', '5-hour quota'))
        if data.get('limits') and not any(metric['type'] == 'rolling' for metric in metrics):
            raise QueryError('Kimi returned an unrecognized rolling quota window.')
    elif name == 'minimax':
        if (data.get('base_resp') or {}).get('status_code') != 0:
            raise QueryError('MiniMax rejected the request; verify your Token Plan key and region.')
        for row in data['model_remains']:
            label = str(row.get('model_name') or 'Token Plan')
            if 'current_interval_remaining_percent' in row:
                span = _num(row.get('end_time')) - _num(row.get('start_time'))
                kind = 'daily' if span > 18000000 else 'session'
                metrics.append(_quota(row['current_interval_remaining_percent'], kind, f'{label} rolling quota', row.get('end_time'), True, True))
            if 'current_weekly_remaining_percent' in row:
                metrics.append(_quota(row['current_weekly_remaining_percent'], 'weekly', f'{label} weekly quota', row.get('weekly_end_time'), True, True))
    elif name == 'kilo':
        metrics.append(_money(data['balance'], 'Available credit balance'))
    elif name == 'lyceum':
        metrics.append(_money(data['available_credits'], 'Available balance'))
        spent = _money(data['used_credits'], 'Credits used (reported period)', kind='spend')
        spent.update(title='Credits used', detail='Reported period')
        metrics.append(spent)
    elif name == 'novita':
        row = data.get('data') if isinstance(data.get('data'), dict) else data
        metrics.append(_money(row['availableBalance'], 'Available credit balance', scale=10000))
        for field, label in [('cashBalance', 'Cash balance'), ('outstandingInvoices', 'Outstanding invoices')]:
            if field in row:
                metrics.append(_money(row[field], label, scale=10000))
    elif name == 'moonshot':
        if data.get('code') != 0 or data.get('status') is not True:
            raise QueryError('Moonshot rejected the balance request; verify your key and region.')
        currency = data.get('_currency') or 'USD'
        for field, label in [('available_balance', 'Available balance'), ('cash_balance', 'Cash balance'), ('voucher_balance', 'Voucher balance')]:
            metrics.append(_money(data['data'][field], label, currency))
    elif name == 'grok':
        metrics.append(_money(-_num(data['total']['val']), 'Prepaid API credit balance', scale=100))
    elif name == 'orcarouter':
        used = _num(data['usage']['total_usage'])/100
        sub = data['subscription']
        limit = next((number(sub.get(key)) for key in ('hard_limit_usd', 'soft_limit_usd', 'system_hard_limit_usd') if number(sub.get(key)) is not None), None)
        if limit is not None and (limit <= 0 or limit >= 100000000):
            limit = None
        metrics.append(_money(used, 'Cumulative spend', kind='spend', limit=limit))
        if limit is not None:
            metrics.append(_money(limit-used, 'Remaining credit balance'))
    elif name == 'ollama':
        included = data.get('included') or {}
        if 'balance_usd' in included:
            balance, allowance = _num(included['balance_usd']), _num(included['allowance_usd'])
            end = (included.get('period') or {}).get('until')
            metrics.append(_money(balance, 'Monthly included credits remaining'))
            metrics.append(_money(max(0, allowance-balance), 'Monthly included credits used', kind='monthly', limit=allowance, reset=end))
        else:
            for key in ('session', 'weekly'):
                row = included.get(key)
                if isinstance(row, dict):
                    metrics.append(_quota(row['remaining_percent'], key, f'{key.title()} quota', row.get('resets_at'), remaining=True))
            for key in ('session', 'weekly', 'monthly'):
                row = (data.get('limits') or {}).get(key)
                if isinstance(row, dict) and 'usage' in row:
                    metrics.append(_quota(row['usage'], key, f'{key.title()} quota', row.get('resets_at'), ratio=True))
        if isinstance(data.get('purchased'), dict):
            metrics.append(_money(data['purchased']['balance_usd'], 'Purchased credits remaining'))
    elif name == 'cursor':
        plan = data.get('membershipType') or ''
        end = data.get('billingCycleEnd')
        if data.get('isUnlimited') is True:
            metrics.append({'type': 'monthly', 'name': 'Included usage', 'percentage': None, 'value': 'Unlimited', 'detail': 'Unlimited included usage', 'reset_in_seconds': _reset(end)})
        else:
            individual = data.get('individualUsage') or {}
            pools = individual.get('plan') or {}
            auto, api = pools.get('autoPercentUsed'), pools.get('apiPercentUsed')
            if auto is None or api is None:
                values = []
                for field in ('autoModelSelectedDisplayMessage', 'namedModelSelectedDisplayMessage'):
                    match = re.search(r'(\d+(?:\.\d+)?)\s*%', str(data.get(field) or ''))
                    values.append(float(match.group(1)) if match else None)
                auto, api = values
            metrics.extend([_quota(auto, 'monthly', 'Cursor Models included quota', end), _quota(api, 'monthly', 'Other Models included quota', end)])
            demand = individual.get('onDemand') or (data.get('teamUsage') or {}).get('onDemand') or {}
            if demand.get('used') is not None:
                cap = number(demand.get('limit'))
                metrics.append(_money(demand['used'], 'On-demand spend this billing cycle', kind='monthly', scale=100, limit=cap/100 if cap else None, reset=end))
    elif name == 'supergrok':
        plan = data.get('subscription_tier_display') or data.get('subscriptionTierDisplay') or data.get('subscription_tier') or data.get('subscriptionTier') or ''
        cfg = data['config']
        period = cfg.get('currentPeriod') or {}
        kind = 'monthly' if str(period.get('type') or '').lower().endswith('monthly') or not period and 'monthlyLimit' in cfg else 'weekly'
        end = period.get('end') or cfg.get('billingPeriodEnd')
        value = cfg.get('creditUsagePercent')
        if value is None and period:
            value = 0  # Proto JSON omits a scalar whose value is zero.
        if value is None:
            cap, used = (cfg.get('monthlyLimit') or {}).get('val'), (cfg.get('used') or {}).get('val')
            metrics.append(_money(used, 'Included credits used', kind='monthly', scale=100, limit=_num(cap)/100, reset=end))
        else:
            metrics.append(_quota(value, kind, 'Included subscription credits used', end))
        for row in cfg.get('productUsage') or []:
            if row.get('usagePercent') is not None:
                metrics.append(_quota(row['usagePercent'], kind, str(row.get('product') or 'Product')+' included usage', end))
        if isinstance(cfg.get('prepaidBalance'), dict):
            metrics.append(_money(cfg['prepaidBalance'].get('val', 0), 'Prepaid API balance', scale=100))
    elif name == 'grok-bot':
        plan = data.get('grokPlanLabel') or data.get('cursorPlanName') or ''
        if data.get('hasNonZeroIncludedLimit') is False:
            metrics.append({'type': 'weekly', 'name': 'Included usage', 'percentage': None, 'value': 'No included allowance', 'detail': 'No included usage allowance'})
        else:
            metrics.append(_quota(data['usagePercent'], 'weekly', 'Weekly included usage', data.get('nextResetTimestampUtc')))
    elif name == 'nous':
        row = dict(data)
        row.update(data.get('paid_service_access') or {})
        row.update(data.get('subscription') or {})
        plan = row.get('plan') or row.get('plan_name') or row.get('planName') or ''
        allowance = number(row.get('monthly_credits', row.get('monthlyCredits')))
        remaining = number(next((row[key] for key in ('credits_remaining', 'creditsRemaining', 'subscription_credits_remaining', 'subscriptionCreditsRemaining') if key in row), None))
        end = next((row[key] for key in ('period_end', 'current_period_end', 'currentPeriodEnd', 'renewal_at', 'renewalAt') if key in row), None)
        if remaining is not None:
            metrics.append(_money(remaining, 'Subscription credits remaining', 'credits'))
            if allowance is not None and allowance > 0:
                metrics.append(_money(max(0, allowance-remaining), 'Monthly subscription credits used', 'credits', 'monthly', limit=allowance, reset=end))
        for keys, label in [(('purchased_credits_remaining', 'purchasedCreditsRemaining', 'top_up_credits_remaining', 'topUpCreditsRemaining'), 'Purchased credits remaining'), (('total_usable_credits', 'totalUsableCredits'), 'Total usable credits')]:
            value = next((row[key] for key in keys if key in row), None)
            if value is not None:
                metrics.append(_money(value, label, 'credits'))
    elif name == 'modelstudio':
        if data.get('success') is False:
            raise QueryError('Model Studio session expired; run bl auth login --console.')
        row = data.get('DataV2') or data.get('data') or data
        for _ in range(2):
            if isinstance(row.get('data'), dict):
                row = row['data']
        for field, reset_field, kind in [('per5HourPercentage', 'per5HourResetTime', 'session'), ('per1WeekPercentage', 'per1WeekResetTime', 'weekly')]:
            if row.get(field) is not None:
                metrics.append(_quota(row[field], kind, 'Token Plan '+kind+' quota', row.get(reset_field), milliseconds=True, ratio=True))
    elif name == 'devin':
        row = data['userStatus']['planStatus']
        for prefix, kind in [('daily', 'daily'), ('weekly', 'weekly')]:
            value, end = row.get(prefix+'QuotaRemainingPercent'), row.get(prefix+'QuotaResetAtUnix')
            if value is not None or end is not None:
                metrics.append(_quota(value if value is not None else 0, kind, kind.title()+' quota', end, remaining=True))
        if row.get('overageBalanceMicros') is not None:
            metrics.append(_money(row['overageBalanceMicros'], 'Overage balance (vendor-reported USD)', scale=1000000))
    return metrics, plan


def collect(name):
    cfg = options()
    if name in ('deepseek', 'deepinfra', 'minimax', 'kilo', 'lyceum', 'novita', 'moonshot', 'ollama', 'orcarouter'):
        token = _key(name)
        headers = _bearer(token)
        if name == 'deepseek':
            return json_request('https://api.deepseek.com/user/balance', headers)
        if name == 'deepinfra':
            return {'checklist': json_request('https://api.deepinfra.com/payment/checklist', headers),
                    'usage': json_request('https://api.deepinfra.com/payment/usage', headers, {'from': 'current'})}
        if name == 'minimax':
            host = 'api.minimaxi.com' if cfg.get('region') == 'cn' else 'api.minimax.io'
            return json_request(f'https://{host}/v1/token_plan/remains', headers)
        if name == 'kilo':
            if cfg.get('organization_id'):
                headers['x-kilocode-organizationid'] = str(cfg['organization_id'])
            return json_request('https://api.kilo.ai/api/profile/balance', headers)
        if name == 'lyceum':
            return json_request('https://api.lyceum.technology/api/v2/external/billing/credits', headers)
        if name == 'novita':
            return json_request('https://api.novita.ai/openapi/v1/billing/balance/detail', headers)
        if name == 'moonshot':
            cn = cfg.get('region') == 'cn'
            value = json_request('https://api.moonshot.'+('cn' if cn else 'ai')+'/v1/users/me/balance', headers)
            value['_currency'] = 'CNY' if cn else 'USD'
            return value
        if name == 'ollama':
            return json_request('https://ollama.com/api/balance', headers)
        return {'usage': json_request('https://api.orcarouter.ai/v1/dashboard/billing/usage', headers),
                'subscription': json_request('https://api.orcarouter.ai/v1/dashboard/billing/subscription', headers)}
    if name == 'kimi':
        credentials = _read(lambda: Path.home() / '.kimi-code/credentials/kimi-code.json')
        token = _key(name, fallback=credentials.get('access_token'))
        region = cfg.get('region')
        if not region and not (os.environ.get('AI_STATUS_AUTH_FILE') or os.environ.get('AI_STATUS_ACCOUNT_ID')):
            try:
                region = (Path.home() / '.kimi-code/region').read_text().strip()
            except (OSError, RuntimeError):
                region = 'cn'
        host = 'api.kimi.ai' if region == 'global' else 'api.kimi.com'
        return json_request(f'https://{host}/coding/v1/usages', _bearer(token))
    if name == 'grok':
        token = _key(name, 'XAI_MANAGEMENT_KEY')
        headers = _bearer(token)
        team = cfg.get('team_id')
        if not team:
            value = json_request('https://management-api.x.ai/auth/management-keys/validation', headers)
            team = value.get('teamId') or (value.get('scopeId') if value.get('scope') in (None, 'SCOPE_TEAM') else None)
        if not team:
            raise QueryError('Set team_id for an organization-scoped xAI Management key.')
        return json_request('https://management-api.x.ai/v1/billing/teams/'+urllib.parse.quote(str(team), safe='')+'/prepaid/balance', headers)
    if name == 'supergrok':
        credentials = _read(lambda: _env_root('GROK_HOME', lambda: Path.home() / '.grok') / 'auth.json')
        fallback = next((row.get('key') for row in credentials.values() if isinstance(row, dict) and row.get('key')), None)
        token = _key(name, 'SUPERGROK_ACCESS_TOKEN', fallback)
        return json_request('https://cli-chat-proxy.grok.com/v1/billing', _bearer(token, {'X-XAI-Token-Auth': 'xai-grok-cli'}), {'format': 'credits'})
    if name == 'cursor':
        token = _access('CURSOR_ACCESS_TOKEN')
        override = os.environ.get('AI_STATUS_AUTH_FILE')
        if not token and (override or not os.environ.get('AI_STATUS_ACCOUNT_ID')):
            database = _auth_path(lambda: _config_root() / 'Cursor/User/globalStorage/state.vscdb')
            if database.suffix == '.json':
                token = _read(database).get('accessToken')
            elif database.is_file():
                try:
                    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)) as conn:
                        row = conn.execute('SELECT value FROM ItemTable WHERE key=?', ('cursorAuth/accessToken',)).fetchone()
                        token = row[0] if row else None
                except sqlite3.Error:
                    pass
        if not token and not override and not os.environ.get('AI_STATUS_ACCOUNT_ID'):
            default = Path.home() / '.cursor/auth.json' if sys.platform == 'darwin' else _config_root() / ('Cursor/auth.json' if os.name == 'nt' else 'cursor/auth.json')
            token = _read(default).get('accessToken')
            if not token and sys.platform == 'darwin':
                from .oscrypt import _secret
                secret = _secret(['/usr/bin/security', 'find-generic-password', '-s', 'cursor-access-token', '-a', 'cursor-user', '-w'])
                token = secret.decode('utf-8') if secret else None
        require_token(token, 'Sign in to Cursor or cursor-agent, or set CURSOR_ACCESS_TOKEN.')
        try:
            payload = token.split('.')[1]
            sub = json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))['sub']
            user = str(sub).split('|')[-1]
        except (ValueError, KeyError, IndexError, TypeError):
            raise QueryError('Cursor token is invalid; sign in again.') from None
        cookie = urllib.parse.quote(user+'%3A%3A'+token, safe='%._-')
        return json_request('https://cursor.com/api/usage-summary', {'Cookie': 'WorkosCursorSessionToken='+cookie, 'Origin': 'https://cursor.com', 'Referer': 'https://cursor.com/dashboard', 'User-Agent': 'Mozilla/5.0 ai-status'})
    if name == 'grok-bot':
        token = _access('GROK_BOT_ACCESS_TOKEN')
        if not token:
            if os.environ.get('AI_STATUS_ACCOUNT_ID') and not os.environ.get('AI_STATUS_AUTH_FILE'):
                raise QueryError('Configure an account auth_file or GROK_BOT_ACCESS_TOKEN environment reference.')
            try:
                from .oscrypt import grok_bot_tokens
                token, _ = grok_bot_tokens(_auth_path(lambda: _config_root() / 'Grok Bot/sand-secrets.json'))
            except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError):
                raise QueryError('Sign in to the Grok Bot desktop app or set GROK_BOT_ACCESS_TOKEN.') from None
        return json_request('https://api2.cursor.sh/aiserver.v1.DashboardService/GetSandUsageStatus', _bearer(token, {'Connect-Protocol-Version': '1', 'x-cursor-client-type': 'sand', 'x-cursor-client-version': '0.1.0', 'x-sand-box-namespace': 'prod', 'x-ghost-mode': 'true'}), method='POST', data={})
    if name == 'nous':
        token = _access('NOUS_ACCESS_TOKEN')
        if not token and os.environ.get('AI_STATUS_AUTH_FILE'):
            credentials = _read(os.environ['AI_STATUS_AUTH_FILE'])
            token = (credentials.get('nous') or credentials).get('access_token')
        require_token(token, 'Configure NOUS_ACCESS_TOKEN or an account auth_file with Nous OAuth credentials.')
        return json_request('https://portal.nousresearch.com/api/oauth/account', _bearer(token))
    if name == 'modelstudio':
        credentials = _read(lambda: Path.home() / '.bailian/config.json')
        token = _access('MODELSTUDIO_ACCESS_TOKEN') or credentials.get('access_token') or credentials.get('accessToken')
        require_token(token, 'Run bl auth login --console or configure an account console token.')
        region = cfg.get('region') or credentials.get('console_region') or 'cn-beijing'
        site = cfg.get('site') or credentials.get('console_site') or 'domestic'
        intl, singapore = site == 'international', region == 'ap-southeast-1'
        host = ('bailian-singapore-cs.alibabacloud.com' if intl else 'modelstudio-cs.console.aliyun.com') if singapore else ('bailian-cs.console.alibabacloud.com' if intl else 'bailian-cs.console.aliyun.com')
        action = 'IntlBroadScopeAspnGateway' if singapore else 'BroadScopeAspnGateway'
        api = 'zeldaHttp.apikeyMgr./tokenplan/personal/api/v2/usage'
        params = {'Api': api, 'V': '1.0', 'Data': {'cornerstoneParam': {'protocol': 'V2', 'console': 'ONE_CONSOLE', 'productCode': 'p_efm', 'switchUserType': 3, 'consoleSite': 'BAILIAN_ALIYUN'}}}
        body = urllib.parse.urlencode({'region': region, 'params': json.dumps(params, separators=(',', ':'))})
        return json_request(f'https://{host}/cli/api.json', _bearer(token, {'Content-Type': 'application/x-www-form-urlencoded'}), {'action': action, 'product': 'sfm_bailian', 'api': api}, 'POST', body)
    if name == 'devin':
        reference = cfg.get('api_key_env')
        token = (os.environ.get(reference) if isinstance(reference, str) else None) or os.environ.get('DEVIN_API_KEY')
        if not token and (os.environ.get('AI_STATUS_AUTH_FILE') or not os.environ.get('AI_STATUS_ACCOUNT_ID')):
            try:
                raw = _auth_path(lambda: (_config_root() if os.name == 'nt' else _env_root('XDG_DATA_HOME', lambda: Path.home() / '.local/share')) / 'devin/credentials.toml').read_text(encoding='utf-8')
                # Read only this top-level TOML field, never other credentials.
                for line in raw.splitlines():
                    if line.lstrip().startswith('['):
                        break
                    match = re.fullmatch(r'\s*windsurf_api_key\s*=\s*("(?:[^"\\]|\\.)*"|\'[^\']*\')\s*(?:#.*)?', line)
                    if match:
                        quoted = match.group(1)
                        token = json.loads(quoted) if quoted.startswith('"') else quoted[1:-1]
                        break
            except (OSError, ValueError, RuntimeError):
                pass
        require_token(token, 'Sign in with the official Devin CLI or configure DEVIN_API_KEY.')
        version = '0.0.0'
        try:
            cache = _env_root('LOCALAPPDATA' if os.name == 'nt' else 'XDG_CACHE_HOME', lambda: Path.home() / '.cache')
            record = json.loads((cache / 'devin/cli/cached_version.json').read_text())
            candidate = record.get('latest') if isinstance(record, dict) else record
            if re.fullmatch(r'\d+\.\d+\.\d+', str(candidate)):
                version = candidate
        except (OSError, ValueError, RuntimeError):
            pass
        metadata = {'apiKey': token, 'ideName': 'devin', 'ideVersion': version, 'extensionVersion': version, 'locale': 'en'}
        return json_request('https://server.codeium.com/exa.seat_management_pb.SeatManagementService/GetUserStatus', {'Accept': 'application/json', 'Connect-Protocol-Version': '1'}, method='POST', data={'metadata': metadata})
    raise QueryError('Unknown provider.')
