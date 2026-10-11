# Contributing to AI Status

**Bug reports, feature requests, and pull requests are welcome.**

This project supports Linux/Waybar, Omarchy Quickshell, a native Windows tray adapter and a native macOS menu bar app. The shared Python backend lives in `packages/lib/src/core/`, providers in `packages/lib/src/providers/`, and the native Omarchy plugin in `packages/lib/quickshell/`. Keep provider data separate from the frontend renderers; see [Windows development](docs/development/windows.md) and [macOS development](docs/development/macos.md).

## Adding a New Provider

Each provider needs two files in `src/providers/<name>/`:

| File | Purpose |
|---|---|
| `query.py` | Fetches raw data via API call, CLI invocation, or terminal interaction |
| `parse.py` | Exports `parse(raw_output)` returning a standardized JSON structure |

Walk through `src/providers/claude/` as a reference implementation.

Steps:

1. Fork the repository on GitHub
2. Create `packages/lib/src/providers/<name>/query.py` with your data-fetching logic and a `main()` function. Use `core.provider_http` for HTTP, CLI invocation and credential-free diagnostics; optional Python dependencies must stay out of the Linux import path. Bash is only a legacy fallback.
3. Create `src/providers/<name>/parse.py` with a `parse(raw_output)` function
4. Register the provider via `ai-status config` (it appears automatically)
5. Open a pull request

## Adding Support for Other Platforms

Waybar formatting lives in `packages/lib/src/core/render.py` using Pango markup. The Quickshell adapter emits structured snapshots from `packages/lib/src/core/quickshell.py`; QML owns its presentation. Keep new frontends separate so existing Waybar output remains compatible. To support another status bar or OS:

1. Fork the repository on GitHub
2. Add an output adapter for your target and reuse the existing queries and state
3. Update `install.sh` and `check.sh` for the new environment
4. Open a pull request

## Making Changes

| Step | Action |
|---|---|
| 1 | Fork and clone the repository |
| 2 | Make your changes -- keep the provider architecture consistent |
| 3 | Run `bash packages/lib/install.sh` to test locally |
| 4 | Verify the daemon runs: `ai-status daemon` |
| 5 | Open a pull request describing what you changed and why |

Run `python3 -m unittest discover -s packages/lib/tests -v` for adapter and isolated installer tests. For native plugin validation and desktop acceptance checks, see [Linux development](docs/development/linux.md#development-validation).

Run `python3 packages/lib/tests/run_qml_tests.py` for native settings and usage page tests. These use the production QML pages with a fake daemon and theme, via Qt Quick Test's offscreen renderer. Install `qt6-declarative-dev-tools`, `qml6-module-qtquick`, `qml6-module-qtquick-window`, `qml6-module-qtquick-shapes`, `qml6-module-qtqml-models`, `qml6-module-qtqml-workerscript`, `qml6-module-qttest`, and `qt6-qpa-plugins`. They do not replace an Omarchy desktop smoke test.
## Releases

Development continues on `main`. The public installer downloads the tag of
the latest published stable GitHub Release, so unreleased commits do not
reach users who install or update through the public command.

After CI succeeds on `main`, Release Please opens or updates a single release
PR with the next version, `packages/lib/VERSION`,
`.release-please-manifest.json`, and `manifest.json`. Release notes are generated
in the PR body without creating a changelog file. Several PRs
can accumulate before a release. Merging a normal feature or fix PR does not
publish a version. Merging the generated release PR creates its version tag
and a draft GitHub Release after the same CI checks succeed. The workflow
builds `ai-status-vX.Y.Z.tar.gz` from that exact tag, containing only
`packages/lib` and `packages/shared`, and smoke-tests the CLI. It attaches the
archive and `SHA256SUMS`, downloads them back to verify the checksum, then
publishes the release as `latest`. Until publication succeeds, users keep
receiving the previous stable release. The Release workflow can be rerun
manually on `main` to resume a draft after an upload or verification failure.

For a pending stable draft, the Windows workflow checks out that exact release
tag and builds and tests the installer and portable ZIP. Publication waits for
those checks, uploads the Windows files alongside the library archive and
verifies every downloaded checksum before marking the release as `latest`.
PR previews continue to build from the PR commit and do not publish releases.

Use Conventional Commit PR titles and squash merges:

- `feat(codex): show the weekly reset time` proposes a minor version.
- `fix(install): preserve the existing install when a download fails`
  proposes a patch version.
- Add `!` or a `BREAKING CHANGE:` footer for incompatible changes.
- Changes exclusively under `apps/web` do not bump the library version.
  Shared provider metadata is part of the library release.
- Routine `docs`, `chore`, `test`, and `ci` commits are omitted from release
  notes and do not trigger releases by themselves.

For `feat`, `fix`, `perf`, `revert`, `deps`, and breaking changes, fill in
`## User-facing changes` in the PR template. Write concrete benefits or
corrections, using the same type as the PR title for the first entry:

```text
BEGIN_COMMIT_OVERRIDE
feat(install): restore the previous version when an update fails

fix(settings): preserve the selected provider and display preferences
END_COMMIT_OVERRIDE
```

Release Please uses these entries instead of internal commit wording. The
`pr-metadata` check rejects invalid titles, missing notes, and placeholder
text. For routine maintenance, remove the block and write `None`. Generated
release PRs do not require this section. The default squash title uses the
validated PR title.

Before merging the release PR, review its release notes and add any migration
instructions users need. GitHub Release notes are taken from the release PR body.
Published stable notes appear on the [web changelog](https://ai-status.gelzin.com/changelog)
and [GitHub Releases](https://github.com/gelzinn/ai-status/releases).
Custom wording belongs in the original feature/fix PR description so it
survives updates to the generated release PR; see
[Release Please's documentation](https://github.com/googleapis/release-please#how-can-i-fix-release-notes).
Keep the generated release PR labels and version metadata intact.

Release Please uses `GITHUB_TOKEN`, so newly opened release PRs are authored
by `github-actions[bot]`. Enable **Allow GitHub Actions to create and approve
pull requests** in the repository's Actions settings; permissions are granted
explicitly to each job, and no personal access token is required.

When GitHub holds a bot-created PR's workflows for approval, a maintainer with
write access must select **Approve workflows to run** in the PR's merge box.
This starts the existing CI and Windows `pull_request` workflows; updated bot
commits can require approval again. See [GitHub's token documentation](https://docs.github.com/en/actions/concepts/security/github_token).
These checks use `pull_request` events because [checks from `workflow_dispatch`
do not satisfy required status checks in a branch ruleset](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks#checks-from-some-workflow-jobs-are-not-evaluated).

Retry failed jobs from their Actions run. Rerun Release manually on `main` to
resume a draft after an upload or verification failure. Wait for the required
PR checks before merging the generated release PR.

The `main` branch rules require `pr-metadata`, `lint`,
`python-syntax`, `installer`, `release-config`, and `release-package`, with
the PR branch up to date before merging. Tests validate versioning, note
generation, installation failures and recovery, and publication retries
without publishing a real release.
