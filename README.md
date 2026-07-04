# Omarchy AI Status

**Monitor AI provider usage limits in your Waybar -- across Claude, Copilot, Codex, Z.AI, Kiro, Antigravity, and OpenCode in real time.**

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
| Codex | .codex/auth.json API | Usage percentage + reset timer |
| Copilot | GitHub Copilot token | Chat and completions usage |
| Kiro | Session cookie scraping | Usage percentage + reset timer |
| OpenCode | OpenCode Go binary | Rolling, weekly, and monthly usage |
| Z.AI | Bearer token from config | Rolling, weekly, and monthly usage |

See the [Providers & Authentication Guide](PROVIDERS.md) for setup details.

## Quick Start

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gelzinn/omarchy-ai-status/main/install.sh)
```

This single command installs, configures symlinks, and restarts Waybar. Run it again to update.

Then add the module to your Waybar config:

```jsonc
"custom/ai-status": {
    "format": "{}",
    "return-type": "json",
    "exec": "~/.local/bin/waybar-ai-status daemon",
    "on-click": "~/.local/bin/waybar-ai-status refresh",
    "on-click-right": "~/.local/bin/waybar-ai-status config",
    "on-scroll-up": "~/.local/bin/waybar-ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/waybar-ai-status scroll-down",
    "on-click-middle": "~/.local/bin/waybar-ai-status cycle-metric",
    "tooltip": true
}
```

The status bar shows the usage percentage of the active provider. Scroll up/down to switch providers, middle-click to cycle metric types (rolling → weekly → monthly). Right-click opens the provider configuration TUI -- toggle providers on or off and reorder them. Hover to see all providers with full details (the active one is marked with →).

## How It Works

A Python daemon runs persistently in the background, fetching usage data from all enabled providers in parallel every 5 minutes. Each provider has a `query.sh` (raw data fetching) and a `parse.py` (structured formatting), making it straightforward to add new providers.

The daemon outputs JSON for Waybar's `return-type: json` custom module format, with the current status icon and a detailed tooltip showing progress bars and reset timers.

## Repository Structure

| Path | Purpose |
|---|---|
| `src/bin/waybar-ai-status` | CLI entry point |
| `src/core/` | Core logic: daemon, fetch, render, state, config management |
| `src/providers/<name>/` | Per-provider query and parse scripts |
| `install.sh` | Self-updating install script |
| `check.sh` | System dependency check |

## Security

This repository does **not** ship with any API keys or session tokens. Each provider script reads credentials from your existing local authentication files -- OpenCode tokens, `.codex/auth.json`, Copilot OAuth sessions, and similar.
