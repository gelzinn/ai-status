# Historical release notes

These files contain the reviewed GitHub release bodies for the 15 published stable releases from v0.1.0 through v0.9.0. GitHub Releases remain the content source for the [web changelog](https://ai-status.gelzin.com/changelog); these Markdown files record a one-time historical normalization, rather than a second changelog or input to the release workflow. Releases v0.10.0 and later retain their existing Release Please notes.

Each file uses the current release-note structure: a linked version heading, the original UTC publication date and applicable Features, Bug Fixes, Performance Improvements, Documentation or Maintenance sections. The initial release links to its tagged commit history because it has no preceding release. Changes are attributed to their original pull requests or commits. Version-bump commits, release preparation boilerplate and merge commits are omitted. @allankayan's first contribution is preserved in v0.2.0.

## Evidence

The source evidence is the original published GitHub release body, the tagged comparison and the commit messages and file changes in that range. Publication dates come from each release's `published_at` metadata, rather than the tag or commit date. The original bodies are retained in the migration snapshot described below. Links use the current `gelzinn/ai-status` repository name, including releases published before the repository was renamed from `omarchy-ai-status`.

| Release | Tagged evidence | Main change references |
| --- | --- | --- |
| v0.1.0 | [Initial history](https://github.com/gelzinn/ai-status/commits/v0.1.0) | [Initial implementation](https://github.com/gelzinn/ai-status/commit/e66291893ab385c0f5f1bccfed2eccb5a9062d77), [configuration](https://github.com/gelzinn/ai-status/commit/f3781e9d1a3d5e45d5a553148f02d4ed2fdf34cb), [terminal launch](https://github.com/gelzinn/ai-status/commit/82938959938f72aa050458edc5e86cb5216f4693) |
| v0.2.0 | [v0.1.0…v0.2.0](https://github.com/gelzinn/ai-status/compare/v0.1.0...v0.2.0) | [#1](https://github.com/gelzinn/ai-status/pull/1), documentation commits linked in the notes |
| v0.3.0 | [v0.2.0…v0.3.0](https://github.com/gelzinn/ai-status/compare/v0.2.0...v0.3.0) | [#2](https://github.com/gelzinn/ai-status/pull/2) |
| v0.3.1 | [v0.3.0…v0.3.1](https://github.com/gelzinn/ai-status/compare/v0.3.0...v0.3.1) | [#3](https://github.com/gelzinn/ai-status/pull/3) |
| v0.3.2 | [v0.3.1…v0.3.2](https://github.com/gelzinn/ai-status/compare/v0.3.1...v0.3.2) | [#5](https://github.com/gelzinn/ai-status/pull/5) |
| v0.3.3 | [v0.3.2…v0.3.3](https://github.com/gelzinn/ai-status/compare/v0.3.2...v0.3.3) | [Funding configuration](https://github.com/gelzinn/ai-status/commit/389f3b3f506ebd58d9981821b9c939497113f431) |
| v0.4.0 | [v0.3.3…v0.4.0](https://github.com/gelzinn/ai-status/compare/v0.3.3...v0.4.0) | [#6](https://github.com/gelzinn/ai-status/pull/6) |
| v0.4.1 | [v0.4.0…v0.4.1](https://github.com/gelzinn/ai-status/compare/v0.4.0...v0.4.1) | [#7](https://github.com/gelzinn/ai-status/pull/7) |
| v0.4.2 | [v0.4.1…v0.4.2](https://github.com/gelzinn/ai-status/compare/v0.4.1...v0.4.2) | [#8](https://github.com/gelzinn/ai-status/pull/8), [#9](https://github.com/gelzinn/ai-status/pull/9), [#10](https://github.com/gelzinn/ai-status/pull/10) |
| v0.5.0 | [v0.4.2…v0.5.0](https://github.com/gelzinn/ai-status/compare/v0.4.2...v0.5.0) | [#11](https://github.com/gelzinn/ai-status/pull/11), [#12](https://github.com/gelzinn/ai-status/pull/12), [#14](https://github.com/gelzinn/ai-status/pull/14), [#15](https://github.com/gelzinn/ai-status/pull/15), [#16](https://github.com/gelzinn/ai-status/pull/16), [#17](https://github.com/gelzinn/ai-status/pull/17) |
| v0.6.0 | [v0.5.0…v0.6.0](https://github.com/gelzinn/ai-status/compare/v0.5.0...v0.6.0) | [#19](https://github.com/gelzinn/ai-status/pull/19) |
| v0.6.1 | [v0.6.0…v0.6.1](https://github.com/gelzinn/ai-status/compare/v0.6.0...v0.6.1) | [#21](https://github.com/gelzinn/ai-status/pull/21) |
| v0.7.0 | [v0.6.1…v0.7.0](https://github.com/gelzinn/ai-status/compare/v0.6.1...v0.7.0) | [#23](https://github.com/gelzinn/ai-status/pull/23) |
| v0.8.0 | [v0.7.0…v0.8.0](https://github.com/gelzinn/ai-status/compare/v0.7.0...v0.8.0) | [#25](https://github.com/gelzinn/ai-status/pull/25) |
| v0.9.0 | [v0.8.0…v0.9.0](https://github.com/gelzinn/ai-status/compare/v0.8.0...v0.9.0) | [#27](https://github.com/gelzinn/ai-status/pull/27) |

Two historical cases need explicit interpretation:

* v0.3.3 originally had only a comparison link. Its range contains the funding configuration and a version bump; the normalized notes describe only the funding change.
* v0.5.0's original generated body compared against v0.4.1 and repeated changes already published in v0.4.2. The normalized body compares against v0.4.2 and assigns each substantive change to the first published tag containing it.

The Maintenance and release-related Bug Fixes describe the automation shipped at those historical tags. They are historical notes, not instructions for the current release workflow.

## Body-only migration

Applied on October 11, 2026: all 15 legacy release bodies match these files.
Release IDs, names, tags, target commits, publication dates, status and assets
were checked against the original snapshot. The seven modern releases were
also checked and their bodies were unchanged.

Before applying these files, export the complete existing release metadata and bodies to a dated JSON snapshot outside the repository. Keep the snapshot's location in the migration record so the original bodies can be restored; do not commit local paths, credentials or transient API responses here.

After review, update only the `body` field of each matching published release, using its existing release ID. Preserve names, tags, target commits, publication dates, draft/prerelease status and assets. Do not recreate or republish releases. Read the releases back and compare their bodies with these files, then compare all other metadata and assets with the backup. Verify that modern releases are unchanged and that the web changelog renders the migrated Markdown after its cache refresh.

Future releases continue to obtain their notes from Release Please and GitHub Releases; this directory does not participate in generation or publication.
