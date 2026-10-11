# Changelog

## [0.12.1](https://github.com/gelzinn/ai-status/compare/v0.12.0...v0.12.1) (2026-10-11)


### Bug Fixes

* **web:** keep platform setup guides focused on stable installation ([24b875c](https://github.com/gelzinn/ai-status/commit/24b875c0960644b44f3aaf2f727d6aa12866b89d))
* **web:** keep Windows downloads on stable releases when the release lookup fails ([24b875c](https://github.com/gelzinn/ai-status/commit/24b875c0960644b44f3aaf2f727d6aa12866b89d))
* **web:** match home installation card spacing without reserving height ([24b875c](https://github.com/gelzinn/ai-status/commit/24b875c0960644b44f3aaf2f727d6aa12866b89d))
* **web:** preserve interactive preview state when switching operating systems ([24b875c](https://github.com/gelzinn/ai-status/commit/24b875c0960644b44f3aaf2f727d6aa12866b89d))
* **web:** show a macOS desktop scene in the interactive preview ([24b875c](https://github.com/gelzinn/ai-status/commit/24b875c0960644b44f3aaf2f727d6aa12866b89d))

## [0.12.0](https://github.com/gelzinn/ai-status/compare/v0.11.0...v0.12.0) (2026-10-11)


### Features

* **cli:** make commands discoverable and show detected default provider connections alongside saved accounts ([a75ade5](https://github.com/gelzinn/ai-status/commit/a75ade501bce2c95856fdc5e2cdd956b6b5fd149))
* **web:** add Linux setup and route LLM installation guides by operating system ([6265a58](https://github.com/gelzinn/ai-status/commit/6265a58d1d9c3b4484d2f0c0302cf7320d0ad1d4))
* **web:** group the provider catalog and publish detailed setup guides for 21 integrations ([6265a58](https://github.com/gelzinn/ai-status/commit/6265a58d1d9c3b4484d2f0c0302cf7320d0ad1d4))


### Bug Fixes

* **cli:** preserve command error codes on Windows and report unavailable terminal configuration ([a75ade5](https://github.com/gelzinn/ai-status/commit/a75ade501bce2c95856fdc5e2cdd956b6b5fd149))
* **web:** make Kilo and Lyceum logos readable across website themes ([6265a58](https://github.com/gelzinn/ai-status/commit/6265a58d1d9c3b4484d2f0c0302cf7320d0ad1d4))

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
