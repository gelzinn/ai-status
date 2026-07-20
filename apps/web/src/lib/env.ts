/**
 * The library / command / repo name. Rename the whole project by changing this
 * ONE constant — it flows into the domain, the GitHub slug, every `ai-status …`
 * command shown on the site, and the rendered provider guides (renderMarkdown
 * swaps the literal for this). `site.name` ("AI Status") is the product's
 * display name and is intentionally separate.
 */
export const LIB_NAME = "ai-status";

const SITE_ORIGIN = `https://${LIB_NAME}.gelzin.com`;
// owner/repo — GitHub exposes it from three hosts (github.com, api.github.com,
// raw.githubusercontent.com), so the slug is the piece worth reusing.
const REPO_SLUG = `gelzinn/${LIB_NAME}`;

/** The public website. */
export const site = {
	name: "AI Status",
	description: "Monitor your AI API limits directly from your status bar.",
	url: SITE_ORIGIN,
	/** Short install URL — the /install route serves packages/lib/install.sh. */
	installUrl: `${SITE_ORIGIN}/install`,
	/** macOS install URL — the /install/macos route serves install-macos.sh. */
	installUrlMac: `${SITE_ORIGIN}/install/macos`,
} as const;

/** The GitHub repository. */
export const repo = {
	url: `https://github.com/${REPO_SLUG}`,
	/** The repo's GitHub API endpoint (stars, metadata). */
	apiRepo: `https://api.github.com/repos/${REPO_SLUG}`,
	/** Latest-release endpoint used to show the current version. */
	apiUrl: `https://api.github.com/repos/${REPO_SLUG}/releases/latest`,
	/** Canonical raw URL for install.sh (mirrored by site.installUrl). */
	rawInstallUrl: `https://raw.githubusercontent.com/${REPO_SLUG}/main/packages/lib/install.sh`,
	/** Canonical raw URL for install-macos.sh (mirrored by site.installUrlMac). */
	rawInstallUrlMac: `https://raw.githubusercontent.com/${REPO_SLUG}/main/packages/lib/install-macos.sh`,
} as const;
