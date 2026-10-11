import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core import extra_providers as p
from core import oscrypt
from core.provider_http import QueryError

MONTH = datetime.now(timezone.utc).strftime('%Y.%m')
FUTURE = '2099-01-01T00:00:00Z'
FIXTURES = {
    'deepseek': {'is_available': True, 'balance_infos': [{'currency': 'USD', 'total_balance': '20.5', 'granted_balance': '2', 'topped_up_balance': '18.5'}]},
    'deepinfra': {'checklist': {'stripe_balance': -10, 'recent': 2, 'limit': 50}, 'usage': {'months': [{'period': MONTH, 'total_cost': 250}]}},
    'kimi': {'usage': {'limit': '100', 'used': '30'}, 'limits': [{'window': {'duration': 300, 'timeUnit': 'TIME_UNIT_MINUTE'}, 'detail': {'limit': 10, 'used': 2}}]},
    'minimax': {'base_resp': {'status_code': 0}, 'model_remains': [{'model_name': 'general', 'start_time': 100000, 'end_time': 18100000, 'weekly_end_time': 604900000, 'current_interval_remaining_percent': 75, 'current_weekly_remaining_percent': 60}]},
    'kilo': {'balance': 12.5},
    'lyceum': {'available_credits': 3.5, 'used_credits': 2},
    'novita': {'availableBalance': '125000', 'cashBalance': '100000'},
    'moonshot': {'code': 0, 'status': True, 'data': {'available_balance': 25, 'cash_balance': 20, 'voucher_balance': 5}},
    'grok': {'total': {'val': '-1000'}},
    'supergrok': {'config': {'creditUsagePercent': 30, 'currentPeriod': {'type': 'USAGE_PERIOD_TYPE_MONTHLY', 'end': FUTURE}, 'productUsage': [{'product': 'GrokBuild', 'usagePercent': 20}], 'prepaidBalance': {'val': '500'}}, 'subscription_tier': 'SuperGrok'},
    'grok-bot': {'usagePercent': 15.25, 'hasNonZeroIncludedLimit': True, 'nextResetTimestampUtc': FUTURE},
    'cursor': {'billingCycleEnd': FUTURE, 'membershipType': 'pro', 'individualUsage': {'plan': {'autoPercentUsed': 20, 'apiPercentUsed': 40}}},
    'nous': {'subscription': {'monthly_credits': 100, 'credits_remaining': 70, 'purchased_credits_remaining': 10, 'total_usable_credits': 80}},
    'ollama': {'included': {'balance_usd': 15, 'allowance_usd': 20, 'period': {'until': FUTURE}}, 'purchased': {'balance_usd': 8}},
    'orcarouter': {'usage': {'total_usage': 250}, 'subscription': {'hard_limit_usd': 10}},
    'modelstudio': {'DataV2': {'data': {'data': {'per5HourPercentage': 0.2, 'per1WeekPercentage': 0.4}}}},
    'devin': {'userStatus': {'planStatus': {'dailyQuotaRemainingPercent': 80, 'weeklyQuotaRemainingPercent': '60', 'overageBalanceMicros': '1000000'}}},
}


class ProviderParsers(unittest.TestCase):
    def test_every_fixture_produces_real_metrics(self):
        self.assertEqual(set(FIXTURES), set(p.NAMES))
        for name, fixture in FIXTURES.items():
            with self.subTest(name=name):
                parsed = p.parse(name, json.dumps(fixture))
                self.assertNotIn('_error', parsed)
                self.assertGreater(len(parsed['metrics']), 0)
                self.assertNotIn('synthetic-credential', json.dumps(parsed))

    def test_empty_error_and_invalid_money_never_become_zero(self):
        for name in FIXTURES:
            for raw in ['{}', '{"error":"secret-value"}', 'null', '[]', 'not json']:
                with self.subTest(name=name, raw=raw):
                    result = p.parse(name, raw)
                    self.assertTrue(result['_error'])
                    self.assertEqual(result['metrics'], [])
                    self.assertNotIn('secret-value', result['_error'])
        for value in [True, None, 'NaN', 'inf']:
            self.assertEqual(p.parse('kilo', {'balance': value})['metrics'], [])

    def test_currency_units_and_balances(self):
        expected = {'deepseek': 20.5, 'deepinfra': 8, 'novita': 12.5, 'grok': 10, 'kilo': 12.5}
        for name, amount in expected.items():
            metric = p.parse(name, FIXTURES[name])['metrics'][0]
            self.assertEqual(metric['amount'], amount)
            self.assertIsNone(metric['percentage'])
        self.assertEqual(p.parse('deepinfra', FIXTURES['deepinfra'])['metrics'][1]['amount'], 2.5)
        moonshot = dict(FIXTURES['moonshot'], _currency='CNY')
        self.assertEqual(p.parse('moonshot', moonshot)['metrics'][0]['unit'], 'CNY')
        self.assertEqual(p.parse('orcarouter', FIXTURES['orcarouter'])['metrics'][0]['percentage'], 25)

    def test_remaining_is_inverted_and_ratios_are_scaled(self):
        self.assertEqual(p.parse('minimax', FIXTURES['minimax'])['metrics'][0]['percentage'], 25)
        self.assertEqual(p.parse('devin', FIXTURES['devin'])['metrics'][0]['percentage'], 20)
        self.assertEqual(p.parse('modelstudio', FIXTURES['modelstudio'])['metrics'][0]['percentage'], 20)
        self.assertEqual(p.parse('nous', FIXTURES['nous'])['metrics'][1]['percentage'], 30)
        self.assertEqual(p.parse('ollama', FIXTURES['ollama'])['metrics'][1]['percentage'], 25)
        self.assertEqual(p.parse('kimi', FIXTURES['kimi'])['metrics'][1]['percentage'], 20)

    def test_proto_zero_is_exhausted_devin_but_unused_supergrok(self):
        parsed = p.parse('devin', {'userStatus': {'planStatus': {'dailyQuotaResetAtUnix': 4070908800}}})
        self.assertEqual(parsed['metrics'][0]['percentage'], 100)
        parsed = p.parse('supergrok', {'config': {'currentPeriod': {'type': 'USAGE_PERIOD_TYPE_WEEKLY'}, 'monthlyLimit': {'val': 1000}, 'used': {'val': 900}}})
        self.assertEqual(parsed['metrics'][0]['percentage'], 0)
        self.assertEqual(parsed['metrics'][0]['type'], 'weekly')

    def test_alternate_kimi_ollama_cursor_and_unlimited_shapes(self):
        parsed = p.parse('kimi', {'usages': {'limit_month_total': {'used_ratio': 0.7}, 'limit_5h': {'used_ratio': 1}}})
        self.assertEqual(len(parsed['metrics']), 1)
        self.assertEqual(parsed['metrics'][0]['percentage'], 70)
        parsed = p.parse('ollama', {'included': {'session': {'remaining_percent': 60}, 'weekly': {'remaining_percent': 80}}})
        self.assertEqual([m['percentage'] for m in parsed['metrics']], [40, 20])
        parsed = p.parse('cursor', {'billingCycleEnd': FUTURE, 'autoModelSelectedDisplayMessage': 'You used 30% of quota', 'namedModelSelectedDisplayMessage': 'You used 40% of quota'})
        self.assertEqual([m['percentage'] for m in parsed['metrics']], [30, 40])
        parsed = p.parse('cursor', {'billingCycleEnd': FUTURE, 'isUnlimited': True})
        self.assertIsNone(parsed['metrics'][0]['percentage'])
        parsed = p.parse('orcarouter', {'usage': {'total_usage': 275}, 'subscription': {'hard_limit_usd': 100000000}})
        self.assertEqual(len(parsed['metrics']), 1)
        self.assertIsNone(parsed['metrics'][0]['percentage'])

    def test_in_band_failures(self):
        minimax = dict(FIXTURES['minimax'], base_resp={'status_code': 2049, 'status_msg': 'secret'})
        self.assertTrue(p.parse('minimax', minimax)['_error'])
        moonshot = dict(FIXTURES['moonshot'], code=401)
        self.assertTrue(p.parse('moonshot', moonshot)['_error'])
        self.assertTrue(p.parse('modelstudio', {'success': False, 'errorCode': 'secret'})['_error'])

    def test_names_keep_multiple_metrics_distinct_and_partial_balance(self):
        for name, fixture in FIXTURES.items():
            metrics = p.parse(name, fixture)['metrics']
            self.assertEqual(len(metrics), len({m['type']+m['name'] for m in metrics}))
        parsed = p.parse('deepinfra', {'checklist': {'stripe_balance': -10, 'recent': 2}, 'usage': {'months': []}})
        self.assertEqual(parsed['metrics'][0]['amount'], 8)
        self.assertEqual(len(parsed['metrics']), 1)


class ProviderCollectors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'AI_STATUS_ACCOUNT_OPTIONS': '{}',
            'HOME': str(self.root), 'USERPROFILE': str(self.root),
            'APPDATA': str(self.root / 'AppData/Roaming'),
            'LOCALAPPDATA': str(self.root / 'AppData/Local'),
            'XDG_CONFIG_HOME': str(self.root / '.config'),
            'XDG_DATA_HOME': str(self.root / '.local/share'),
            'XDG_CACHE_HOME': str(self.root / '.cache'),
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_api_key_collectors_use_fixed_endpoints_and_headers(self):
        for name in ('deepseek', 'deepinfra', 'minimax', 'kilo', 'lyceum', 'novita', 'moonshot', 'ollama', 'orcarouter'):
            with self.subTest(name=name), patch.dict(os.environ, {name.upper()+'_API_KEY': 'synthetic-credential'}), patch.object(p, 'json_request', return_value={}) as api:
                p.collect(name)
                self.assertTrue(api.called)
                for call in api.call_args_list:
                    self.assertTrue(call.args[0].startswith('https://'))
                    self.assertEqual(call.args[1]['Authorization'], 'Bearer synthetic-credential')

    def test_missing_credentials_fail_before_network(self):
        for name in ('deepseek', 'deepinfra', 'minimax', 'kilo', 'novita', 'moonshot', 'grok', 'ollama', 'orcarouter'):
            with self.subTest(name=name), patch.object(p, 'json_request') as api:
                with self.assertRaises(QueryError):
                    p.collect(name)
                api.assert_not_called()

    def test_grok_resolves_team_and_rejects_org_scope(self):
        with patch.dict(os.environ, {'XAI_MANAGEMENT_KEY': 'synthetic-credential'}), patch.object(p, 'json_request', side_effect=[{'scope': 'SCOPE_TEAM', 'scopeId': 'team 1'}, FIXTURES['grok']]) as api:
            self.assertEqual(p.collect('grok'), FIXTURES['grok'])
            self.assertIn('/teams/team%201/prepaid/balance', api.call_args.args[0])
        with patch.dict(os.environ, {'XAI_MANAGEMENT_KEY': 'synthetic-credential'}), patch.object(p, 'json_request', return_value={'scope': 'SCOPE_ORGANIZATION', 'scopeId': 'org'}) as api:
            with self.assertRaises(QueryError):
                p.collect('grok')
            self.assertEqual(api.call_count, 1)

    def test_read_only_local_json_auth_collectors(self):
        for name, credentials in [('kimi', {'access_token': 'synthetic-credential'}), ('supergrok', {'issuer': {'key': 'synthetic-credential'}}), ('nous', {'nous': {'access_token': 'synthetic-credential'}}), ('modelstudio', {'access_token': 'synthetic-credential', 'console_region': 'ap-southeast-1', 'console_site': 'international'})]:
            with self.subTest(name=name):
                path = self.root / (name+'.json')
                content = json.dumps(credentials)
                path.write_text(content)
                with patch.dict(os.environ, {'AI_STATUS_AUTH_FILE': str(path)}), patch.object(Path, 'home', side_effect=AssertionError('Explicit auth must not discover a home')), patch.object(p, 'json_request', return_value={}) as api:
                    p.collect(name)
                    self.assertEqual(api.call_args.args[1]['Authorization'], 'Bearer synthetic-credential')
                    if name == 'modelstudio':
                        self.assertIn('bailian-singapore-cs.alibabacloud.com', api.call_args.args[0])
                        self.assertEqual(api.call_args.args[3], 'POST')
                self.assertEqual(path.read_text(), content)

    def test_cursor_read_only_sqlite_and_cookie(self):
        token = 'header.'+base64.urlsafe_b64encode(b'{"sub":"auth0|user1"}').decode().rstrip('=')+'.signature'
        path = self.root / 'state.vscdb'
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE ItemTable (key TEXT, value TEXT)')
            db.execute('INSERT INTO ItemTable VALUES (?, ?)', ('cursorAuth/accessToken', token))
            db.commit()
        before = path.read_bytes()
        with patch.dict(os.environ, {'AI_STATUS_AUTH_FILE': str(path)}), patch.object(Path, 'home', side_effect=AssertionError('Explicit auth must not discover a home')), patch.object(p, 'json_request', return_value=FIXTURES['cursor']) as api:
            self.assertEqual(p.collect('cursor'), FIXTURES['cursor'])
            self.assertEqual(api.call_args.args[1]['Cookie'], 'WorkosCursorSessionToken=user1%3A%3A'+token)
        self.assertEqual(path.read_bytes(), before)

    def test_grok_bot_and_devin_post_real_rpc_bodies(self):
        with patch.dict(os.environ, {'GROK_BOT_ACCESS_TOKEN': 'synthetic-credential'}), patch.object(p, 'json_request', return_value={}) as api:
            p.collect('grok-bot')
            self.assertIn('GetSandUsageStatus', api.call_args.args[0])
            self.assertEqual(api.call_args.kwargs, {'method': 'POST', 'data': {}})
        path = self.root / 'credentials.toml'
        content = 'windsurf_api_key = "synthetic-credential"\napi_server_url = "https://attacker.invalid"\n'
        path.write_text(content)
        with patch.dict(os.environ, {'AI_STATUS_AUTH_FILE': str(path)}), patch.object(Path, 'home', side_effect=RuntimeError('Could not determine home directory.')), patch.dict(os.environ, {'LOCALAPPDATA': '', 'XDG_CACHE_HOME': ''}), patch.object(p, 'json_request', return_value={}) as api:
            p.collect('devin')
            self.assertTrue(api.call_args.args[0].startswith('https://server.codeium.com/'))
            self.assertEqual(api.call_args.kwargs['data']['metadata']['apiKey'], 'synthetic-credential')
        self.assertEqual(path.read_text(), content)

    def test_explicit_accounts_do_not_discover_global_credentials(self):
        for name in ('kimi', 'supergrok', 'nous', 'modelstudio', 'cursor', 'grok-bot', 'devin'):
            with self.subTest(name=name), patch.dict(os.environ, {'AI_STATUS_ACCOUNT_ID': 'second-account'}), patch.object(Path, 'home', side_effect=AssertionError('Explicit accounts must not discover a home')), patch.object(p, 'json_request') as api:
                with self.assertRaises(QueryError):
                    p.collect(name)
                api.assert_not_called()

    def test_credential_env_references_are_resolved_without_literal_secrets(self):
        with patch.dict(os.environ, {'AI_STATUS_ACCOUNT_OPTIONS': '{"api_key_env":"MY_DEEPSEEK_KEY"}', 'MY_DEEPSEEK_KEY': 'synthetic-credential'}), patch.object(p, 'json_request', return_value={}) as api:
            p.collect('deepseek')
            self.assertEqual(api.call_args.args[1]['Authorization'], 'Bearer synthetic-credential')
        with patch.dict(os.environ, {'AI_STATUS_ACCOUNT_OPTIONS': '{"access_token_env":"MY_NOUS_TOKEN"}', 'MY_NOUS_TOKEN': 'synthetic-credential'}), patch.object(Path, 'home', side_effect=AssertionError('Explicit tokens must not discover a home')), patch.object(p, 'json_request', return_value={}) as api:
            p.collect('nous')
            self.assertEqual(api.call_args.args[1]['Authorization'], 'Bearer synthetic-credential')
        for platform, os_name, variable in [('linux', 'posix', 'XDG_CONFIG_HOME'), ('win32', 'nt', 'APPDATA')]:
            with self.subTest(platform=platform), patch.object(p, 'os', SimpleNamespace(name=os_name, environ={variable: str(self.root)})), patch.object(p, 'sys', SimpleNamespace(platform=platform)), patch.object(Path, 'home', side_effect=AssertionError('Configured roots must not discover a home')):
                self.assertEqual(p._config_root(), self.root)


class EncryptionReader(unittest.TestCase):
    def test_nist_aes_block_vectors(self):
        plain = bytes.fromhex('00112233445566778899aabbccddeeff')
        for key, encrypted in [('000102030405060708090a0b0c0d0e0f', '69c4e0d86a7b0430d8cdb78070b4c55a'), ('000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f', '8ea2b7ca516745bfeafc49904b496089')]:
            keys = oscrypt._keys(bytes.fromhex(key))
            self.assertEqual(oscrypt._block(plain, keys), bytes.fromhex(encrypted))
            self.assertEqual(oscrypt._block(bytes.fromhex(encrypted), keys, True), plain)

    def test_nist_gcm_authentication_and_decryption(self):
        key = bytes(16)
        encrypted = bytes.fromhex('0388dace60b6a392f328c2b971b2fe78')
        tag = bytes.fromhex('ab6e47d42cec13bdf53a67b21257bddf')
        self.assertEqual(oscrypt.decrypt_gcm(bytes(12)+encrypted+tag, key), bytes(16))
        with self.assertRaises(ValueError):
            oscrypt.decrypt_gcm(bytes(12)+encrypted+bytes(16), key)

    def test_linux_native_file_decrypts_without_writes(self):
        key = hashlib.pbkdf2_hmac('sha1', b'peanuts', b'saltysalt', 1, 16)
        def encrypt(value):
            raw = value.encode()
            raw += bytes([16-len(raw)%16])*(16-len(raw)%16)
            previous, result = b' '*16, b'v11'
            for offset in range(0, len(raw), 16):
                previous = oscrypt._block(bytes(a^b for a,b in zip(raw[offset:offset+16], previous)), oscrypt._keys(key))
                result += previous
            return base64.b64encode(result).decode()
        data = {'cursor-accounts': {'active': 'account', 'accounts': {'account': {'cursor-access-token': encrypt('test-access'), 'cursor-refresh-token': encrypt('test-refresh')}}}}
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'sand-secrets.json'
            content = json.dumps(data)
            path.write_text(content)
            with patch.object(oscrypt, '_secret', return_value=None), patch.object(oscrypt, 'os', SimpleNamespace(name='posix')), patch.object(oscrypt, 'sys', SimpleNamespace(platform='linux')):
                self.assertEqual(oscrypt.grok_bot_tokens(path), ('test-access', 'test-refresh'))
                with patch.dict(os.environ, {'AI_STATUS_AUTH_FILE': str(path)}, clear=True), patch.object(Path, 'home', side_effect=AssertionError('Explicit auth must not discover a home')), patch.object(p, 'json_request', return_value={}) as api:
                    p.collect('grok-bot')
                    self.assertEqual(api.call_args.args[1]['Authorization'], 'Bearer test-access')
            self.assertEqual(path.read_text(), content)


if __name__ == '__main__':
    unittest.main()
