<div align="center">
  <img src="packages/lib/assets/app.png" alt="AI Status logo" width="72" height="72" />
  <h1>AI Status</h1>
  <p><strong>Your AI usage, at a glance.</strong></p>
  <p>Track usage limits, reset timers and available reset credits from your desktop.<br />Native panels for Omarchy Quickshell, Windows and macOS, plus Waybar integration.</p>
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
| **macOS 13+** | Native menu bar app, usage panel and settings | [Run the macOS installer](#macos-13) |

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

### macOS 13+

```bash
curl -fsSL https://ai-status.gelzin.com/install/macos | bash
```

The installer builds a native SwiftUI/AppKit menu bar app with the same usage, Settings, reset-credit and About page structure as Windows and Quickshell. Click the menu bar item to open the panel, choose a provider or limit, and use the header's **Refresh** and **Settings** controls.

Requires macOS 13+, Python 3.10+ and Xcode Command Line Tools (`xcode-select --install`). The native integration does not require SwiftBar. Re-run to update while keeping your preferences. Existing SwiftBar users can select `--mode stream` or `--mode periodic` instead.

[macOS installation, branch testing and SwiftBar options →](packages/lib/MACOS.md)

### Windows 10/11

1. Open the [latest release](https://github.com/gelzinn/ai-status/releases/latest).
2. Download `ai-status-<version>-windows-x64-setup.exe` and run it as your normal user, or extract the portable `ai-status-<version>-windows-x64.zip`.
3. Launch **AI Status** from the Start menu, or open `ai-status.exe` in the extracted portable folder. Click the tray logo to see usage.

The packaged app includes its runtime. Installation needs no administrator access, Python setup or WSL. Provider apps and authenticated sessions remain separate prerequisites. Enable **Start when I sign in to Windows** in Settings if you want it to launch at sign-in.

[Windows installation, updates and provider compatibility →](packages/lib/WINDOWS.md)

## What you get

- **29 providers in one view.** Track subscription limits, API costs and prepaid balances, including separate rolling, weekly, monthly and per-model windows.
- **Choose what stays visible.** Pick the active provider and limit, then choose the provider name, plan, limit name, percentage and icon shown in the bar. The Windows tray and macOS menu bar follow your selection.
- **Multiple accounts.** Add as many connections as you need for each provider, with independent labels, credentials, caches and selected metrics. Manage connections with `ai-status accounts`; enable and reorder them in the desktop Settings.
- **Native settings.** Enable providers, reorder them and select limits inside the Omarchy, Windows and macOS panels. Windows also supports drag and drop; Waybar uses an interactive configuration TUI.
- **Useful reset details.** See reset countdowns and available Claude/Codex reset credits, with expiry dates, remaining time and time zones when reported. Redeem credits in the provider's own app.
- **Refresh when you need it.** Usage updates every five minutes, with manual refresh and loading feedback. Usable cached data remains visible when a refresh fails.
- **A desktop runtime.** The Omarchy widget runs inside the existing shell with one backend across monitors. Windows uses Qt widgets with a bundled runtime. macOS uses SwiftUI/AppKit and the same Python backend. Desktop installation requires no Node or NPM.

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
| <img src="packages/lib/assets/providers/claude.png" width="18" height="18" alt="" /> **Claude** | Session (5h) and weekly usage, including per-model weekly limits | Claude Code OAuth (OpenCode fallback) |
| <img src="packages/lib/assets/providers/codex.png" width="18" height="18" alt="" /> **Codex** | 5-hour and weekly limits (a single monthly window on free plans) | ~/.codex/auth.json |
| <img src="packages/lib/assets/providers/opencode.png" width="18" height="18" alt="" /> **OpenCode** | Rolling, weekly, and monthly usage | OpenCode auth + workspace config |
| <img src="packages/lib/assets/providers/antigravity.png" width="18" height="18" alt="" /> **Antigravity** | Weekly and 5-hour limits per model (Gemini and Claude/GPT) | agy CLI session |
| <img src="packages/lib/assets/providers/copilot.png" width="18" height="18" alt="" /> **Copilot** | Chat and completions usage | OpenCode auth (Copilot) |
| <img src="packages/lib/assets/providers/zai.png" width="18" height="18" alt="" /> **Z.AI** | Rolling, weekly, and monthly usage | OpenCode auth (Z.AI) |
| <img src="packages/lib/assets/providers/kiro.png" width="18" height="18" alt="" /> **Kiro** | Usage percentage and reset timer | kiro-cli session |
| <img src="packages/lib/assets/providers/commandcode.png" width="18" height="18" alt="" /> **Command Code** | 5-hour and weekly spend limits; monthly spend and available credits | ~/.commandcode/auth.json (cmd login) |
| <img src="packages/lib/assets/providers/anthropic-api.png" width="18" height="18" alt="" /> **Anthropic API** | Monthly organization API spend | ANTHROPIC_ADMIN_KEY (organization Admin key) |
| <img src="packages/lib/assets/providers/openai-api.png" width="18" height="18" alt="" /> **OpenAI API** | Monthly organization API spend | OPENAI_ADMIN_KEY (organization Admin key) |
| <img src="packages/lib/assets/providers/google-cloud.png" width="18" height="18" alt="" /> **Google Cloud** | Project quotas; optional billing-export monthly cost | gcloud or GOOGLE_CLOUD_ACCESS_TOKEN; project_id option |
| <img src="packages/lib/assets/providers/openrouter.png" width="18" height="18" alt="" /> **OpenRouter** | Key usage and limits; account spend / total credits and remaining balance | OPENROUTER_API_KEY; OPENROUTER_MANAGEMENT_KEY for account credits |
| <img src="packages/lib/assets/providers/deepseek.png" width="18" height="18" alt="" /> **DeepSeek** | Available prepaid balance | DEEPSEEK_API_KEY |
| <img src="packages/lib/assets/providers/deepinfra.png" width="18" height="18" alt="" /> **DeepInfra** | Prepaid balance and current-month spend | DEEPINFRA_API_KEY |
| <img src="packages/lib/assets/providers/kimi.png" width="18" height="18" alt="" /> **Kimi** | Coding subscription quota and rolling limits | KIMI_API_KEY or Kimi CLI login |
| <img src="packages/lib/assets/providers/minimax.png" width="18" height="18" alt="" /> **MiniMax** | Token Plan quota windows | MINIMAX_API_KEY (Token Plan key) |
| <img src="packages/lib/assets/providers/kilo.png" width="18" height="18" alt="" /> **Kilo** | Personal or organization credit balance | KILO_API_KEY; optional organization_id |
| <img src="packages/lib/assets/providers/lyceum.png" width="18" height="18" alt="" /> **Lyceum** | Available USD balance and reported spend | LYCEUM_API_KEY |
| <img src="packages/lib/assets/providers/novita.png" width="18" height="18" alt="" /> **Novita** | Available prepaid balance | NOVITA_API_KEY |
| <img src="packages/lib/assets/providers/moonshot.png" width="18" height="18" alt="" /> **Moonshot** | Available USD or CNY balance | MOONSHOT_API_KEY; region option |
| <img src="packages/lib/assets/providers/grok.png" width="18" height="18" alt="" /> **Grok API (xAI)** | Team prepaid balance | XAI_MANAGEMENT_KEY; team_id for organization-scoped keys |
| <img src="packages/lib/assets/providers/supergrok.png" width="18" height="18" alt="" /> **SuperGrok** | Subscription credits and product usage | Grok Build login or SUPERGROK_ACCESS_TOKEN |
| <img src="packages/lib/assets/providers/grok-bot.png" width="18" height="18" alt="" /> **Grok Bot** | Weekly included usage | Grok Bot desktop login or GROK_BOT_ACCESS_TOKEN |
| <img src="packages/lib/assets/providers/cursor.png" width="18" height="18" alt="" /> **Cursor** | Included usage pools and on-demand spend | Cursor IDE/agent login or CURSOR_ACCESS_TOKEN |
| <img src="packages/lib/assets/providers/nous.png" width="18" height="18" alt="" /> **Nous Research** | Subscription and top-up credits | NOUS_ACCESS_TOKEN or existing OAuth credentials |
| <img src="packages/lib/assets/providers/ollama.png" width="18" height="18" alt="" /> **Ollama Cloud** | Cloud session/weekly or monthly quota | OLLAMA_API_KEY (cloud key) |
| <img src="packages/lib/assets/providers/orcarouter.png" width="18" height="18" alt="" /> **OrcaRouter** | Credit limit, spend and remaining balance | ORCAROUTER_API_KEY |
| <img src="packages/lib/assets/providers/modelstudio.png" width="18" height="18" alt="" /> **Alibaba Model Studio** | Token Plan rolling and weekly quota | bl auth login --console |
| <img src="packages/lib/assets/providers/devin.png" width="18" height="18" alt="" /> **Devin** | Daily and weekly CLI quota; optional overage balance | Official Devin CLI credentials |

Available metrics depend on the account, plan and upstream API. Providers without usable data stay available in Settings. See the [authentication guide](packages/lib/PROVIDERS.md) and [Windows compatibility notes](packages/lib/WINDOWS.md#authentication-and-provider-compatibility) for setup details, including Kiro on Windows 10.

## Documentation

| Guide | What you will find |
| --- | --- |
| [Install and configure](packages/lib/INSTALL.md) | Dependencies, bar placement, display options and manual setup |
| [Windows](packages/lib/WINDOWS.md) | Installer, portable app, sign-in option, compatibility and local builds |
| [macOS](packages/lib/MACOS.md) | Native menu bar app, local builds, sign-in startup and optional SwiftBar modes |
| [Providers and authentication](packages/lib/PROVIDERS.md) | Credential sources, account setup and troubleshooting |
| [Updates and rollback](packages/lib/UPDATES.md) | Stable releases, version selection, checksums and recovery |
| [Changelog](packages/lib/CHANGELOG.md) | Changes in each published release |
| [Releases](https://github.com/gelzinn/ai-status/releases) | Linux packages, Windows downloads and release notes |

## How it works

A shared Python backend queries enabled connections with bounded parallel workers every five minutes. Each provider has its own collector and parser. Waybar consumes JSON with a Pango tooltip; the Omarchy plugin consumes structured snapshots through a shared QML model. The Windows adapter renders the same provider data in a native Qt tray panel; macOS uses a SwiftUI/AppKit menu bar panel backed by the shared JSON daemon.

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
| `packages/lib/macos/` | Native macOS menu bar app and local build |
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
