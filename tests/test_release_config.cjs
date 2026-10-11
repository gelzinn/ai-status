// Exercise the real Release Please manifest with an in-memory GitHub client.
// No tags, releases, branches or PRs are written by these tests.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const Ajv = require("ajv");
const { Manifest, configSchema, setLogger } = require("release-please");

const root = path.resolve(__dirname, "..");
const config = JSON.parse(fs.readFileSync(path.join(root, "release-please-config.json")));
const versions = JSON.parse(fs.readFileSync(path.join(root, ".release-please-manifest.json")));
const previousVersion = versions["."];
const previousSha = config["bootstrap-sha"];
const quiet = { info() {}, warn() {}, debug() {}, trace() {}, error() {} };
setLogger(quiet);

function commit(message, files, sha = "f".repeat(40)) {
  return { message, files, sha };
}

function assertNoChangelogUpdates(pr) {
  assert.equal(
    pr.updates.some(update => /(^|\/)CHANGELOG\.md$/i.test(update.path)),
    false,
    "Release PRs must keep notes in their body without creating a changelog file",
  );
}

async function manifest(commits, merged = []) {
  const github = {
    repository: { owner: "gelzinn", repo: "ai-status" },
    async getFileJson(file) {
      return JSON.parse(fs.readFileSync(path.join(root, file)));
    },
    async *releaseIterator() {
      yield { tagName: `v${previousVersion}`, sha: previousSha, notes: "Previous release" };
    },
    async *mergeCommitIterator() {
      yield* commits;
      yield commit(`chore: release v${previousVersion}`, ["packages/lib/VERSION"], previousSha);
      // A historical feature must never leak into the next release notes.
      yield commit("feat: historical feature", ["packages/lib/src/core/daemon.py"], "a".repeat(40));
    },
    async *pullRequestIterator() {
      yield* merged;
    },
  };
  return Manifest.fromManifest(github, "main");
}

test("release config is valid and starts from the current VERSION", () => {
  const ajv = new Ajv({ strict: false, validateFormats: false });
  assert.equal(ajv.validate(configSchema, config), true, JSON.stringify(ajv.errors));
  assert.equal(fs.readFileSync(path.join(root, "packages/lib/VERSION"), "utf8").trim(), previousVersion);
  assert.equal(config.packages["."]["skip-changelog"], true);
  assert.equal(Object.hasOwn(config.packages["."], "changelog-path"), false);
  assert.equal(fs.existsSync(path.join(root, "packages/lib/CHANGELOG.md")), false);
});

test("web-only features and routine maintenance do not propose a release", async () => {
  const release = await manifest([
    commit("feat(web): redesign the site", ["apps/web/src/app/page.tsx"]),
    commit("chore: update CI", [".github/workflows/ci.yml"]),
  ]);
  assert.equal((await release.buildPullRequests()).length, 0);
});

test("library fixes propose a patch with notes and a matching VERSION", async () => {
  const release = await manifest([commit("fix(install): preserve failed downloads", ["packages/lib/install.sh"])]);
  const [pr] = await release.buildPullRequests();
  const [major, minor, patch] = previousVersion.split(".").map(Number);
  assert.match(pr.body.toString(), new RegExp(`${major}\\.${minor}\\.${patch + 1}`));
  assert.match(pr.body.toString(), /Bug Fixes/);
  assert.match(pr.body.toString(), /preserve failed downloads/);
  assertNoChangelogUpdates(pr);
  const version = pr.updates.find(update => update.path === "packages/lib/VERSION");
  assert.equal(version.updater.updateContent(previousVersion), `${major}.${minor}.${patch + 1}\n`);
  const plugin = pr.updates.find(update => update.path === "manifest.json");
  assert.ok(plugin, "The Omarchy plugin version must follow the library release");
  const pluginContent = fs.readFileSync(path.join(root, "manifest.json"), "utf8");
  assert.equal(JSON.parse(plugin.updater.updateContent(pluginContent)).version, `${major}.${minor}.${patch + 1}`);
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
  assertNoChangelogUpdates(pr);
  assert.ok(pr.updates.some(update => update.path === ".release-please-manifest.json"));

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
  assertNoChangelogUpdates(pr);
});
