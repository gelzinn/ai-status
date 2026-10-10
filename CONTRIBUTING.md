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

## Releases

Development continues on `main`. The public installer downloads the tag of
the latest published stable GitHub Release, so unreleased commits do not
reach users who install or update through the public command.

After CI succeeds on `main`, Release Please opens or updates a single release
PR with the next version, `packages/lib/VERSION`,
`.release-please-manifest.json`, and `packages/lib/CHANGELOG.md`. Several PRs
can accumulate before a release. Merging a normal feature or fix PR does not
publish a version; merging the generated release PR publishes its version
tag and GitHub Release after the same CI checks succeed. The Release
workflow can also be rerun manually on `main` after a transient failure.

Use Conventional Commit titles and squash merges to make the release notes
useful for users:

- `feat(codex): show the weekly reset time` proposes a minor version.
- `fix(install): preserve the existing install when a download fails`
  proposes a patch version.
- Add `!` or a `BREAKING CHANGE:` footer for incompatible changes.
- Changes exclusively under `apps/web` do not bump the library version.
  Shared provider metadata is part of the library release.
- Routine `docs`, `chore`, `test`, and `ci` commits are omitted from release
  notes and do not trigger releases by themselves.

Before merging the release PR, review both its release notes and the generated
changelog, and add any migration instructions users need. GitHub Release
notes are taken from the release PR body; keep it consistent with the changelog.
To keep custom wording across further
updates to the release PR, put it in the original feature/fix PR description
using a `BEGIN_COMMIT_OVERRIDE` / `END_COMMIT_OVERRIDE` block, as described
in [Release Please's documentation](https://github.com/googleapis/release-please#how-can-i-fix-release-notes).
Keep the generated release PR labels and version metadata intact.

The workflow uses the existing `BOT_TOKEN` secret with repository contents,
pull request, and issue-label permissions. Using a bot token allows CI to
run on generated PRs. Require the CI checks in the `main` branch rules as
well if merging failing PRs must be prevented.
