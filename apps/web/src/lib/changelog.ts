/** Public release data used by the changelog. Credentials stay in releases.ts. */
export interface Release {
	id: number;
	name: string;
	tagName: string;
	url: string;
	publishedAt: string;
	body: string;
}

export type ReleaseResult =
	| { status: "available"; releases: Release[] }
	| { status: "unavailable"; releases: [] };

export const RELEASES_PER_PAGE = 10;
const API_PAGE_SIZE = 100;

interface FetchReleasesOptions {
	apiRepo: string;
	userAgent: string;
	token?: string;
	fetcher?: typeof fetch;
}

function normalizeRelease(value: unknown): Release | null {
	if (!value || typeof value !== "object") {
		throw new Error("GitHub returned an invalid release.");
	}
	const release = value as Record<string, unknown>;
	if (typeof release.draft !== "boolean" || typeof release.prerelease !== "boolean") {
		throw new Error("GitHub returned invalid release visibility.");
	}
	if (release.draft || release.prerelease) return null;

	if (
		!Number.isSafeInteger(release.id) || (release.id as number) <= 0 ||
		typeof release.tag_name !== "string" || !release.tag_name.trim() ||
		typeof release.html_url !== "string" ||
		typeof release.published_at !== "string" ||
		!Number.isFinite(Date.parse(release.published_at)) ||
		(release.name != null && typeof release.name !== "string") ||
		(release.body != null && typeof release.body !== "string")
	) {
		throw new Error("GitHub returned invalid release metadata.");
	}
	const url = new URL(release.html_url);
	if (url.protocol !== "https:" || url.hostname !== "github.com") {
		throw new Error("GitHub returned an invalid release URL.");
	}
	return {
		id: release.id as number,
		name: (release.name as string | null | undefined)?.trim() || release.tag_name,
		tagName: release.tag_name,
		url: url.href,
		publishedAt: release.published_at,
		body: (release.body as string | null | undefined) ?? "",
	};
}

function nextPage(link: string | null, endpoint: URL, page: number, count: number): number | null {
	if (!link) return count === API_PAGE_SIZE ? page + 1 : null;
	const next = link.split(",").find((part) => /;\s*rel="next"/.test(part));
	if (!next) return null;
	const href = next.match(/<([^>]+)>/)?.[1];
	if (!href) throw new Error("GitHub returned invalid pagination.");
	const url = new URL(href, endpoint);
	const nextNumber = Number(url.searchParams.get("page"));
	// Never follow an arbitrary Link URL with the optional GitHub credential.
	// Only the next page number is carried into our own trusted endpoint.
	if (
		url.origin !== endpoint.origin || url.pathname !== endpoint.pathname ||
		!Number.isSafeInteger(nextNumber) || nextNumber !== page + 1
	) {
		throw new Error("GitHub returned invalid pagination.");
	}
	return nextNumber;
}

/** Fetch every page before returning, so a partial history is never cached. */
export async function fetchGitHubReleases({
	apiRepo,
	userAgent,
	token,
	fetcher = fetch,
}: FetchReleasesOptions): Promise<Release[]> {
	const endpoint = new URL(`${apiRepo.replace(/\/$/, "")}/releases`);
	const releases = new Map<number, Release>();
	let page: number | null = 1;
	while (page !== null) {
		const url = new URL(endpoint);
		url.searchParams.set("per_page", String(API_PAGE_SIZE));
		url.searchParams.set("page", String(page));
		const response = await fetcher(url.href, {
			headers: {
				Accept: "application/vnd.github+json",
				"User-Agent": userAgent,
				...(token ? { Authorization: `Bearer ${token}` } : {}),
			},
			cache: "no-store",
			redirect: "error",
			signal: AbortSignal.timeout(5000),
		});
		if (!response.ok) {
			throw new Error(`GitHub releases request failed (${response.status}).`);
		}
		const data: unknown = await response.json();
		if (!Array.isArray(data)) throw new Error("GitHub returned an invalid release list.");
		for (const value of data) {
			const release = normalizeRelease(value);
			if (release && !releases.has(release.id)) releases.set(release.id, release);
		}
		page = nextPage(response.headers.get("link"), endpoint, page, data.length);
	}
	return [...releases.values()].sort((a, b) =>
		Date.parse(b.publishedAt) - Date.parse(a.publishedAt) || b.id - a.id,
	);
}

/** Keep the last complete history if a read fails, while retrying future reads. */
export function createReleaseReader(
	load: () => Promise<Release[]>,
	onError: (error: unknown) => void = () => {},
): () => Promise<ReleaseResult> {
	let lastGood: Release[] | null = null;
	return async () => {
		try {
			lastGood = await load();
			return { status: "available", releases: lastGood };
		} catch (error) {
			onError(error);
			return lastGood === null
				? { status: "unavailable", releases: [] }
				: { status: "available", releases: lastGood };
		}
	};
}

/** Search the complete stable history, then paginate the matches. */
export function selectReleases(
	releases: Release[],
	{ query = "", page = 1 }: { query?: string; page?: number } = {},
) {
	const normalizedQuery = query.trim();
	const needle = normalizedQuery.toLowerCase();
	const matches = needle
		? releases.filter((release) =>
			[release.name, release.tagName, release.body].some((text) => text.toLowerCase().includes(needle)),
		)
		: releases;
	const pageCount = Math.max(1, Math.ceil(matches.length / RELEASES_PER_PAGE));
	const selectedPage = Math.min(pageCount, Math.max(1, Number.isFinite(page) ? Math.floor(page) : 1));
	const start = (selectedPage - 1) * RELEASES_PER_PAGE;
	return {
		releases: matches.slice(start, start + RELEASES_PER_PAGE),
		query: normalizedQuery,
		page: selectedPage,
		pageCount,
		total: matches.length,
	};
}
