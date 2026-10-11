## Grok Bot

Tracks weekly included usage.

Authentication: **Grok Bot desktop login or GROK_BOT_ACCESS_TOKEN**. Enable `grok-bot` in Settings after configuring credentials. New integrations are opt-in.

Each connection can have a separate label, credential source and provider options. Add accounts with `ai-status accounts add --file connection.json`; inspect `ai-status accounts list`. See the [complete authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

Only percentages with a reported limit (or an explicitly configured budget) display a progress bar. Balance and cost metrics display their amount and currency. Upstream availability depends on your account and permissions.

Native session reading depends on the desktop app's storage format: macOS uses Keychain, Linux uses Secret Service when available, and Windows uses the current user's DPAPI-protected key from the adjacent `Local State` file. The reader accepts Chromium `v10`/`v11` tokens; other formats need `GROK_BOT_ACCESS_TOKEN`.
