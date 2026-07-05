# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| latest  | :white_check_mark: |

## Reporting a Vulnerability

This project involves reading authentication tokens from local credentials
files (e.g. `.codex/auth.json`, GitHub Copilot tokens, session cookies) to
display usage limits. The software **never** transmits these credentials — all
data is fetched and rendered locally.

If you discover a security vulnerability, please open a
[GitHub Security Advisory](https://github.com/gelzinn/omarchy-ai-status/security/advisories/new)
instead of a public issue.
