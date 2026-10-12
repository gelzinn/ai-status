import { readFile } from "node:fs/promises";
import path from "node:path";
import { repo } from "./env";

/** Prefer the published release; use package.json when GitHub is unavailable. */
export async function getLatestVersion(): Promise<string> {
  try {
    const response = await fetch(repo.apiUrl, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(5000),
    });
    if (response.ok) {
      const release = await response.json();
      if (typeof release?.tag_name === "string" && /^v?\d+\.\d+\.\d+(?:[-+][\w.-]+)?$/.test(release.tag_name)) {
        return release.tag_name.startsWith("v") ? release.tag_name : `v${release.tag_name}`;
      }
    }
  } catch {
    // The local version does not depend on the release API or its rate limits.
  }
  const { version } = JSON.parse(await readFile(path.resolve(process.cwd(), "../../package.json"), "utf-8"));
  if (typeof version !== "string" || !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(version)) {
	throw new Error("package.json must contain a stable application version");
  }
  return `v${version}`;
}
