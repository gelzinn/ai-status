import assert from "node:assert/strict";
import test from "node:test";
import {
	createReleaseReader,
	fetchGitHubReleases,
	selectReleases,
} from "../apps/web/src/lib/changelog.ts";

const apiRepo = "https://api.github.com/repos/example/project";
const options = { apiRepo, userAgent: "AI Status" };

function release(id = 1, overrides = {}) {
	return {
		id,
		name: `Release ${id}`,
		tag_name: `v1.0.${id}`,
		html_url: `https://github.com/example/project/releases/tag/v1.0.${id}`,
		published_at: "2026-10-01T12:00:00Z",
		body: `Notes ${id}`,
		draft: false,
		prerelease: false,
		...overrides,
	};
}

function response(data, { status = 200, link } = {}) {
	return new Response(JSON.stringify(data), {
		status,
		headers: { "Content-Type": "application/json", ...(link ? { Link: link } : {}) },
	});
}

async function history(values) {
	return fetchGitHubReleases({ ...options, fetcher: async () => response(values) });
}

test("fetches all linked pages, removes drafts/prereleases, and sorts by publication", async () => {
	const requested = [];
	const releases = await fetchGitHubReleases({
		...options,
		fetcher: async (url) => {
			requested.push(url);
			if (new URL(url).searchParams.get("page") === "1") {
				return response([
					release(1, { published_at: "2026-10-01T12:00:00Z" }),
					release(2, { draft: true, published_at: null }),
					release(3, { prerelease: true }),
				], { link: `<${apiRepo}/releases?per_page=100&page=2>; rel="next", <${apiRepo}/releases?per_page=100&page=2>; rel="last"` });
			}
			return response([
				release(4, { published_at: "2026-10-05T12:00:00Z" }),
				release(5, { published_at: "2026-09-30T12:00:00Z" }),
			], { link: `<${apiRepo}/releases?per_page=100&page=1>; rel="prev"` });
		},
	});
	assert.equal(requested.length, 2);
	assert.ok(requested.every((url) => new URL(url).searchParams.get("per_page") === "100"));
	assert.deepEqual(releases.map(({ id }) => id), [4, 1, 5]);
});

test("falls back to full-page detection when GitHub omits Link headers", async () => {
	let requests = 0;
	const releases = await fetchGitHubReleases({
		...options,
		fetcher: async () => {
			requests += 1;
			return response(requests === 1 ? Array.from({ length: 100 }, (_, i) => release(i + 1)) : [release(101)]);
		},
	});
	assert.equal(requests, 2);
	assert.equal(releases.length, 101);
});

test("a final Link header stops pagination even when the final page is full", async () => {
	let requests = 0;
	const releases = await fetchGitHubReleases({
		...options,
		fetcher: async () => {
			requests += 1;
			return response(Array.from({ length: 100 }, (_, i) => release(i + 1)), {
				link: `<${apiRepo}/releases?per_page=100&page=1>; rel="first"`,
			});
		},
	});
	assert.equal(requests, 1);
	assert.equal(releases.length, 100);
});

test("uses optional authorization, uncached page reads, and a timeout", async () => {
	let request;
	await fetchGitHubReleases({
		...options,
		token: "test-only-token",
		fetcher: async (_url, init) => {
			request = init;
			return response([]);
		},
	});
	assert.equal(request.headers.Authorization, "Bearer test-only-token");
	assert.equal(request.headers["User-Agent"], "AI Status");
	assert.equal(request.headers.Accept, "application/vnd.github+json");
	assert.equal(request.cache, "no-store");
	assert.equal(request.redirect, "error");
	assert.ok(request.signal instanceof AbortSignal);
	let anonymousRequest;
	await fetchGitHubReleases({
		...options,
		fetcher: async (_url, init) => {
			anonymousRequest = init;
			return response([]);
		},
	});
	assert.equal(anonymousRequest.headers.Authorization, undefined);
});

test("normalizes missing release names and notes without discarding the release", async () => {
	const [value] = await history([release(1, { name: null, body: null })]);
	assert.equal(value.name, "v1.0.1");
	assert.equal(value.body, "");
	assert.equal(value.tagName, "v1.0.1");
	assert.equal(value.publishedAt, "2026-10-01T12:00:00Z");
});

test("a repository without published stable releases returns an empty success", async () => {
	assert.deepEqual(await history([]), []);
	assert.deepEqual(await history([release(1, { draft: true }), release(2, { prerelease: true })]), []);
});

test("deduplicates release IDs across pages if publishing shifts pagination", async () => {
	const releases = await fetchGitHubReleases({
		...options,
		fetcher: async (url) => response([release(1)], new URL(url).searchParams.get("page") === "1"
			? { link: `<${apiRepo}/releases?page=2>; rel="next"` }
			: {}),
	});
	assert.equal(releases.length, 1);
});

test("rejects HTTP and network errors, including failure after a successful first page", async () => {
	for (const status of [403, 404, 429, 500]) {
		await assert.rejects(fetchGitHubReleases({ ...options, fetcher: async () => response({}, { status }) }), new RegExp(String(status)));
	}
	await assert.rejects(fetchGitHubReleases({ ...options, fetcher: async () => { throw new Error("network unavailable"); } }), /network unavailable/);
	await assert.rejects(fetchGitHubReleases({
		...options,
		fetcher: async (url) => new URL(url).searchParams.get("page") === "1"
			? response([release(1)], { link: `<${apiRepo}/releases?page=2>; rel="next"` })
			: response({}, { status: 503 }),
	}), /503/);
});

test("rejects malformed JSON, list, release metadata, and unsafe URLs", async () => {
	await assert.rejects(fetchGitHubReleases({ ...options, fetcher: async () => new Response("{ invalid json") }));
	for (const invalid of [
		{ message: "Not Found" },
		[null],
		[{}],
		[release(1, { prerelease: undefined })],
		[release(1, { id: "1" })],
		[release(1, { tag_name: "" })],
		[release(1, { published_at: null })],
		[release(1, { published_at: "invalid date" })],
		[release(1, { name: {} })],
		[release(1, { body: {} })],
		[release(1, { html_url: "javascript:alert(1)" })],
		[release(1, { html_url: "https://evil.example/releases" })],
	]) {
		await assert.rejects(history(invalid));
	}
});

test("rejects untrusted, skipped, and cyclic pagination without making another request", async () => {
	for (const href of [
		"https://evil.example/releases?page=2",
		"https://api.github.com/repos/other/project/releases?page=2",
		`${apiRepo}/releases?page=1`,
		`${apiRepo}/releases?page=3`,
	]) {
		let requests = 0;
		await assert.rejects(fetchGitHubReleases({
			...options,
			fetcher: async () => {
				requests += 1;
				return response([release(1)], { link: `<${href}>; rel="next"` });
			},
		}), /invalid pagination/);
		assert.equal(requests, 1);
	}
});

test("the reader distinguishes an unavailable cold cache from a valid empty history", async () => {
	const errors = [];
	const unavailable = createReleaseReader(async () => { throw new Error("GitHub unavailable"); }, (error) => errors.push(error));
	assert.deepEqual(await unavailable(), { status: "unavailable", releases: [] });
	assert.equal(errors.length, 1);
	const empty = createReleaseReader(async () => []);
	assert.deepEqual(await empty(), { status: "available", releases: [] });
});

test("the reader preserves its last complete history and retries after failed refreshes", async () => {
	const original = await history([release(1)]);
	const updated = await history([release(2)]);
	let attempts = 0;
	const read = createReleaseReader(async () => {
		attempts += 1;
		if (attempts === 1) return original;
		if (attempts < 4) throw new Error("Transient failure");
		return updated;
	});
	assert.deepEqual((await read()).releases, original);
	assert.deepEqual((await read()).releases, original);
	assert.deepEqual((await read()).releases, original);
	assert.deepEqual((await read()).releases, updated);
	assert.equal(attempts, 4);
});

test("a successful empty refresh replaces previous history and survives later failures", async () => {
	const original = await history([release(1)]);
	let attempts = 0;
	const read = createReleaseReader(async () => {
		attempts += 1;
		if (attempts === 1) return original;
		if (attempts === 2) return [];
		throw new Error("Transient failure");
	});
	await read();
	assert.deepEqual(await read(), { status: "available", releases: [] });
	assert.deepEqual(await read(), { status: "available", releases: [] });
});

test("paginates ten releases at a time and clamps invalid/out-of-range pages", async () => {
	const releases = await history(Array.from({ length: 23 }, (_, i) => release(i + 1)));
	const first = selectReleases(releases);
	assert.equal(first.releases.length, 10);
	assert.equal(first.total, 23);
	assert.equal(first.pageCount, 3);
	assert.equal(first.page, 1);
	const second = selectReleases(releases, { page: 2 });
	assert.deepEqual(second.releases, releases.slice(10, 20));
	const last = selectReleases(releases, { page: 200 });
	assert.equal(last.page, 3);
	assert.equal(last.releases.length, 3);
	for (const page of [0, -10, NaN, Infinity]) {
		assert.equal(selectReleases(releases, { page }).page, 1);
	}
	assert.equal(selectReleases(releases, { page: 2.5 }).page, 2);
});

test("searches names, versions, and full notes across the entire history before pagination", async () => {
	const releases = await history(Array.from({ length: 24 }, (_, i) => release(i + 1, {
		name: i === 0 ? "Windows improvements" : `Release ${i + 1}`,
		body: i > 10 ? "New WINDOWS support" : "Bug fixes",
	})));
	const first = selectReleases(releases, { query: " WINDOWS ", page: 1 });
	assert.equal(first.query, "WINDOWS");
	assert.equal(first.total, 14);
	assert.equal(first.pageCount, 2);
	assert.equal(first.releases.length, 10);
	const second = selectReleases(releases, { query: "windows", page: 2 });
	assert.equal(second.releases.length, 4);
	assert.equal(selectReleases(releases, { query: "v1.0.24" }).total, 1);
	assert.equal(selectReleases(releases, { query: "Bug fixes" }).total, 11);
	assert.deepEqual(selectReleases(releases, { query: "unknown", page: 2 }), {
		releases: [], query: "unknown", page: 1, pageCount: 1, total: 0,
	});
	assert.equal(selectReleases(releases, { query: "   " }).total, 24);
});
