const SITE_ORIGIN = "https://ai-status.gelzin.com";
// owner/repo — GitHub exposes it from three hosts (github.com, api.github.com,
// raw.githubusercontent.com), so the slug is the piece worth reusing.
const REPO_SLUG = "gelzinn/ai-status";

/** The public website. */
export const site = {
	name: "AI Status",
	description: "Monitor your AI API limits directly from your status bar.",
	url: SITE_ORIGIN,
	/** Short install URL — the /install route serves packages/lib/install.sh. */
	installUrl: `${SITE_ORIGIN}/install`,
} as const;

/** The GitHub repository. */
export const repo = {
	url: `https://github.com/${REPO_SLUG}`,
	/** Latest-release endpoint used to show the current version. */
	apiUrl: `https://api.github.com/repos/${REPO_SLUG}/releases/latest`,
	/** Canonical raw URL for install.sh (mirrored by site.installUrl). */
	rawInstallUrl: `https://raw.githubusercontent.com/${REPO_SLUG}/main/packages/lib/install.sh`,
} as const;
