# Quota alerts and recovery notices

AI Status alerts when a subscription quota reaches 80%, 95% or 100% consumed.
Configure them in Settings on Quickshell, Windows or macOS, or with the CLI on
any platform. A window jumping from 79% to 96% sends one 95% alert. Reaching
100% later sends the exhaustion alert. Alert text identifies the account,
window or model, actual consumption and the provider's reported reset.
Displaying **Remaining** in the panel keeps alerts based on quota consumed.

```bash
ai-status notifications --thresholds 80,95,100
ai-status notifications --connection account:personal --metric weekly --thresholds 95,100
ai-status notifications --connection codex --metric rolling --disable
ai-status notifications --mute 60
ai-status notifications --resume
ai-status notifications --quiet-hours 22:00-08:00
ai-status notifications --work-hours 09:00-18:00
ai-status notifications --recent-only
ai-status notifications --disable
```

`--connection` and `--metric` together edit a window's override. Omitting them
edits defaults. Find connection IDs with `ai-status accounts`; metric keys
are in `ai-status status` or the Settings limit selector. Examples include
`rolling`, `weekly` and `weekly:Fable`. A `*` metric in a JSON rule matches
all windows of that connection. Exact window rules take priority. Thresholds
are whole percentages from 1 to 100. An empty threshold list in JSON disables
threshold alerts while keeping recovery monitoring.

Silence, quiet hours and working hours apply to all quota and recovery notices.
Hours follow the computer's local timezone and can cross midnight. Clear a
schedule with `--quiet-hours ''` or `--work-hours ''`. Crossings observed while
silenced are remembered and do not produce a backlog of old alerts when
silence ends. `--all-accounts` restores recovery monitoring for every enabled
connection; `--recent-only` requires nonzero usage first observed, or increasing
consumption, in the past 24 hours.

## Confirmed recovery

The engine remembers exhausted windows. A successful fresh response must
contain every previously observed quota window before it can confirm full
recovery. If the rolling quota resets while the weekly quota remains exhausted,
the partial recovery notice names the remaining restriction. Only a response
showing all observed quota windows below 100% produces the full recovery notice.
Each recovery episode is notified once, including across app restarts.

An exhausted window's reported reset schedules a fresh check shortly afterward,
while collection still respects the provider's cooldown. A reset countdown
reaching zero, a failed request, a cached fallback or an omitted window never
confirms capacity. A fresh response retaining an elapsed reset returns to the
normal five-minute cadence. Delayed resets and manually used reset credits are
handled by observed consumption changes rather than assuming timers are correct.

Only valid subscription percentages from successful observations less than ten
minutes old enter the engine. Amounts, credit balances and local API budgets
are excluded. Legacy snapshots without observation metadata wait for a new
collection. Reset dates are never invented when the provider omits them.

## Delivery and saved preferences

Linux uses `notify-send` from `libnotify`; the desktop must provide a notification
service. Windows uses the running tray app's native notification support. macOS
uses Notification Center under the AI Status app's identity and asks for its
permission when alerts are enabled. The operating system's notification and
Do Not Disturb settings control presentation. Unsupported delivery or denied
permission leaves collection and the panel working.

On desktops supporting notification actions, clicking opens the relevant
account and limit. Quickshell opens a single panel; Waybar selects the limit
for its display and tooltip. Windows opens the usage panel. macOS opens the
menu bar panel. Older Linux notification tools retain ordinary alerts without
an action button.

Preferences are stored in `notifications.json` beside the existing AI Status
configuration: `~/.config/ai-status` on Linux/macOS or `%APPDATA%\ai-status`
on Windows. Export with `ai-status notifications --json`; import a document
with `ai-status notifications --file preferences.json` (or `--file -` for stdin).
Native Settings saves the same file and preserves other accounts' rules.

Deduplication is saved in `notification-state.json`. A profile-wide lock and
an atomic reservation before delivery prevent multiple local collectors or
monitors from repeating a crossing. Profiles on separate computers remain
independent. Failed transports retry on a later fresh sample. A crash after
reservation can lose an alert instead of repeating it.

macOS keeps a durable delivery outbox for up to five minutes and uses stable
Notification Center request IDs across restarts. Expired, silenced or
superseded notices are discarded. Known account identities survive token
rotation; if credentials supply no stable account identity, changing the
opaque token may be treated as a new login. Switching an identified account
never confirms recovery for the previous account.

## Development validation

Run the shared engine, collector and desktop tests with:

```bash
PYTHONPATH=packages/lib/src QT_QPA_PLATFORM=offscreen \
  python3 -m unittest discover -s packages/lib/tests -v
python3 packages/lib/tests/run_qml_tests.py
```

Tests cover threshold transitions, precision, jumps, resets, simultaneous local
processes, restart deduplication, silence, permission and delivery failures,
stale/error observations, two-window partial recovery and full recovery.
The native macOS `--smoke` checks preference serialization and queued events;
the existing macOS CI job builds the app. Desktop notification presentation,
permission dialogs and banner clicks also require a real desktop smoke test.
