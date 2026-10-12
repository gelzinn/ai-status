import os
import sys
import time
import subprocess
import shutil
import argparse
import json
import uuid
from . import daemon
from . import state
from . import logos
from . import render
from . import config as cfgmod
from . import quickshell, paths, fetch, accounts, __version__

TERMINALS = ["foot", "alacritty", "kitty", "ghostty", "wezterm", "xterm"]


def _provider_metric_keys(cache, dir_name, idx):
    """Ordered list of a provider's metric keys (same order the tooltip shows).
    Keys, not types, so metrics that share a type (e.g. Claude's general vs
    Fable weekly) are individually selectable."""
    for p in cache:
        if (p.get("_connection_id") or p.get("_dir")) == dir_name and p.get("_idx", 0) == idx:
            metrics = sorted(
                p.get("metrics", []),
                key=render.metric_sort_key,
            )
            return [render.metric_key(m) for m in metrics]
    return []


def _first_metric_for(cache, dir_name, idx):
    keys = _provider_metric_keys(cache, dir_name, idx)
    return keys[0] if keys else "rolling"

def _scroll(direction, frontend="waybar"):
    providers = cfgmod.enabled_connection_order()
    if not providers:
        return

    cache = state.load_cache()
    if frontend in ("quickshell", "macos", "swiftbar"):
        cache = [dict(p, metrics=quickshell.usable_metrics(p)) for p in cache if quickshell.usable_metrics(p)]
    items = []
    seen = set()
    for p in cache:
        identity = p.get("_connection_id") or p.get("_dir")
        if p.get("metrics") and identity in providers:
            key = (identity, p.get("_idx", 0))
            if key not in seen:
                seen.add(key)
                items.append(key)

    if not items:
        if frontend in ("quickshell", "macos", "swiftbar"):
            return
        items = [(p, 0) for p in providers]

    selected = state.load_selected() or {}
    current_dir = selected.get("provider")
    current_idx = selected.get("idx", 0)

    try:
        idx = items.index((current_dir, current_idx))
    except (ValueError, IndexError):
        idx = -1 if direction > 0 else 0

    new_dir, new_idx = items[(idx + direction) % len(items)]
    new_metric = _first_metric_for(cache, new_dir, new_idx)
    
    selected["provider"] = new_dir
    selected["idx"] = new_idx
    selected["metric"] = new_metric

    state.save_selected(selected)
    if frontend == "waybar":
        logos.update_current(selected)

def scroll_up(frontend="waybar"):
    _scroll(-1, frontend)

def scroll_down(frontend="waybar"):
    _scroll(1, frontend)

def cycle_metric(frontend="waybar"):
    selected = state.load_selected() or {}
    provider = selected.get("provider")
    idx = selected.get("idx", 0)
    current = selected.get("metric", "rolling")
    
    cache = state.load_cache()
    if frontend in ("quickshell", "macos", "swiftbar"):
        cache = [dict(p, metrics=quickshell.usable_metrics(p)) for p in cache if quickshell.usable_metrics(p)]
    keys = _provider_metric_keys(cache, provider, idx)

    if len(keys) <= 1:
        return

    try:
        pos = keys.index(current)
    except ValueError:
        pos = -1
    
    new_metric = keys[(pos + 1) % len(keys)]
    
    selected["provider"] = provider
    selected["idx"] = idx
    selected["metric"] = new_metric

    state.save_selected(selected)


# ── macOS / SwiftBar ──────────────────────────────────────────────────────
# macOS has no Waybar daemon streaming JSON. SwiftBar runs a plugin script on
# an interval (or as a long-lived streamable process) and renders its stdout.
# The plugin reads the shared cache and renders; a refresh is a detached child
# so the short-lived plugin invocation never blocks on the network.

SWIFTBAR_STALE_SECS = 300  # background-refresh cadence, matching the daemon


def _cache_age():
    try:
        return time.time() - os.path.getmtime(state.CACHE_FILE)
    except OSError:
        return None


def _refresh_in_flight():
    """True while *any* refresh holds the query lock — our own background thread,
    the ``Refresh`` menu action, or the periodic plugin's spawned child. Lets the
    stream animate the spark for a manual refresh too, not just its own."""
    try:
        return time.time() - os.path.getmtime(state.LOCK_FILE) < 90
    except OSError:
        return False


def _swiftbar_refresh():
    """Fetch every enabled provider and save the shared cache (blocking).

    Used both by the background refresh and by the "Refresh" menu action. The
    query lock keeps two refreshes from running at once — if one already holds
    it, this call is a no-op and the running one updates the cache."""
    from . import fetch
    if sys.platform == "darwin":
        from .macos import configure_environment
        configure_environment()

    if not state.acquire_lock():
        return
    try:
        data = fetch.fetch_all_data(include_errors=True)
        if data:
            state.save_cache(data)
    finally:
        state.release_lock()


def _spawn_background_refresh():
    """Detach a child running ``swiftbar-refresh`` so the cache refreshes out of
    band. A thread would die with the plugin process, so this must be its own
    session. Skips spawning when a refresh is already in flight."""
    if not state.acquire_lock():
        return
    state.release_lock()  # only probed for one in flight; the child re-acquires
    try:
        subprocess.Popen(
            [sys.executable, os.path.realpath(sys.argv[0]), "swiftbar-refresh"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def _swiftbar_select(args):
    """Set the active provider/metric from a menu click (replaces Waybar scroll).

    ``args`` = [dir_name, idx, metric_key?]. A missing metric falls back to the
    provider's first metric."""
    # SwiftBar may or may not strip surrounding quotes from param values; strip
    # defensively so ``param4="rolling"`` never arrives as the literal `"rolling"`
    # (which would fail every comparison and make clicks a silent no-op).
    args = [a[1:-1] if len(a) >= 2 and a[0] == '"' and a[-1] == '"' else a for a in args]
    if not args:
        return
    dir_name = args[0]
    try:
        idx = int(args[1]) if len(args) > 1 else 0
    except ValueError:
        idx = 0
    metric = args[2] if len(args) > 2 else None
    quickshell.select_metric({"provider": dir_name, "idx": idx,
                              "metric": metric or _first_metric_for(state.load_cache(), dir_name, idx)})


def swiftbar_render():
    """Print the SwiftBar menu from the cache, kicking a background refresh when
    the cache is missing or stale."""
    from . import swiftbar as sb

    age = _cache_age()
    if age is None or age >= SWIFTBAR_STALE_SECS:
        _spawn_background_refresh()
    print(sb.render_from_state())


def _swiftbar_sig():
    """Cheap change signature (cache + selection mtimes) so the idle stream only
    re-emits when something actually changed."""
    def mt(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0
    return (mt(state.CACHE_FILE), mt(state.SELECTED_FILE), mt(cfgmod.CONFIG_FILE), mt(cfgmod.accounts_file()))


def swiftbar_stream():
    """Long-lived SwiftBar *streamable* plugin.

    Renders from the shared cache (the Tier-1 model) and animates the Claude
    spark in the menu bar while a refresh is in flight — the menu-bar analogue
    of the shimmer the Linux tooltip shows. SwiftBar keeps this process alive,
    so the refresh runs in a background thread and the loop streams one full
    menu per frame, each terminated by SwiftBar's ``~~~`` separator.
    """
    import signal
    import threading
    from . import swiftbar as sb

    state.register_pid()  # lets `ai-status refresh` (SIGUSR1) poke us
    refreshing = threading.Event()

    def do_refresh():
        refreshing.set()
        try:
            _swiftbar_refresh()
        finally:
            refreshing.clear()

    def kick(*_):
        if not refreshing.is_set():
            threading.Thread(target=do_refresh, daemon=True).start()

    try:
        signal.signal(signal.SIGUSR1, kick)
    except (ValueError, OSError):
        pass

    FRAME_DELAY = 0.12   # spark animation cadence
    IDLE_POLL = 0.4      # responsiveness to menu-click selection changes
    HEARTBEAT = 30.0     # re-emit at least this often when idle
    last_auto = 0.0
    last_sig = None
    last_emit = 0.0
    frame_idx = 0

    age = _cache_age()
    if age is None or age >= SWIFTBAR_STALE_SECS:
        kick()

    while True:
        try:
            now = time.time()
            age = _cache_age()
            if (not refreshing.is_set()
                    and (age is None or age >= SWIFTBAR_STALE_SECS)
                    and now - last_auto >= SWIFTBAR_STALE_SECS):
                last_auto = now
                kick()

            cache = state.load_cache()
            selected = state.load_selected()

            if refreshing.is_set() or _refresh_in_flight():
                spinner = sb.SPINNERS[frame_idx % len(sb.SPINNERS)]
                menu = sb.render_menu(
                    cache, selected,
                    spinner=spinner,
                    title_image=sb.spark_frame(frame_idx),
                )
                sys.stdout.write(menu + "\n~~~\n")
                sys.stdout.flush()
                frame_idx += 1
                last_sig = None  # force one fresh emit when the animation ends
                time.sleep(FRAME_DELAY)
            else:
                frame_idx = 0
                sig = _swiftbar_sig()
                if sig != last_sig or now - last_emit >= HEARTBEAT:
                    sys.stdout.write(sb.render_menu(cache, selected) + "\n~~~\n")
                    sys.stdout.flush()
                    last_sig = sig
                    last_emit = now
                time.sleep(IDLE_POLL)
        except (BrokenPipeError, KeyboardInterrupt):
            break
        except Exception:
            time.sleep(1)


def print_logo():
    """Output for the waybar image module: line 1 is the logo PNG path, line 2
    is the tooltip (the same rich breakdown as the text module).

    Newlines in the tooltip are encoded as U+2028 (LINE SEPARATOR) so waybar
    keeps it as a single output line — the image module only reads one line of
    tooltip — while Pango still renders the breaks. This is what lets hovering
    the logo show the full tooltip, not just the icon.
    """
    selected = state.load_selected() or {}
    if state.get_icon_mode(selected) != "logo":
        print("")
        return
    # current.png is kept up to date by the daemon (startup + selection change)
    # and the scroll command; only seed it here if it's missing so this hot path
    # (called once per loading frame) stays a couple of file reads.
    if not os.path.exists(logos.CURRENT_PNG):
        logos.update_current(selected, notify=False)
    path = logos.CURRENT_PNG if os.path.exists(logos.CURRENT_PNG) else ""

    # Prefer the live tooltip the daemon mirrors (so the logo shows the same
    # loading animation as the text); fall back to a fresh render if absent.
    tooltip = ""
    try:
        if os.path.exists(logos.TOOLTIP_FILE):
            with open(logos.TOOLTIP_FILE, encoding="utf-8") as f:
                tooltip = f.read()
        else:
            tooltip = render.build_final_state(state.load_cache(), selected).get("tooltip", "")
        tooltip = tooltip.replace("\n", " ")
    except Exception:
        tooltip = ""

    sys.stdout.write(f"{path}\n{tooltip}")


def revert_waybar():
    """Restore the Waybar config we backed up before configuring it — a clean
    undo for an automatic setup, in case anything looks off."""
    import shutil
    cfg = os.path.expanduser("~/.config/waybar/config.jsonc")
    bak = cfg + ".ai-status.bak"
    if not os.path.exists(bak):
        print("No AI Status backup found — nothing to revert.")
        print("(A backup is only made when you let the installer configure Waybar for you;")
        print(" if you added the modules by hand, just remove them yourself.)")
        return
    try:
        if os.path.exists(cfg):
            shutil.copy2(cfg, cfg + ".pre-revert")  # keep the revert itself undoable
        shutil.copy2(bak, cfg)
    except Exception as e:
        print(f"Could not restore the backup: {e}")
        sys.exit(1)
    print(f"Restored your original Waybar config from:\n  {bak}")
    try:
        subprocess.run(["pkill", "-SIGUSR2", "waybar"], capture_output=True, timeout=3)
        print("Reloaded Waybar — the ai-status modules were removed.")
    except Exception:
        print("Restart Waybar to apply the change.")


class _CLIParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def _check_value(self, action, value):
        if isinstance(action, argparse._SubParsersAction) and value not in action.choices:
            raise argparse.ArgumentError(action, f"unknown command '{value}'")
        super()._check_value(action, value)

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n\nRun '{self.prog} --help' for usage and examples.\n")


def _configure_accounts_parser(parser):
    parser.description = (
        "List default provider connections detected by the desktop and saved accounts.\n"
        "With no subcommand, list connections from the last usage snapshot.\n"
        "Default CLI logins do not need accounts add; --refresh checks enabled connections."
    )
    parser.epilog = (
        "Examples:\n"
        "  ai-status accounts\n"
        "  ai-status accounts --refresh\n"
        "  ai-status accounts list --saved --json\n"
        "  ai-status accounts add codex --id work --label Work --auth-file ~/.codex-work/auth.json\n"
        "  ai-status accounts edit work --disabled\n"
        "  ai-status accounts list --json\n\n"
        "Find provider IDs: ai-status providers\n"
        "More options:      ai-status accounts add --help"
    )
    parser.set_defaults(action="list", json=False, saved=False, refresh=False)
    options = (
        ("--json", "Print connection metadata as JSON without credential values"),
        ("--saved", "List only manually saved accounts; preserve the original JSON schema"),
        ("--refresh", "Fetch usage for enabled connections before listing (may take a few seconds)"),
    )
    for option, description in options:
        parser.add_argument(option, action="store_true", help=description)
    commands = parser.add_subparsers(dest="action", title="account commands", metavar="COMMAND")
    listing = commands.add_parser("list", help="List detected default connections and saved accounts (default)",
                                  description="List connections from the last usage snapshot and saved account configuration.")
    for option, description in options:
        listing.add_argument(option, action="store_true", default=argparse.SUPPRESS, help=description)
    listing.epilog = "Use --refresh to check enabled connections now, or --saved to list only manually added accounts."
    for verb in ("add", "edit"):
        command = commands.add_parser(verb, help=f"{verb.title()} an account connection",
                                      description=f"{verb.title()} an account using credential file or environment references.")
        command.epilog = (
            "Examples:\n"
            "  ai-status accounts add codex --id work --label Work --auth-file ~/.codex-work/auth.json\n"
            "  ai-status accounts add openrouter --id work-api --env OPENROUTER_API_KEY=OPENROUTER_WORK_KEY\n"
            "  ai-status accounts add --file account.json\n"
            "  ai-status accounts edit work --label Office --enabled\n\n"
            "Use ai-status providers to find provider IDs. For --env, pass the name of an\n"
            "existing environment variable containing the credential."
        )
        if verb == "add":
            command.add_argument("provider", nargs="?", help="Provider ID from ai-status providers; may also be set in --file")
            command.add_argument("--id", dest="account_id", help="Unique account ID (generated if omitted)")
        else:
            command.add_argument("account_id", help="Account ID from ai-status accounts")
        command.add_argument("--label", help="Account name shown in the desktop interface")
        command.add_argument("--auth-file", help="Path to an existing provider credential file")
        command.add_argument("--env", action="append", default=[], metavar="TARGET=SOURCE_ENV", help="Resolve TARGET from SOURCE_ENV at query time")
        command.add_argument("--file", help="Account JSON file, or - to read stdin; options and references belong in this JSON")
        command.add_argument("--disabled", action="store_true", help="Disable usage collection for this account")
        command.add_argument("--enabled", action="store_true", help="Enable usage collection for this account")
    removing = commands.add_parser("remove", help="Remove a connection, keeping credential files",
                                   description="Remove a saved account connection. Its credential files are retained.")
    removing.add_argument("account_id", help="Account ID from ai-status accounts")
    parser.set_defaults(action="list")


def _print_table(headers, rows):
    rows = [[" ".join(str(value).split()) for value in row] for row in rows]
    widths = [max([len(header), *(len(row[index]) for row in rows)]) for index, header in enumerate(headers)]
    for row in [headers, *rows]:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip())


def _accounts_main(argv=None):
    parser = _CLIParser(prog="ai-status accounts")
    _configure_accounts_parser(parser)
    return _run_accounts(parser.parse_args(sys.argv[2:] if argv is None else argv), parser)


def _connection_usage_status(entries, stale):
    usable = []
    for entry in entries:
        try:
            if quickshell.usable_metrics(entry):
                usable.append(entry)
        except (AttributeError, TypeError, ValueError, OverflowError):
            continue  # A malformed cache entry cannot establish usable usage.
    if usable:
        return "cached" if stale or any(entry.get("_cached") for entry in usable) else "available"
    return "unavailable" if entries else "not_checked"


def _listed_connections(records):
    # This is the desktop's last collected snapshot, not a probe of credential
    # files or the Keychain. Listing must remain fast and have no side effects.
    cached = {}
    for entry in state.load_cache():
        if not isinstance(entry, dict):
            continue
        identity = entry.get("_connection_id")
        if not isinstance(identity, str) or not identity:
            account_id = entry.get("_account_id")
            identity = "account:" + account_id if isinstance(account_id, str) and account_id else entry.get("_dir")
        if not isinstance(identity, str) or not identity:
            continue
        if not identity.startswith("account:") and entry.get("_account_id") is not None:
            continue
        if not identity.startswith("account:") and entry.get("_dir") not in (None, identity):
            continue
        cached.setdefault(identity, []).append(entry)
    age = _cache_age()
    stale = age is not None and age >= SWIFTBAR_STALE_SECS
    enabled = cfgmod.enabled_order()
    defaults = []
    for provider in cfgmod.available_providers():
        usage = _connection_usage_status(cached.get(provider, []), stale)
        if usage in ("available", "cached"):
            defaults.append({"id": provider, "provider": provider, "label": "Default",
                             "enabled": provider in enabled, "connection_id": provider,
                             "source": "default", "usage_status": usage})
    saved = []
    for record in records:
        identity = "account:" + record["id"]
        entries = [entry for entry in cached.get(identity, [])
                   if entry.get("_dir") in (None, record["provider"])
                   and entry.get("_account_id") in (None, record["id"])]
        saved.append({**accounts.public_record(record), "connection_id": identity,
                      "source": "saved", "usage_status": _connection_usage_status(entries, stale)})
    return defaults + saved


def _list_accounts(args, records):
    if args.saved:
        public = [accounts.public_record(record) for record in records]
        if args.json:
            print(json.dumps(public, ensure_ascii=False))
        elif public:
            _print_table(["ID", "PROVIDER", "LABEL", "STATUS"], [
                [record["id"], record["provider"], record["label"], "enabled" if record["enabled"] else "disabled"]
                for record in public
            ])
        else:
            print("No saved account connections configured.\n")
            print("Show default CLI connections: ai-status accounts")
            print("Add another account:         ai-status accounts add --help")
        return 0
    if args.refresh:
        state.save_cache(fetch.fetch_all_data(include_errors=True))
    public = _listed_connections(records)
    if args.json:
        print(json.dumps(public, ensure_ascii=False))
    elif public:
        _print_table(["ID", "PROVIDER", "LABEL", "SOURCE", "COLLECTION", "USAGE"], [
            [("default:" + record["id"]) if record["source"] == "default" else record["id"],
             record["provider"], record["label"], record["source"],
             "enabled" if record["enabled"] else "disabled", record["usage_status"]]
            for record in public
        ])
        print("\nDefault connections use existing provider logins. Edit/remove applies to saved accounts.")
        print("Usage is from the last collected snapshot; use --refresh to check enabled connections now.")
        print("Configure default connections: ai-status config")
    else:
        print("No account connections detected yet.\n")
        print("Check your existing CLI logins: ai-status accounts --refresh")
        print("Configure providers:           ai-status config")
        print("Add another account:           ai-status accounts add --help")
    return 0


def _unknown_account(account_id):
    if account_id.startswith("default:") or account_id in cfgmod.available_providers():
        raise accounts.AccountError("Default provider connections are managed with ai-status config. Edit/remove applies only to saved accounts.")
    raise accounts.AccountError("Unknown account ID. Use ai-status accounts --saved to find saved account IDs.")


def _run_accounts(args, parser):
    if args.action != "list":
        for option in ("json", "saved", "refresh"):
            if getattr(args, option):
                parser.error(f"--{option} is only supported by accounts list")
    if args.saved and args.refresh:
        parser.error("--saved cannot be combined with --refresh")
    try:
        document = accounts.load_document(cfgmod.accounts_file())
        records = document["accounts"]
        if args.action == "list":
            return _list_accounts(args, records)
        if args.action == "remove":
            if not any(record["id"] == args.account_id for record in records):
                _unknown_account(args.account_id)
            document["accounts"] = [record for record in records if record["id"] != args.account_id]
            if "order" in document:
                document["order"] = [identity for identity in document["order"] if identity != "account:" + args.account_id]
            accounts.save_document(document, cfgmod.accounts_file())
            state.trigger_refresh()
            print("Account connection removed.")
            return 0
        payload = {}
        if args.file:
            try:
                if args.file == "-":
                    payload = json.load(sys.stdin)
                else:
                    with open(args.file, encoding="utf-8-sig") as stream:
                        payload = json.load(stream)
            except (OSError, ValueError):
                raise accounts.AccountError("Unable to read account JSON; check its format and permissions.") from None
            if not isinstance(payload, dict):
                raise accounts.AccountError("Account JSON must be an object.")
        if args.action == "edit":
            previous = next((record for record in records if record["id"] == args.account_id), None)
            if previous is None:
                _unknown_account(args.account_id)
            record = {**previous, **payload, "id": args.account_id}
        else:
            record = dict(payload)
            if args.provider:
                record["provider"] = args.provider
            record["id"] = args.account_id or record.get("id") or uuid.uuid4().hex
            if not record.get("provider"):
                raise accounts.AccountError("Specify a provider or use --file with a provider field. Find provider IDs with ai-status providers.")
        if args.label is not None:
            record["label"] = args.label
        if args.auth_file is not None:
            record["auth_file"] = args.auth_file
        if args.disabled and args.enabled:
            raise accounts.AccountError("Choose either enabled or disabled.")
        if args.disabled or args.enabled:
            record["enabled"] = args.enabled
        if args.env:
            overrides = dict(record.get("env") or {})
            for reference in args.env:
                if "=" not in reference:
                    raise accounts.AccountError("Environment references must use TARGET=SOURCE_ENV.")
                target, source = reference.split("=", 1)
                overrides[target] = {"from_env": source}
            record["env"] = overrides
        record = accounts.normalize(record)
        if record["provider"] not in cfgmod.available_providers():
            raise accounts.AccountError("Unknown provider; use ai-status providers to list installed provider IDs.")
        if args.action == "add":
            if any(existing["id"] == record["id"] for existing in records):
                raise accounts.AccountError("Account ID already exists; use accounts edit.")
            records.append(record)
        else:
            document["accounts"] = [record if existing["id"] == record["id"] else existing for existing in records]
        if "order" in document:
            identity = "account:" + record["id"]
            document["order"] = [item for item in document["order"] if item != identity]
            if record["enabled"]:
                document["order"].append(identity)
        accounts.save_document(document, cfgmod.accounts_file())
        state.trigger_refresh()
        print(f"Account connection saved: {record['id']}")
        return 0
    except (accounts.AccountError, OSError):
        # AccountError messages are deliberately secret-free; filesystem errors
        # may echo arbitrary paths and therefore use a fixed message.
        error = sys.exc_info()[1]
        print(str(error) if isinstance(error, accounts.AccountError) else "Unable to read or save account configuration.", file=sys.stderr)
        return 1


_FRONTEND_COMMANDS = (
    "daemon", "refresh", "config", "save-settings", "select-metric", "scroll-up",
    "scroll-down", "cycle-metric", "logo", "revert",
)


def _add_frontend_arguments(parser, visible=()):
    # Preserve flags before and after the command while showing them only in
    # the help of the command that uses them. Suppressed defaults prevent a
    # subparser from overwriting a value supplied before the command.
    options = (
        ("--format", {"choices": ["waybar", "quickshell", "macos"]}, "Daemon output format (default: waybar)"),
        ("--frontend", {"choices": ["waybar", "quickshell", "macos", "swiftbar"]}, "Desktop integration (default: waybar)"),
        ("--settings-json", {"metavar": "JSON"}, "Validated settings object from the desktop interface"),
        ("--selection-json", {"metavar": "JSON"}, "Provider, account index and metric selection object"),
    )
    for option, settings, description in options:
        parser.add_argument(option, **settings, default=argparse.SUPPRESS,
                            help=description if option in visible else argparse.SUPPRESS)


def _build_parser():
    parser = _CLIParser(
        prog="ai-status", description="AI Status — AI provider usage in your desktop bar.",
        epilog=(
            "Examples:\n"
            "  ai-status config                 Configure providers and display preferences\n"
            "  ai-status providers              Find provider IDs\n"
            "  ai-status accounts               List default connections and saved accounts\n"
            "  ai-status accounts add --help    Connect another account\n"
            "  ai-status status                 Fetch usage as JSON\n\n"
            "Desktop integration commands:\n"
            "  daemon, tray, macos, swiftbar, swiftbar-stream, swiftbar-refresh,\n"
            "  swiftbar-select, save-settings, select-metric, scroll-up, scroll-down,\n"
            "  cycle-metric, logo, revert\n\n"
            "Run ai-status COMMAND --help or ai-status help COMMAND for details.\n"
            "Without a command: show this help on Linux; open the app on Windows/macOS."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__, help="Show the installed version and exit")
    _add_frontend_arguments(parser)
    commands = parser.add_subparsers(dest="command", title="commands", metavar="COMMAND")
    descriptions = (
        ("config", "Configure providers and display preferences"),
        ("status", "Fetch current usage and print JSON"),
        ("refresh", "Request a refresh in the running desktop app or bar"),
        ("update", "Start an optional update using your installation method"),
        ("providers", "List installed provider IDs and default connection settings"),
        ("accounts", "List default connections and manage saved accounts"),
        ("doctor", "Print version, paths and runtime diagnostics as JSON"),
        ("help", "Show help for a command, including nested commands"),
    )
    command_parsers = {}
    for name, description in descriptions:
        command_parsers[name] = commands.add_parser(name, help=description, description=description + ".")
    _configure_accounts_parser(command_parsers["accounts"])
    command_parsers["config"].epilog = (
        "Windows and macOS open native Settings by default. On Linux, this opens the\n"
        "terminal configuration UI. On macOS, --frontend selects the terminal UI.\n\n"
        "Set quota display without opening Settings:\n"
        "  ai-status config --usage-display remaining\n"
        "  ai-status config --usage-display used"
    )
    command_parsers["config"].add_argument(
        "--usage-display", choices=state.USAGE_DISPLAY_MODES,
        help="Show quota used or remaining; save directly without opening Settings (default: used)",
    )
    command_parsers["status"].epilog = "Output: a JSON object with providers and errors. Requires provider authentication."
    command_parsers["update"].epilog = (
        "Windows opens a checksummed installer. Linux and macOS open the updater in\n"
        "a terminal. Portable and custom installations use the update guide:\n"
        "https://github.com/gelzinn/ai-status/blob/main/packages/lib/UPDATES.md\n\n"
        "An opened updater still needs to finish; this command does not force updates."
    )
    command_parsers["providers"].add_argument("--json", action="store_true", help="Print provider metadata as JSON")
    command_parsers["providers"].epilog = (
        "Enabled means the default connection is configured for collection, not that it is\n"
        "authenticated. Detected connections and saved accounts are listed by ai-status accounts.\n\n"
        "Configure providers: ai-status config\n"
        "Authentication guide: https://ai-status.gelzin.com/providers"
    )
    command_parsers["doctor"].add_argument("--smoke", action="store_true", help=argparse.SUPPRESS)
    command_parsers["doctor"].add_argument("--http-smoke", action="store_true", help=argparse.SUPPRESS)
    command_parsers["help"].add_argument("command_path", nargs="*", metavar="COMMAND", help="For example: accounts add")
    integrations = (
        ("daemon", "Stream usage for the desktop bar", ("--format",)),
        ("save-settings", "Save settings supplied by a native desktop interface", ("--frontend", "--settings-json")),
        ("select-metric", "Select a usage metric from a native desktop interface", ("--frontend", "--selection-json")),
        ("scroll-up", "Select the previous provider with usage data", ("--frontend",)),
        ("scroll-down", "Select the next provider with usage data", ("--frontend",)),
        ("cycle-metric", "Select the next limit for the active provider", ("--frontend",)),
        ("logo", "Print the Waybar logo path and tooltip", ()),
        ("revert", "Restore the Waybar configuration backup", ()),
        ("tray", "Open the native Windows tray app", ()),
        ("macos", "Open the native macOS menu bar app", ()),
        ("swiftbar", "Render the SwiftBar menu from cached usage", ()),
        ("swiftbar-stream", "Stream the animated SwiftBar menu", ()),
        ("swiftbar-refresh", "Fetch usage for SwiftBar and save the cache", ()),
        ("swiftbar-select", "Select a provider and metric from SwiftBar", ()),
    )
    for name, description, visible in integrations:
        # Integration commands remain discoverable in the epilog without
        # crowding the list of everyday tasks.
        command = commands.add_parser(name, description=description + ".")
        command_parsers[name] = command
        if name in _FRONTEND_COMMANDS:
            _add_frontend_arguments(command, visible)
    for name in ("config", "refresh"):
        _add_frontend_arguments(command_parsers[name], ("--frontend",) if name == "config" else ())
    for name in ("tray", "macos"):
        command_parsers[name].add_argument("--settings", action="store_true", help="Open the app's Settings page")
    selection = command_parsers["swiftbar-select"]
    selection.add_argument("provider", help="Provider or saved account connection ID")
    selection.add_argument("idx", nargs="?", default="0", help="Provider result index (default: 0)")
    selection.add_argument("metric", nargs="?", help="Metric key (default: first available limit)")
    return parser, command_parsers


def _command_help(parser, command_path):
    for name in command_path:
        commands = next((action for action in parser._actions if isinstance(action, argparse._SubParsersAction)), None)
        if commands is None or name not in commands.choices:
            parser.error(f"unknown command '{name}'")
        parser = commands.choices[name]
    parser.print_help()
    return 0


def _providers_main(as_json=False):
    metadata = (paths.read_json(paths.LIB_DIR / "assets/providers.json")
                or paths.read_json(paths.LIB_DIR.parent / "shared/providers/providers.json"))
    enabled = cfgmod.enabled_order()
    records = [{"id": name, "name": metadata.get(name, {}).get("name", name), "enabled": name in enabled}
               for name in cfgmod.available_providers()]
    if as_json:
        print(json.dumps(records, ensure_ascii=False))
    elif records:
        _print_table(["ID", "NAME", "DEFAULT CONNECTION"], [
            [record["id"], record["name"], "enabled" if record["enabled"] else "disabled"] for record in records
        ])
        print("\nEnabled indicates collection settings, not authentication status.")
        print("Configure providers: ai-status config")
        print("Detected and saved connections: ai-status accounts")
    else:
        print("No provider collectors found. Reinstall AI Status to restore them.")
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--query":
        if len(argv) != 2:
            raise SystemExit("Usage: ai-status --query PROVIDER")
        fetch.run_query(argv[1])
        return 0
    parser, command_parsers = _build_parser()
    args = parser.parse_args(argv)
    command = args.command
    if command not in _FRONTEND_COMMANDS:
        for name in ("format", "frontend", "settings_json", "selection_json"):
            if hasattr(args, name):
                parser.error(f"--{name.replace('_', '-')} requires a desktop integration command")
    else:
        _validate_frontend_args(args, command_parsers[command])
    if command == "help":
        return _command_help(parser, args.command_path)
    if command == "accounts":
        return _run_accounts(args, command_parsers[command])
    if command == "providers":
        return _providers_main(args.json)
    if command == "config" and args.usage_display is not None:
        selected = state.load_selected() or {}
        selected["usage_display"] = args.usage_display
        try:
            paths.atomic_json(state.SELECTED_FILE, selected)
        except OSError:
            print("Unable to save display preferences.", file=sys.stderr)
            return 1
        print(f"Usage display: {args.usage_display.title()}")
        return 0
    if command == "update":
        from . import updates
        try:
            print(updates.run_update(), flush=True)
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
        return 0
    if command == "doctor":
        info = {"version": fetch.get_version_info()["current"],
                "providers": cfgmod.available_providers(), "config": str(paths.CONFIG_DIR),
                "cache": str(paths.CACHE_DIR), "desktop": False, "conpty": False}
        try:
            from . import tray
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication([])
            info["desktop"] = not tray.status_icon().isNull()
            if paths.IS_WINDOWS:
                from .windows_console import available
                info["conpty"] = available()
            if args.smoke:
                info.update(tray.smoke_test())
        except ImportError:
            pass
        if args.http_smoke:
            from .provider_http import request
            response = json.loads(request("https://api.github.com/", timeout=10))
            info["native_https"] = paths.IS_WINDOWS and "current_user_url" in response
        print(json.dumps(info, ensure_ascii=False))
    elif command == "status":
        errors = {}
        data = fetch.fetch_all_data(on_error=lambda name, message: errors.update({name: message}))
        state.save_cache(data)
        print(json.dumps({"providers": data, "errors": errors}, ensure_ascii=False))
    elif command in ("swiftbar", "swiftbar-stream", "swiftbar-refresh", "swiftbar-select"):
        actions = {"swiftbar": swiftbar_render, "swiftbar-stream": swiftbar_stream,
                   "swiftbar-refresh": _swiftbar_refresh}
        if command == "swiftbar-select":
            try:
                values = [args.provider, args.idx]
                if args.metric is not None:
                    values.append(args.metric)
                _swiftbar_select(values)
            except (ValueError, OSError) as error:
                print(str(error), file=sys.stderr)
                return 1
        else:
            actions[command]()
    elif command == "macos" or (sys.platform == "darwin" and command in (None, "config") and not hasattr(args, "frontend")):
        from . import macos
        macos.launch(configure=command == "config" or getattr(args, "settings", False))
    elif command == "tray" or (paths.IS_WINDOWS and command in (None, "config")):
        from . import tray
        tray.run(configure=command == "config" or getattr(args, "settings", False))
    elif command is None:
        parser.print_help()
    else:
        return _frontend_main(args, command_parsers[command])
    return 0


def _validate_frontend_args(args, parser):
    if getattr(args, "format", "waybar") != "waybar" and args.command != "daemon":
        parser.error("--format is only supported by daemon")
    if getattr(args, "settings_json", None) is not None and args.command != "save-settings":
        parser.error("--settings-json is only supported by save-settings")
    if getattr(args, "selection_json", None) is not None and args.command != "select-metric":
        parser.error("--selection-json is only supported by select-metric")
    if args.command in ("select-metric", "save-settings"):
        option = "selection-json" if args.command == "select-metric" else "settings-json"
        if getattr(args, "frontend", "waybar") not in ("quickshell", "macos") or getattr(args, option.replace("-", "_"), None) is None:
            parser.error(f"{args.command} requires --frontend quickshell|macos and --{option}")


def _frontend_main(args, parser):
    for name, default in (("format", "waybar"), ("frontend", "waybar"), ("settings_json", None), ("selection_json", None)):
        if not hasattr(args, name):
            setattr(args, name, default)
    if args.command == "select-metric":
        try:
            quickshell.select_metric(json.loads(args.selection_json))
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
    elif args.command == "save-settings":
        try:
            quickshell.save_settings(json.loads(args.settings_json))
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
    elif args.command == "refresh":
        state.trigger_refresh()
    elif args.command == "daemon":
        if args.format == "waybar":
            paths.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            sys.stderr = open(paths.LOG_FILE, 'w', encoding='utf-8')
        daemon.run(output_format=args.format)
    elif args.command == "config":
        if not sys.stdout.isatty():
            for term in TERMINALS:
                executable = shutil.which(term)
                if executable:
                    subprocess.Popen([executable, "-e", sys.executable, os.path.realpath(sys.argv[0]),
                                      "config", "--frontend", args.frontend])
                    return 0
            print("No supported terminal found. Run ai-status config in an interactive terminal.", file=sys.stderr)
            return 1
        from . import tui
        tui.run()
    elif args.command == "scroll-up":
        scroll_up(args.frontend)
    elif args.command == "scroll-down":
        scroll_down(args.frontend)
    elif args.command == "cycle-metric":
        cycle_metric(args.frontend)
    elif args.command == "logo":
        print_logo()
    elif args.command == "revert":
        revert_waybar()
