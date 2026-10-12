// Keep Release Please's release lifecycle while using one version source.
// Tested against release-please@17.3.0; no version state is written separately.
const { GitHub, Manifest } = require("release-please");
const { ManifestPlugin } = require("release-please/build/src/plugin");
const { PackageJson } = require("release-please/build/src/updaters/node/package-json");
const { GenericJson } = require("release-please/build/src/updaters/generic-json");

class PackageVersionUpdates extends ManifestPlugin {
  async run(candidates) {
    for (const { pullRequest } of candidates) {
      // The Node strategy also proposes optional lock/sample files, and
      // Manifest adds its state updater. Retain only the canonical package
      // updater and the required Omarchy version derived from that same version.
      const packages = pullRequest.updates.filter(update =>
        update.path === "package.json" && update.updater instanceof PackageJson);
      const plugins = pullRequest.updates.filter(update =>
        update.path === "manifest.json" && update.updater instanceof GenericJson &&
        update.updater.jsonpath === "$.version");
      if (packages.length !== 1 || plugins.length !== 1) {
        throw new Error("A release PR must update package.json and the derived Omarchy version exactly once");
      }
      pullRequest.updates = [packages[0], plugins[0]];
    }
    return candidates;
  }
}

async function buildManifest(github, targetBranch = "main") {
  // Manifest's version reader expects {path: version}. Adapt the canonical
  // package on reads, leaving package contents and all other GitHub APIs intact.
  const versionSource = new Proxy(github, {
    get(target, property) {
      if (property === "getFileJson") return async (file, branch) => {
        const contents = await target.getFileJson(file, branch);
        if (file !== "package.json") return contents;
        if (!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(contents.version)) {
          throw new Error("package.json must contain a stable version");
        }
        return { ".": contents.version };
      };
      const value = target[property];
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
  const manifest = await Manifest.fromManifest(
    versionSource, targetBranch, "release-please-config.json", "package.json");
  manifest.plugins.push(new PackageVersionUpdates(github, targetBranch, manifest.repositoryConfig));
  return manifest;
}

async function main() {
  const repository = process.env.GITHUB_REPOSITORY || "";
  const token = process.env.GH_TOKEN;
  if (!/^[\w.-]+\/[\w.-]+$/.test(repository) || !token) {
    throw new Error("GITHUB_REPOSITORY and GH_TOKEN are required");
  }
  const [owner, repo] = repository.split("/");
  const github = await GitHub.create({ owner, repo, token, defaultBranch: "main" });
  // Create tags/drafts first, then reload state before updating the next PR.
  // A pending draft is still found by its exact package version during retries.
  await (await buildManifest(github)).createReleases();
  await (await buildManifest(github)).createPullRequests();
}

module.exports = { buildManifest };
if (require.main === module) main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
