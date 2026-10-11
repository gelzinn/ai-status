# Changelog

## [0.11.0](https://github.com/gelzinn/ai-status/compare/v0.10.0...v0.11.0) (2026-10-11)


### Features

* **macos:** add a native menu bar app with the shared desktop usage, reset credits, settings and about pages ([54c7755](https://github.com/gelzinn/ai-status/commit/54c775597384c913955f80ba6d6d0ef0eda8d32e))
* **providers:** track API spend and quotas across 29 providers with unlimited named account connections ([765a8f1](https://github.com/gelzinn/ai-status/commit/765a8f1a9576c4fe7ed213ef8b3df752e8e32482))


### Bug Fixes

* **desktop:** keep the selected account when unavailable accounts are hidden ([54c7755](https://github.com/gelzinn/ai-status/commit/54c775597384c913955f80ba6d6d0ef0eda8d32e))
* **macos:** read Claude Code Keychain credentials and preserve existing installs and preferences during updates ([54c7755](https://github.com/gelzinn/ai-status/commit/54c775597384c913955f80ba6d6d0ef0eda8d32e))
* **openrouter:** show available account balance directly below its credit usage bar ([765a8f1](https://github.com/gelzinn/ai-status/commit/765a8f1a9576c4fe7ed213ef8b3df752e8e32482))
* **usage:** align usage content with provider names and keep balance values beside their labels ([765a8f1](https://github.com/gelzinn/ai-status/commit/765a8f1a9576c4fe7ed213ef8b3df752e8e32482))
* **usage:** display balances without invented percentages and isolate account credentials and cached results ([765a8f1](https://github.com/gelzinn/ai-status/commit/765a8f1a9576c4fe7ed213ef8b3df752e8e32482))


### Performance Improvements

* **usage:** reuse fresh usage and persist service rate-limit cooldowns across refreshes ([765a8f1](https://github.com/gelzinn/ai-status/commit/765a8f1a9576c4fe7ed213ef8b3df752e8e32482))

## [0.10.0](https://github.com/gelzinn/ai-status/compare/v0.9.0...v0.10.0) (2026-10-10)


### Features

* **desktop:** access refresh and settings directly and find project details and a quick guide in About ([3fefe0e](https://github.com/gelzinn/ai-status/commit/3fefe0ee5085f2d29c3122f92adc8e8bc8d9083f))
* **install:** choose stable releases and restore the previous local version with --rollback ([1cf7f68](https://github.com/gelzinn/ai-status/commit/1cf7f68b2317237fe8d25455325f71433ddfb6aa))
* **install:** download verified release packages without requiring git ([1cf7f68](https://github.com/gelzinn/ai-status/commit/1cf7f68b2317237fe8d25455325f71433ddfb6aa))
* **quickshell:** add native Omarchy usage and settings panels while keeping Waybar support ([b365c2d](https://github.com/gelzinn/ai-status/commit/b365c2d93bb6441a58dacf6c65904d691d6403cd))
* **quickshell:** choose provider limits and bar icons from floating lists with matching right-aligned chevrons and official provider names ([3fefe0e](https://github.com/gelzinn/ai-status/commit/3fefe0ee5085f2d29c3122f92adc8e8bc8d9083f))
* **windows:** inspect Claude and Codex reset credits in provider details ([2903dd0](https://github.com/gelzinn/ai-status/commit/2903dd0c34d98a784d755da018911b61392c7ec0))
* **windows:** monitor AI usage from the Windows system tray ([2903dd0](https://github.com/gelzinn/ai-status/commit/2903dd0c34d98a784d755da018911b61392c7ec0))


### Bug Fixes

* **desktop:** place Back before the title in settings and resets, round reset tables and animate only the refresh icon while updating ([3fefe0e](https://github.com/gelzinn/ai-status/commit/3fefe0ee5085f2d29c3122f92adc8e8bc8d9083f))
* **install:** restore your installation and settings if activation or setup fails ([1cf7f68](https://github.com/gelzinn/ai-status/commit/1cf7f68b2317237fe8d25455325f71433ddfb6aa))
* **quickshell:** hide unavailable providers and match Windows loading animations and reset-credit details ([b365c2d](https://github.com/gelzinn/ai-status/commit/b365c2d93bb6441a58dacf6c65904d691d6403cd))
* **quickshell:** smooth refresh and settings icons at normal and HiDPI display scales ([b365c2d](https://github.com/gelzinn/ai-status/commit/b365c2d93bb6441a58dacf6c65904d691d6403cd))
* **settings:** keep Windows and Quickshell settings open after saving and show provider logos in the selected limit and every option ([3fefe0e](https://github.com/gelzinn/ai-status/commit/3fefe0ee5085f2d29c3122f92adc8e8bc8d9083f))
* **settings:** preserve your selected provider, metric, and display preferences during updates ([1cf7f68](https://github.com/gelzinn/ai-status/commit/1cf7f68b2317237fe8d25455325f71433ddfb6aa))


### Performance Improvements

* **windows:** reduce the installer size to under 17 MiB ([2903dd0](https://github.com/gelzinn/ai-status/commit/2903dd0c34d98a784d755da018911b61392c7ec0))
