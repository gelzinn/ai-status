# Installing AI Status

AI Status tracks provider usage, reset timers, API costs and balances from your
desktop. Start with the installation guide for your operating system. Each
guide covers its supported environment, requirements, stable installation,
provider setup and updates.

## Choose your operating system

| System | Supported environment | Installation guide |
| --- | --- | --- |
| Linux | Wayland with Waybar, or the Omarchy Quattro Quickshell shell | [Linux installation](LINUX.md) |
| macOS | macOS 13 or newer | [macOS installation](MACOS.md) |
| Windows | Windows 10 version 1809+ or Windows 11, x64 | [Windows installation](WINDOWS.md) |

Follow the selected guide for its installation commands and prerequisites.
Linux supports Waybar and the Omarchy Quattro widget. macOS provides a native
menu bar app with optional SwiftBar integration. Windows provides an installer
and a portable tray app with its runtime included.

## Before installing

Check the requirements in your system's guide, then sign in through the apps or
CLIs for the providers you want to monitor. API providers may require keys with
specific permissions. AI Status reads those existing sessions or your configured
credential sources; it does not sign in to providers for you.

See [Providers and authentication](PROVIDERS.md) for supported providers,
credential sources and additional accounts. Each connection can keep its own
label and credentials.

## After installing

Open your system's usage panel or tooltip, enable the configured providers in
Settings, and select the connection and metric to display. Use your platform
guide for its controls, command-line tools, startup preferences and update steps.
Install updates from published stable releases using that guide's installer or
download instructions.

## Guides for LLMs

The [LLM guide directory](LLMS.md) explains how to identify the target operating
system and choose its instructions. Detailed guides are also available as plain
text:

- [Linux LLM guide](https://ai-status.gelzin.com/linux/llms.txt)
- [macOS LLM guide](https://ai-status.gelzin.com/macos/llms.txt)
- [Windows LLM guide](https://ai-status.gelzin.com/windows/llms.txt)
