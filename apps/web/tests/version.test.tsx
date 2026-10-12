import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { getLatestVersion } from "../src/lib/version";

test("the published release remains preferred over the local package version", async (t) => {
	t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ tag_name: "v99.0.0" })));
	assert.equal(await getLatestVersion(), "v99.0.0");
});

test("API failures use the canonical package version and ignore a conflicting legacy VERSION", async (t) => {
	const root = await mkdtemp(path.join(tmpdir(), "ai-status-web-version-"));
	const previous = process.cwd();
	try {
		await mkdir(path.join(root, "apps/web"), { recursive: true });
		await mkdir(path.join(root, "packages/lib"), { recursive: true });
		await writeFile(path.join(root, "package.json"), JSON.stringify({ version: "1.2.3" }));
		await writeFile(path.join(root, "packages/lib/VERSION"), "9.9.9\n");
		process.chdir(path.join(root, "apps/web"));
		const request = t.mock.method(globalThis, "fetch", async () => new Response("", { status: 503 }));
		assert.equal(await getLatestVersion(), "v1.2.3");
		request.mock.mockImplementation(async () => { throw new Error("network unavailable"); });
		assert.equal(await getLatestVersion(), "v1.2.3");
		for (const version of ["invalid", "01.2.3", "v1.2.3", null]) {
			await writeFile(path.join(root, "package.json"), JSON.stringify({ version }));
			await assert.rejects(getLatestVersion(), /stable application version/);
		}
	} finally {
		process.chdir(previous);
		await rm(root, { recursive: true, force: true });
	}
});
