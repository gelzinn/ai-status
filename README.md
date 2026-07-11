# AI Status

Monitor AI provider usage limits in your Waybar — across Claude, Copilot, Codex, Z.AI, Kiro, Antigravity, and OpenCode in real time.

<img width="348" height="954" alt="Screenshot" src="https://github.com/user-attachments/assets/dcba0b97-d462-452e-b1b6-000cc445b803" />

## Features

| Feature | Description |
|---|---|
| **Multi-Provider** | Tracks API usage limits across seven AI services simultaneously |
| **Live Updates** | Auto-refreshes every 5 minutes with animated loading states |
| **Tooltip Detail** | Per-provider breakdown with progress bars, percentages, and reset timers |
| **Configurable** | Enable, disable, or reorder providers via an interactive TUI (right-click) |
| **Self-Updating** | One command installs and keeps the module up to date |
| **Zero Dependencies** | Pure Python and Bash -- no NPM, no Node, no system-level packages |

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

See the [Providers & Authentication Guide](PROVIDERS.md) for setup details.

## ⚠️ Upgrading from v0.4.x (omarchy-ai-status)?
The project has been renamed to **AI Status**. When you run the install script below, your existing configurations will be migrated automatically. However, **you must update your Waybar config** to use the new `ai-status` command instead of `waybar-ai-status`.

## Quick Start

```bash
curl -fsSL https://ai-status.gelzin.com/install | bash
```

The installer walks you through a short setup — choose how the module looks (provider logo, plan, percentage) and let it **configure Waybar for you**. It backs up your existing config first, so if anything looks off you can undo everything with `ai-status revert`. Run the same command again anytime to update.

**If you let the installer configure Waybar, you're all set** — jump to [how it works](#how-it-works). The steps below are only needed if you opted out of automatic setup.

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

The daemon outputs JSON for Waybar's `return-type: json` custom module format, with the current status icon and a detailed tooltip showing progress bars and reset timers.

## Repository Structure

| Path | Purpose |
|---|---|
| `src/bin/ai-status` | CLI entry point |
| `src/core/` | Core logic: daemon, fetch, render, state, config management |
| `src/providers/<name>/` | Per-provider query and parse scripts |
| `install.sh` | Self-updating install script |
| `check.sh` | System dependency check |

## Security

This repository does **not** ship with any API keys or session tokens. Each provider script reads credentials from your existing local authentication files -- OpenCode tokens, `.codex/auth.json`, Copilot OAuth sessions, and similar.
