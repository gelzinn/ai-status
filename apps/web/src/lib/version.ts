import { readFile } from "node:fs/promises";
import path from "node:path";
import { repo } from "./env";

/** Prefer the published release; use the app's version file when GitHub is unavailable. */
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
  const version = await readFile(path.resolve(process.cwd(), "../../packages/lib/VERSION"), "utf-8");
  return `v${version.trim()}`;
}
