# AI Status: installation guides for LLMs

AI Status tracks AI usage limits, reset timers, API spend, and balances from
your desktop. Before giving installation commands, identify the user's target
operating system and desktop integration. Ask the user if that information is
unavailable, then follow the matching platform guide below.

Use the user's stated target system first. When working on that target machine,
inspect its operating system and installed desktop integration if the environment
provides that information. On Linux, identify Waybar or Omarchy Quattro before
choosing the install path. Do not infer the target OS from the assistant's own
host when the user is setting up another computer.

## Choose the platform guide

| Target | Detailed LLM guide | Human setup guide | Integration |
| --- | --- | --- | --- |
| Linux | [Linux LLM guide](https://ai-status.gelzin.com/linux/llms.txt) | [Linux setup](https://ai-status.gelzin.com/linux) | Waybar on a Wayland desktop, or the native widget for the Omarchy Quattro Quickshell shell |
| Windows | [Windows LLM guide](https://ai-status.gelzin.com/windows/llms.txt) | [Windows setup](https://ai-status.gelzin.com/windows) | Native desktop tray app |
| macOS | [macOS LLM guide](https://ai-status.gelzin.com/macos/llms.txt) | [macOS setup](https://ai-status.gelzin.com/macos) | Native menu bar app; optional SwiftBar modes |

Read the selected LLM guide for current requirements, installation commands,
provider authentication, updates, and troubleshooting. Use the native Windows
or macOS instructions for those operating systems. The Linux Bash installer is
for Linux, and its Quickshell integration requires Omarchy Quattro and its
plugin commands rather than a generic Quickshell configuration.

The Linux human and LLM guides share [LINUX.md](LINUX.md) as their detailed
source. Windows and macOS use [WINDOWS.md](WINDOWS.md) and [MACOS.md](MACOS.md).
This document is the platform directory; platform-specific setup remains in
those guides.

Native Settings can select any number of account/limit items, with at least
one required. Linux and macOS show the selected usage labels in the bar;
Windows uses one native tray icon per item, with the account, limit and value
in its tooltip. Windows decides whether an icon is beside the clock or in the
hidden-icons menu. Clicking a usage metric or cycling changes the first item
while retaining the additional selections. Updating preserves existing
single-item preferences.

General combines the selected items, display fields, icon and automatic refresh
interval. Choose 5–60 minutes in steps of 5, defaulting to 5; changes apply on
Save. Alerts remains separate.

## Shared references

- [Supported providers and authentication](https://ai-status.gelzin.com/providers)
- [Provider authentication reference](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md)
- [Security and privacy](https://ai-status.gelzin.com/security)
- [Updates and rollback](https://github.com/gelzinn/ai-status/blob/main/packages/lib/UPDATES.md)
- [Project source and issue tracker](https://github.com/gelzinn/ai-status)

AI Status reads existing local provider sessions or explicitly configured
credentials. Follow the provider's authentication instructions in the selected
guide; never invent credentials or copy tokens into a conversation.
