# AI Status

Monitor AI provider usage limits in **Waybar and the Omarchy Quickshell bar** — across Claude, Copilot, Codex, Z.AI, Kiro, Antigravity, OpenCode, and Command Code in real time.

<img width="348" height="954" alt="Screenshot" src="https://github.com/user-attachments/assets/dcba0b97-d462-452e-b1b6-000cc445b803" />

## Features

| Feature | Description |
|---|---|
| **Two Bars** | Native Omarchy Quickshell widget and panel, plus the existing Waybar integration |
| **Multi-Provider** | Tracks API usage limits across eight AI services simultaneously |
| **Live Updates** | Auto-refreshes every 5 minutes with animated loading states |
| **Usage Details** | Per-provider progress bars, percentages, and resets in a Waybar tooltip or Quickshell panel |
| **Configurable** | Enable, disable, or reorder providers via an interactive TUI (right-click) |
| **Self-Updating** | One command installs and keeps the module up to date |
| **Lightweight** | Python and Bash backend, native QML UI on Quickshell; no Node or NPM needed on your desktop |

## Supported Providers

| Provider | Data Source | Tracks |
|---|---|---|
| Antigravity | agy CLI (PTY) | Gemini and Claude/GPT rolling + weekly usage |
| Claude | OpenCode session tokens | Usage metrics |
| Codex | .codex/auth.json API | 5-hour and weekly usage limits |
| Copilot | GitHub Copilot token | Chat and completions usage |
| Kiro | Session cookie scraping | Usage percentage + reset timer |
| OpenCode | OpenCode Go binary | Rolling, weekly, and monthly usage |
| Z.AI | Bearer token from config | Rolling, weekly, and monthly usage |
| Command Code | Command Code local auth | Monthly spend and remaining credit |

See the [Providers & Authentication Guide](packages/lib/PROVIDERS.md) for setup details.

## ⚠️ Upgrading from v0.4.x (omarchy-ai-status)?
The project has been renamed to **AI Status**. When you run the install script below, your existing configurations will be migrated automatically. However, **you must update your Waybar config** to use the new `ai-status` command instead of `waybar-ai-status`.

## Quick Start

```bash
curl -fsSL https://ai-status.gelzin.com/install | bash
```

The installer detects your active bar and walks you through a short setup. Choose how the module looks (provider logo, plan, percentage) and let it configure **Waybar or Omarchy Quickshell**. It configures only the selected bar. Run the same command again to update; existing preferences are preserved unless you change them.

To choose explicitly, pass `--bar waybar` or `--bar quickshell`. Existing `--configure-waybar` flags continue to select Waybar. Waybar setup keeps a backup you can restore with `ai-status revert`.

### Omarchy Quickshell plugin

On the new Omarchy desktop, you can also install directly:

```bash
omarchy plugin add https://github.com/gelzinn/ai-status.git --enable
```

The plugin includes its Python backend, so a separate CLI installation is unnecessary. It uses the same provider credentials, preferences, and cache as Waybar. Left-click opens a native details panel with **Refresh** and **Configure** buttons; right-click opens the configuration TUI, scroll switches providers, and middle-click cycles metrics. Escape closes the panel.

```bash
omarchy plugin update io.github.gelzinn.ai-status
omarchy plugin disable io.github.gelzinn.ai-status
omarchy plugin remove io.github.gelzinn.ai-status
```

See the [installation guide](packages/lib/INSTALL.md) for dependencies, placement, and development validation. The Waybar instructions below apply when you opt out of its automatic setup.

### Manual Waybar setup

Add the module definition to `~/.config/waybar/config.jsonc`:

```jsonc
"custom/ai-status": {
    "exec": "~/.local/bin/ai-status daemon",
    "restart-interval": 1,
    "return-type": "json",
    "format": "{}",
    "tooltip": true,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric"
}
```

Then reference it in whichever bar section you use — a module that's defined but not listed in a `modules-*` array **won't render**:

```jsonc
{
    // ...
    "modules-right": [
        "custom/ai-status",
        "clock",
        "tray"
    ]
    // ...
}
```

**Want the provider's logo too?** Install with `--icon-mode logo` (or add it by hand — see [INSTALL.md](packages/lib/INSTALL.md)). It adds an `image#ai-status` module next to the text that shows the same tooltip on hover; just remember to list `"image#ai-status"` in `modules-right` alongside `"custom/ai-status"`.

The status bar shows the usage percentage of the active provider. Scroll up/down to switch providers, middle-click to cycle through the active provider's limits (rolling, weekly, monthly — including per-model ones, like Claude's Fable weekly). Right-click opens the provider configuration TUI -- toggle providers on or off and reorder them. Hover to see all providers with full details (the active one is marked with →).

## How It Works

A Python daemon runs persistently in the background, fetching usage data from all enabled providers in parallel every 5 minutes. Each provider has a `query.sh` (raw data fetching) and a `parse.py` (structured formatting), making it straightforward to add new providers.

By default the daemon outputs Waybar's `return-type: json` format and Pango tooltip. `ai-status daemon --format quickshell` emits structured JSON snapshots for the Omarchy plugin. One shared QML model runs a single Python daemon across all monitors inside the existing Omarchy shell; it never starts another Quickshell instance.

## Repository Structure

| Path | Purpose |
|---|---|
| `packages/lib/src/bin/ai-status` | CLI entry point |
| `packages/lib/src/core/` | Shared daemon, queries, state, and frontend output |
| `packages/lib/src/providers/<name>/` | Per-provider query and parse scripts |
| `packages/lib/quickshell/` | Native Omarchy bar widget, panel, and shared model |
| `manifest.json` | Omarchy plugin contract |
| `packages/lib/install.sh` | Installer and updater for both bars |
| `packages/lib/check.sh` | Dependencies for the selected bar |

## Security

This repository does **not** ship with any API keys or session tokens. Each provider script reads credentials from your existing local authentication files -- OpenCode tokens, `.codex/auth.json`, Copilot OAuth sessions, and similar.
