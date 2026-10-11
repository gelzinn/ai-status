import "server-only";

import { unstable_cache } from "next/cache";
import { createReleaseReader, fetchGitHubReleases } from "@/lib/changelog";
import { repo, site } from "@/lib/env";

const getCachedReleases = unstable_cache(
	() => fetchGitHubReleases({
		apiRepo: repo.apiRepo,
		userAgent: site.name,
		token: process.env.GITHUB_TOKEN,
	}),
	["github-releases-v1", repo.apiRepo],
	{ revalidate: 300 },
);

// The aggregate loader throws on any failed page. Next keeps its previous
// successful cache entry when background revalidation fails; the reader also
// retains the last successful value in this process for foreground failures.
export const getReleases = createReleaseReader(getCachedReleases, (error) => {
	console.error("Failed to fetch GitHub releases:", error);
});
