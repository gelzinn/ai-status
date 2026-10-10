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
  const version = pr.updates.find(update => update.path === "packages/lib/VERSION");
  assert.equal(version.updater.updateContent(previousVersion), `${major}.${minor}.${patch + 1}\n`);
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
  assert.ok(pr.updates.some(update => update.path === "packages/lib/CHANGELOG.md"));
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
  assert.match(published.notes, /add a provider/);
  assert.match(published.notes, /pin stable versions/);
});
