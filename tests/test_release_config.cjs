// Exercise the real Release Please manifest with an in-memory GitHub client.
// No tags, releases, branches or PRs are written by these tests.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const Ajv = require("ajv");
const { configSchema, setLogger } = require("release-please");
const { buildManifest } = require("../.github/scripts/release_please.cjs");

const root = path.resolve(__dirname, "..");
const config = JSON.parse(fs.readFileSync(path.join(root, "release-please-config.json")));
const packageContent = fs.readFileSync(path.join(root, "package.json"), "utf8");
const pluginContent = fs.readFileSync(path.join(root, "manifest.json"), "utf8");
const previousVersion = JSON.parse(packageContent).version;
const previousSha = config["bootstrap-sha"];
const quiet = { info() {}, warn() {}, debug() {}, trace() {}, error() {} };
setLogger(quiet);

function commit(message, files, sha = "f".repeat(40)) {
  return { message, files, sha };
}

function assertCanonicalVersionUpdates(pr) {
  assert.deepEqual(pr.updates.map(update => update.path), ["package.json", "manifest.json"]);
  const updated = JSON.parse(pr.updates[0].updater.updateContent(packageContent));
  const plugin = JSON.parse(pr.updates[1].updater.updateContent(pluginContent));
  assert.match(updated.version, /^\d+\.\d+\.\d+$/);
  assert.equal(plugin.version, updated.version);
  assert.deepEqual({ ...updated, version: previousVersion }, JSON.parse(packageContent));
  assert.deepEqual({ ...plugin, version: previousVersion }, JSON.parse(pluginContent));
  assert.equal(pr.headRefName, "release-please--branches--main");
}

async function manifest(commits, merged = [], options = {}) {
  const currentVersion = Object.hasOwn(options, "currentVersion") ? options.currentVersion : previousVersion;
  const baselineSha = options.draft ? "b".repeat(40) : previousSha;
  const github = {
    repository: { owner: "gelzinn", repo: "ai-status" },
    async getFileJson(file) {
      assert.notEqual(file, ".release-please-manifest.json");
      if (file === "package.json") return { ...JSON.parse(packageContent), version: currentVersion };
      if (file === "release-please-config.json" && options.config) return options.config;
      return JSON.parse(fs.readFileSync(path.join(root, file)));
    },
    async getFileContentsOnBranch(file) {
      assert.equal(file, "package.json");
      return { parsedContent: JSON.stringify({ ...JSON.parse(packageContent), version: currentVersion }) };
    },
    async *releaseIterator() {
      // Newer unrelated or prerelease tags must not become the release baseline.
      yield { tagName: "v999.0.0-beta.1", sha: "c".repeat(40), notes: "Preview" };
      yield { tagName: "other-v999.0.0", sha: "d".repeat(40), notes: "Other component" };
      if (!options.tagOnly) {
        yield { tagName: `v${currentVersion}`, sha: baselineSha,
          notes: "Previous release", draft: !!options.draft };
        if (options.draft) {
          yield { tagName: `v${previousVersion}`, sha: previousSha, notes: "Published stable release" };
        }
      }
    },
    async *tagIterator() {
      yield { name: `v${currentVersion}`, sha: baselineSha };
    },
    async *mergeCommitIterator() {
      yield* commits;
      yield commit(`chore: release v${currentVersion}`, ["package.json"], baselineSha);
      // A historical feature must never leak into the next release notes.
      yield commit("feat: historical feature", ["packages/lib/src/core/daemon.py"], "a".repeat(40));
    },
    async *pullRequestIterator() {
      yield* merged;
    },
  };
  return buildManifest(github, "main");
}

test("release config uses one canonical package version and preserves the release policy", () => {
  const ajv = new Ajv({ strict: false, validateFormats: false });
  assert.equal(ajv.validate(configSchema, config), true, JSON.stringify(ajv.errors));
  assert.match(previousVersion, /^\d+\.\d+\.\d+$/);
  assert.equal(config.packages["."]["release-type"], "node");
  assert.equal(config.packages["."]["package-name"], "");
  assert.equal(config.packages["."]["include-component-in-tag"], false);
  assert.equal(config.packages["."]["include-v-in-tag"], true);
  assert.equal(config.packages["."]["draft"], true);
  assert.equal(config.packages["."]["force-tag-creation"], true);
  assert.deepEqual(config.packages["."]["exclude-paths"], ["apps/web"]);
  assert.deepEqual(config.packages["."]["extra-files"], [
    { type: "json", path: "manifest.json", jsonpath: "$.version" },
  ]);
  assert.equal(config.packages["."]["skip-changelog"], true);
  assert.equal(Object.hasOwn(config.packages["."], "changelog-path"), false);
  assert.equal(fs.existsSync(path.join(root, "packages/lib/CHANGELOG.md")), false);
  assert.equal(fs.existsSync(path.join(root, ".release-please-manifest.json")), false);
  assert.equal(fs.existsSync(path.join(root, "packages/lib/VERSION")), false);
  assert.equal(JSON.parse(pluginContent).version, previousVersion);
});

test("web-only features and routine maintenance do not propose a release", async () => {
  const release = await manifest([
    commit("feat(web): redesign the site", ["apps/web/src/app/page.tsx"]),
    commit("chore: update CI", [".github/workflows/ci.yml"]),
  ]);
  assert.equal((await release.buildPullRequests()).length, 0);
});

test("library fixes propose a patch changing only the canonical and derived JSON versions", async () => {
  const release = await manifest([commit("fix(install): preserve failed downloads", ["packages/lib/install.sh"])]);
  const [pr] = await release.buildPullRequests();
  const [major, minor, patch] = previousVersion.split(".").map(Number);
  assert.match(pr.body.toString(), new RegExp(`${major}\\.${minor}\\.${patch + 1}`));
  assert.match(pr.body.toString(), /Bug Fixes/);
  assert.match(pr.body.toString(), /preserve failed downloads/);
  assertCanonicalVersionUpdates(pr);
  assert.equal(JSON.parse(pr.updates[0].updater.updateContent(packageContent)).version,
    `${major}.${minor}.${patch + 1}`);
});

test("features and fixes accumulate in one PR, including shared metadata", async () => {
  const release = await manifest([
    commit("feat(providers): add a provider", ["packages/shared/providers/providers.json"]),
    commit("fix(install): pin stable versions", ["packages/lib/install.sh"], "e".repeat(40)),
    commit("feat(web): redesign the site", ["apps/web/src/app/page.tsx"], "d".repeat(40)),
  ]);
  const prs = await release.buildPullRequests();
  assert.equal(prs.length, 1);
  const pr = prs[0];
  const notes = pr.body.toString();
  assert.match(notes, /Features/);
  assert.match(notes, /Bug Fixes/);
  assert.match(notes, /add a provider/);
  assert.match(notes, /pin stable versions/);
  assert.doesNotMatch(notes, /redesign the site|historical feature/);
  assertCanonicalVersionUpdates(pr);

  // Ordinary merges publish nothing. Only the generated release PR is eligible.
  const ordinary = await manifest([], [{ number: 1, labels: [], title: "feat: add a provider" }]);
  assert.equal((await ordinary.buildReleases()).length, 0);
  const releaseSha = "b".repeat(40);
  const merged = await manifest([], [{
    number: 2,
    labels: pr.labels,
    title: pr.title.toString(),
    body: notes,
    headBranchName: pr.headRefName,
    baseBranchName: "main",
    sha: releaseSha,
    mergeCommitOid: releaseSha,
    files: pr.updates.map(update => update.path),
  }]);
  const [published] = await merged.buildReleases();
  const [major, minor] = previousVersion.split(".").map(Number);
  assert.equal(published.tag.toString(), `v${major}.${minor + 1}.0`);
  assert.equal(published.sha, releaseSha);
  assert.equal(published.draft, true);
  assert.equal(published.forceTag, true);
  assert.equal(published.prerelease, undefined);
  assert.match(published.notes, /add a provider/);
  assert.match(published.notes, /pin stable versions/);
});

test("user-written PR entries replace internal commit wording in release notes", async () => {
  const change = commit("feat(install): refactor all the installer internals", ["packages/lib/install.sh"]);
  change.pullRequest = {
    number: 34,
    body: "## User-facing changes\n\nBEGIN_COMMIT_OVERRIDE\n" +
      "feat(install): restore the previous version when an update fails\n\n" +
      "fix(settings): preserve your selected provider and display preferences\n" +
      "END_COMMIT_OVERRIDE\n\n## Validation\nOffline tests pass.\n",
  };
  const release = await manifest([change]);
  const [pr] = await release.buildPullRequests();
  const notes = pr.body.toString();
  assert.match(notes, /restore the previous version when an update fails/);
  assert.match(notes, /preserve your selected provider and display preferences/);
  assert.match(notes, /Features/);
  assert.match(notes, /Bug Fixes/);
  assert.doesNotMatch(notes, /refactor all the installer internals|Offline tests/);
  assertCanonicalVersionUpdates(pr);
});

test("the existing stable tag bounds history even without a matching GitHub release", async () => {
  const release = await manifest([
    commit("fix(install): preserve offline installs", ["packages/lib/install.sh"]),
  ], [], { tagOnly: true });
  const [pr] = await release.buildPullRequests();
  assertCanonicalVersionUpdates(pr);
  assert.match(pr.body.toString(), /preserve offline installs/);
  assert.doesNotMatch(pr.body.toString(), /historical feature|999\.0\.0/);
  assert.match(pr.body.toString(), new RegExp(`compare/v${previousVersion}\\.\\.\\.v`));
});

test("a merged package version remains the baseline while its stable draft awaits publication", async () => {
  const [major, minor, patch] = previousVersion.split(".").map(Number);
  const pendingVersion = `${major}.${minor}.${patch + 1}`;
  const release = await manifest([], [], { currentVersion: pendingVersion, draft: true });
  assert.equal(release.releasedVersions["."].toString(), pendingVersion);
  assert.equal((await release.buildPullRequests()).length, 0);
});

test("invalid or missing canonical versions fail before proposing any release", async () => {
  await assert.rejects(manifest([], [], { currentVersion: undefined }), /stable version/);
  await assert.rejects(manifest([], [], { currentVersion: "0.14.0-beta.1" }), /stable version/);
  await assert.rejects(manifest([], [], { currentVersion: "not-a-version" }), /stable version/);
});

test("a missing Omarchy version updater fails instead of producing an unsynchronized release PR", async () => {
  const incomplete = structuredClone(config);
  delete incomplete.packages["."]["extra-files"];
  const release = await manifest([
    commit("fix(install): preserve failed downloads", ["packages/lib/install.sh"]),
  ], [], { config: incomplete });
  await assert.rejects(release.buildPullRequests(), /derived Omarchy version exactly once/);
});
