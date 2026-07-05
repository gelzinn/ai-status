#!/bin/bash

# shellcheck source=./config.sh
source "$(dirname "$0")/config.sh"

echo "Checking system requirements for $PROJECT_NAME..."
echo ""

MISSING_DEPS=0
ERR_MSG=""

# OS Check
OS="$(uname -s)"
if [ "$OS" = "Linux" ]; then
    echo "OK: OS: Linux"
elif [ "$OS" = "Darwin" ]; then
    echo "OK: OS: macOS"
else
    ERR_MSG+="Unsupported OS: $OS (This module is currently designed for Linux and macOS)\n"
    MISSING_DEPS=1
fi

# Status Bar Check
if [ "$OS" = "Linux" ]; then
    if ! command -v waybar >/dev/null 2>&1; then
        ERR_MSG+="Missing Status Bar: 'waybar' was not found (Waybar is required on Linux)\n"
        MISSING_DEPS=1
    else
        echo "OK: Status Bar: Waybar"
    fi
elif [ "$OS" = "Darwin" ]; then
    echo "OK: Status Bar: SwiftBar / xbar (expected)"
fi

# Utilities Check
for cmd in python3 jq curl git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        ERR_MSG+="Missing command: $cmd\n"
        MISSING_DEPS=1
    else
        echo "OK: Found: $cmd"
    fi
done

echo ""

if [ $MISSING_DEPS -ne 0 ]; then
    echo -e "$ERR_MSG"
    echo "Installation Aborted: Unsupported Environment"
    echo ""
    echo "If you use a different OS (like macOS) or a different status bar (like Polybar),"
    echo "we would love your help to make $PROJECT_NAME support it."
    echo ""
    echo "Please check our CONTRIBUTING.md guide and fork the project at:"
    echo "$REPO_URL"
    exit 1
fi

echo "All requirements met! Your system is ready."
exit 0
