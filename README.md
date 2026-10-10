<div align="center">
  <img src="packages/lib/assets/app.png" alt="AI Status logo" width="72" height="72" />
  <h1>AI Status</h1>
  <p><strong>Your AI usage, at a glance.</strong></p>
  <p>Track usage limits, reset timers and available reset credits from your desktop.<br />Native panels for Omarchy Quickshell and Windows, plus Waybar integration.</p>
  <p>
    <a href="https://github.com/gelzinn/ai-status/releases/latest"><img src="https://img.shields.io/github/v/release/gelzinn/ai-status?style=flat-square&amp;label=release" alt="Latest stable release" /></a>
    <a href="https://github.com/gelzinn/ai-status/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/gelzinn/ai-status/ci.yml?branch=main&amp;style=flat-square&amp;label=checks" alt="CI status on main" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="MIT license" /></a>
  </p>
  <p>
    <a href="https://ai-status.gelzin.com">Website &amp; interactive preview</a> ·
    <a href="#quick-start">Install</a> ·
    <a href="#supported-providers">Providers</a> ·
    <a href="#documentation">Documentation</a>
  </p>
</div>

<table>
  <tr>
    <th align="left">Omarchy Quickshell</th>
    <th align="left">Windows tray</th>
  </tr>
  <tr>
    <td valign="top"><img src="docs/screenshots/omarchy-usage.png" alt="Omarchy panel with Codex and Claude usage bars, reset timers and available reset credits" width="360" /></td>
    <td valign="top"><img src="docs/screenshots/windows-usage.png" alt="Windows panel showing the same provider usage, refresh and settings controls" width="360" /></td>
  </tr>
</table>

*Example panels rendered with sample usage data. Omarchy follows your shell theme.*

## Quick start

| Desktop | Integration | Setup |
| --- | --- | --- |
| **Omarchy Quickshell** | Native bar widget, usage panel and settings | [Install the plugin](#omarchy-quickshell) |
| **Linux with Waybar** | Status module with a detailed usage tooltip | [Run the installer](#linux-with-waybar) |
| **Windows 10/11 x64** | Native tray app, usage panel and settings | [Download the installer or portable ZIP](#windows-1011) |

Sign in to the providers you want to monitor using their apps or CLIs, then follow the setup for your desktop. See [provider authentication](packages/lib/PROVIDERS.md) for the credentials and additional setup each integration needs.

### Omarchy Quickshell

On the Omarchy Quattro shell:

```bash
omarchy plugin add https://github.com/gelzinn/ai-status.git --enable
```

The plugin includes its Python backend. Click the widget for usage; right-click or use the settings icon to configure providers, limits and the bar appearance. The panel shares your existing AI Status preferences and cache with Waybar.

Update the plugin with:

```bash
omarchy plugin update io.github.gelzinn.ai-status
```

[Dependencies, placement and configuration →](packages/lib/INSTALL.md#omarchy-quickshell-plugin)

### Linux with Waybar

```bash
curl -fsSL https://ai-status.gelzin.com/install | bash -s -- --bar waybar
```

The installer walks you through provider selection and appearance, then configures Waybar. Hover for details, scroll to switch providers, middle-click to switch limits and right-click for configuration.

Run the same command to update to the latest stable release. Existing preferences are preserved, and the installer keeps a backup of your Waybar configuration. The installer also supports Omarchy; omit `--bar waybar` to detect your active bar automatically.

[Installation options →](packages/lib/INSTALL.md) · [Updates and rollback →](packages/lib/UPDATES.md)

<details>
<summary>Manual Waybar configuration</summary>

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

</details>

### Windows 10/11

1. Open the [latest release](https://github.com/gelzinn/ai-status/releases/latest).
2. Download `ai-status-<version>-windows-x64-setup.exe` and run it as your normal user, or extract the portable `ai-status-<version>-windows-x64.zip`.
3. Launch **AI Status** from the Start menu, or open `ai-status.exe` in the extracted portable folder. Click the tray logo to see usage.

The packaged app includes its runtime. Installation needs no administrator access, Python setup or WSL. Provider apps and authenticated sessions remain separate prerequisites. Enable **Start when I sign in to Windows** in Settings if you want it to launch at sign-in.

[Windows installation, updates and provider compatibility →](packages/lib/WINDOWS.md)

## What you get

- **29 providers in one view.** Track subscription limits, API costs and prepaid balances, including separate rolling, weekly, monthly and per-model windows.
- **Choose what stays visible.** Pick the active provider and limit, then choose the provider name, plan, limit name, percentage and icon shown in the bar. On Windows, the tray logo and tooltip follow your selection.
- **Multiple accounts.** Add as many connections as you need for each provider, with independent labels, credentials, caches and selected metrics. Manage connections with `ai-status accounts`; enable and reorder them in the desktop Settings.
- **Native settings.** Enable providers, reorder them and select limits inside the Omarchy and Windows panels. Windows also supports drag and drop; Waybar uses an interactive configuration TUI.
- **Useful reset details.** See reset countdowns and available Claude/Codex reset credits, with expiry dates, remaining time and time zones when reported. Redeem credits in the provider's own app.
- **Refresh when you need it.** Usage updates every five minutes, with manual refresh and loading feedback. Usable cached data remains visible when a refresh fails.
- **A desktop runtime.** The Omarchy widget runs inside the existing shell with one backend across monitors. Windows uses Qt widgets with a bundled runtime. Desktop installation requires no Node or NPM.

<details>
<summary>More views: settings, reset credits and Waybar</summary>

<table>
  <tr>
    <th align="left">Omarchy settings</th>
    <th align="left">Windows settings</th>
  </tr>
  <tr>
    <td valign="top"><img src="docs/screenshots/omarchy-settings.png" alt="Omarchy settings with provider logos, limit and icon selectors, display options and reorder arrows" width="360" /></td>
    <td valign="top"><img src="docs/screenshots/windows-settings.png" alt="Windows settings with the same options and a draggable provider list" width="360" /></td>
  </tr>
</table>

<img src="docs/screenshots/reset-credits.png" alt="Codex reset-credit table with three available resets, expiry dates and remaining time" width="360" />

Save applies preferences and keeps Settings open. Back sits before the panel title. **About AI Status** contains the project details, links and a short usage guide.

**Waybar usage tooltip**

<img src="docs/screenshots/waybar-tooltip.png" alt="Waybar tooltip showing per-provider usage percentages, progress bars and reset countdowns" width="320" />

</details>

## Supported providers

| Provider | Usage tracked | Credentials / source |
| --- | --- | --- |
| **Claude** | Session (5h) and weekly usage, including per-model weekly limits | Claude Code OAuth (OpenCode fallback) |
| **Codex** | 5-hour and weekly limits (a single monthly window on free plans) | ~/.codex/auth.json |
| **OpenCode** | Rolling, weekly, and monthly usage | OpenCode auth + workspace config |
| **Antigravity** | Weekly and 5-hour limits per model (Gemini and Claude/GPT) | agy CLI session |
| **Copilot** | Chat and completions usage | OpenCode auth (Copilot) |
| **Z.AI** | Rolling, weekly, and monthly usage | OpenCode auth (Z.AI) |
| **Kiro** | Usage percentage and reset timer | kiro-cli session |
| **Command Code** | 5-hour and weekly spend limits; monthly spend and available credits | ~/.commandcode/auth.json (cmd login) |
| **Anthropic API** | Monthly organization API spend | ANTHROPIC_ADMIN_KEY (organization Admin key) |
| **OpenAI API** | Monthly organization API spend | OPENAI_ADMIN_KEY (organization Admin key) |
| **Google Cloud** | Project quotas; optional billing-export monthly cost | gcloud or GOOGLE_CLOUD_ACCESS_TOKEN; project_id option |
| **OpenRouter** | Key usage, monthly spend, remaining limit and prepaid credits | OPENROUTER_API_KEY |
| **DeepSeek** | Available prepaid balance | DEEPSEEK_API_KEY |
| **DeepInfra** | Prepaid balance and current-month spend | DEEPINFRA_API_KEY |
| **Kimi** | Coding subscription quota and rolling limits | KIMI_API_KEY or Kimi CLI login |
| **MiniMax** | Token Plan quota windows | MINIMAX_API_KEY (Token Plan key) |
| **Kilo** | Personal or organization credit balance | KILO_API_KEY; optional organization_id |
| **Lyceum** | Available USD balance and reported spend | LYCEUM_API_KEY |
| **Novita** | Available prepaid balance | NOVITA_API_KEY |
| **Moonshot** | Available USD or CNY balance | MOONSHOT_API_KEY; region option |
| **Grok API (xAI)** | Team prepaid balance | XAI_MANAGEMENT_KEY; team_id for organization-scoped keys |
| **SuperGrok** | Subscription credits and product usage | Grok Build login or SUPERGROK_ACCESS_TOKEN |
| **Grok Bot** | Weekly included usage | Grok Bot desktop login or GROK_BOT_ACCESS_TOKEN |
| **Cursor** | Included usage pools and on-demand spend | Cursor IDE/agent login or CURSOR_ACCESS_TOKEN |
| **Nous Research** | Subscription and top-up credits | NOUS_ACCESS_TOKEN or existing OAuth credentials |
| **Ollama Cloud** | Cloud session/weekly or monthly quota | OLLAMA_API_KEY (cloud key) |
| **OrcaRouter** | Credit limit, spend and remaining balance | ORCAROUTER_API_KEY |
| **Alibaba Model Studio** | Token Plan rolling and weekly quota | bl auth login --console |
| **Devin** | Daily and weekly CLI quota; optional overage balance | Official Devin CLI credentials |

Available metrics depend on the account, plan and upstream API. Providers without usable data stay available in Settings. See the [authentication guide](packages/lib/PROVIDERS.md) and [Windows compatibility notes](packages/lib/WINDOWS.md#authentication-and-provider-compatibility) for setup details, including Kiro on Windows 10.

## Documentation

| Guide | What you will find |
| --- | --- |
| [Install and configure](packages/lib/INSTALL.md) | Dependencies, bar placement, display options and manual setup |
| [Windows](packages/lib/WINDOWS.md) | Installer, portable app, sign-in option, compatibility and local builds |
| [Providers and authentication](packages/lib/PROVIDERS.md) | Credential sources, account setup and troubleshooting |
| [Updates and rollback](packages/lib/UPDATES.md) | Stable releases, version selection, checksums and recovery |
| [Changelog](packages/lib/CHANGELOG.md) | Changes in each published release |
| [Releases](https://github.com/gelzinn/ai-status/releases) | Linux packages, Windows downloads and release notes |

## How it works

A shared Python backend queries enabled connections with bounded parallel workers every five minutes. Each provider has its own collector and parser. Waybar consumes JSON with a Pango tooltip; the Omarchy plugin consumes structured snapshots through a shared QML model. The Windows adapter renders the same provider data in a native Qt tray panel.

Credentials come from your local provider authentication stores or explicitly configured keys. AI Status does not ship credentials, perform provider sign-in or modify provider credential files. Authenticate through the provider's own app or CLI. [Read the security overview →](https://ai-status.gelzin.com/security)

<details>
<summary>Repository layout</summary>

| Path | Purpose |
| --- | --- |
| `packages/lib/src/bin/ai-status` | CLI entry point |
| `packages/lib/src/core/` | Shared queries, state, output and desktop adapter |
| `packages/lib/src/providers/` | Provider collectors and parsers |
| `packages/lib/quickshell/` | Native Omarchy widget, panels and shared model |
| `packages/lib/windows/` | Windows packaging and installer |
| `packages/shared/providers/` | Provider names, logos and metadata |
| `apps/web/` | Website, interactive preview and documentation |
| `manifest.json` | Omarchy plugin contract |

</details>

<details>
<summary>Upgrading from v0.4.x / omarchy-ai-status</summary>

The project is now **AI Status**. The installer migrates existing preferences. Update your Waybar configuration to use `ai-status` instead of `waybar-ai-status`. See the [update guide](packages/lib/UPDATES.md) for the current stable-release flow.

</details>

## Contributing

[Report a bug](https://github.com/gelzinn/ai-status/issues/new?template=bug_report.md), [suggest a feature](https://github.com/gelzinn/ai-status/issues/new?template=feature_request.md) or open a pull request. Provider integrations live in `packages/lib/src/providers/`; see the [provider architecture](packages/lib/PROVIDERS.md#provider-architecture) before adding a collector.

[MIT licensed](LICENSE) · Created by [gelzin.com](https://gelzin.com).
