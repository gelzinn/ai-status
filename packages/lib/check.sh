#!/bin/bash

# shellcheck source=./config.sh
source "$(dirname "$0")/config.sh"

GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
BOLD="\033[1m"
DIM="\033[2m"
RESET="\033[0m"

echo ""
echo -e "  ${YELLOW}${BOLD}${PROJECT_NAME}${RESET} ${DIM}— system check${RESET}"
echo ""

MISSING_DEPS=0
ERR_MSG=""

# OS Check
OS="$(uname -s)"
if [ "$OS" != "Linux" ]; then
    ERR_MSG+="  ${RED}✖${RESET} Unsupported OS: ${OS} (currently Linux only)\n"
    MISSING_DEPS=1
else
    echo -e "  ${GREEN}✔${RESET} OS: Linux"
fi

# Status Bar Check
if ! command -v waybar >/dev/null 2>&1; then
    ERR_MSG+="  ${RED}✖${RESET} waybar not found (required status bar)\n"
    MISSING_DEPS=1
else
    echo -e "  ${GREEN}✔${RESET} Waybar"
fi

# Utilities Check
for cmd in python3 jq curl git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        ERR_MSG+="  ${RED}✖${RESET} $cmd not found\n"
        MISSING_DEPS=1
    else
        echo -e "  ${GREEN}✔${RESET} $cmd"
    fi
done

# Optional: an SVG rasterizer is needed to render the provider logo (image
# module). Not fatal — without it the logo is simply skipped and the bar keeps
# working with text only.
if command -v magick >/dev/null 2>&1 || command -v convert >/dev/null 2>&1 || command -v rsvg-convert >/dev/null 2>&1; then
    echo -e "  ${GREEN}✔${RESET} SVG rasterizer ${DIM}(provider logo)${RESET}"
else
    echo -e "  ${YELLOW}!${RESET} No SVG rasterizer ${DIM}(install imagemagick or librsvg for the provider logo — optional)${RESET}"
fi

echo ""

if [ $MISSING_DEPS -ne 0 ]; then
    echo -e "$ERR_MSG"
    echo ""
    echo -e "  ${RED}Installation aborted${RESET}"
    echo ""
    echo "  Missing dependencies? Install them and try again."
    echo "  For non-Linux or non-Waybar support, see CONTRIBUTING.md:"
    echo "  $REPO_URL"
    exit 1
fi

echo -e "  ${GREEN}All good.${RESET}"
exit 0
