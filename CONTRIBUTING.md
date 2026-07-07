# Contributing to AI Status

**Bug reports, feature requests, and pull requests are welcome.**

This project targets Linux and Waybar, but the core logic in `src/core/` and the provider scripts in `src/providers/` are platform-independent and can be adapted to other status bars or operating systems.

## Adding a New Provider

Each provider needs two files in `src/providers/<name>/`:

| File | Purpose |
|---|---|
| `query.sh` | Fetches raw data via API call, CLI invocation, or terminal interaction |
| `parse.py` | Exports `parse(raw_output)` returning a standardized JSON structure |

Walk through `src/providers/claude/` as a reference implementation.

Steps:

1. Fork the repository on GitHub
2. Create `src/providers/<name>/query.sh` with your data-fetching logic
3. Create `src/providers/<name>/parse.py` with a `parse(raw_output)` function
4. Register the provider via `ai-status config` (it appears automatically)
5. Open a pull request

## Adding Support for Other Platforms

The visual formatting lives in `src/core/render.py` using Pango markup (Waybar's format). To support another status bar or OS:

1. Fork the repository on GitHub
2. Modify `src/core/render.py` to output the appropriate format for your target
3. Update `install.sh` and `check.sh` for the new environment
4. Open a pull request

## Making Changes

| Step | Action |
|---|---|
| 1 | Fork and clone the repository |
| 2 | Make your changes -- keep the provider architecture consistent |
| 3 | Run `./install.sh` to test locally |
| 4 | Verify the daemon runs: `ai-status daemon` |
| 5 | Open a pull request describing what you changed and why |
