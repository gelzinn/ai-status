#!/bin/bash
if ! command -v kiro-cli &>/dev/null; then
  exit 0
fi

if ! kiro-cli whoami --format json &>/dev/null; then
  exit 0
fi

kiro-cli chat --no-interactive /usage 2>&1 || true
