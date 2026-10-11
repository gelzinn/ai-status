import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { renderMarkdown } from "../src/lib/markdown";

const release = { tagName: "v0.13.0", publishedAt: "2026-10-11T18:33:06Z" };

test("release Markdown preserves content and removes only the repeated automatic heading", async () => {
	const notes = "## [0.13.0](https://github.com/gelzinn/ai-status/compare/v0.12.1...v0.13.0) (2026-10-11)\n\n" +
		"### Features\n\n* **updates:** Keep your preferences.\n\n" +
		"[Details](https://github.com/gelzinn/ai-status/pull/1)\n\n" +
		"![Panel preview](https://example.com/preview.png)\n\n`ai-status update`\n\n" +
		"| Platform | Ready |\n| --- | --- |\n| Linux | Yes |";
	const html = renderToStaticMarkup(await renderMarkdown(notes, { release, headingPrefix: "release-123-" }));
	assert.doesNotMatch(html, /<h2/);
	assert.match(html, /id="release-123-features"/);
	assert.match(html, /<strong>updates:<\/strong>/);
	assert.match(html, /href="https:\/\/github.com\/gelzinn\/ai-status\/pull\/1"/);
	assert.match(html, /src="https:\/\/example.com\/preview.png"/);
	assert.match(html, /alt="Panel preview"/);
	assert.match(html, /<code>ai-status update<\/code>/);
	assert.match(html, /<table>/);
	const custom = renderToStaticMarkup(await renderMarkdown("## A new panel\n\nDetails.", { release }));
	assert.match(custom, /A new panel/);
	const differentDate = renderToStaticMarkup(await renderMarkdown(notes, {
		release: { ...release, publishedAt: "2026-10-12T00:00:00Z" },
	}));
	assert.match(differentDate, /<h2/);
});

test("heading IDs and local links remain unique within and across releases", async () => {
	const notes = "### Fixes\n\n[Jump to fixes](#fixes)\n\n### Fixes\n\nAnother fix.";
	const first = renderToStaticMarkup(await renderMarkdown(notes, { headingPrefix: "release-1-" }));
	const second = renderToStaticMarkup(await renderMarkdown(notes, { headingPrefix: "release-2-" }));
	assert.match(first, /id="release-1-fixes"/);
	assert.match(first, /id="release-1-fixes-1"/);
	assert.match(first, /href="#release-1-fixes"/);
	assert.match(second, /id="release-2-fixes"/);
	const guide = renderToStaticMarkup(await renderMarkdown(notes));
	assert.match(guide, /id="fixes"/);
	assert.match(guide, /href="#fixes"/);
});

test("external release content cannot execute HTML or unsafe URLs", async () => {
	const notes = "<script>alert('script')</script>\n\n" +
		'<img src="x" onerror="alert(1)">\n\n' +
		"[Unsafe](javascript:alert%281%29)\n\n![Unsafe image](data:text/html;base64,PHNjcmlwdD4=)\n\n" +
		"[Good](https://example.com)\n\n<iframe src=\"https://example.com\"></iframe>";
	const html = renderToStaticMarkup(await renderMarkdown(notes));
	assert.doesNotMatch(html, /<script|<iframe|onerror|javascript:|data:text\/html|src="x"/);
	assert.match(html, /href="https:\/\/example.com"/);
});

test("fenced code survives even when GitHub notes use an unknown language", async () => {
	const html = renderToStaticMarkup(await renderMarkdown("```custom-release-language\nai-status --version\n```"));
	assert.match(html, /<pre/);
	assert.match(html, /ai-status --version/);
});

test("release images have valid SSR markup and linked images preserve their destination", async () => {
	const notes = "![Preview](https://example.com/image.png)\n\n[![Linked preview](https://example.com/image.png)](https://example.com/full-image.png)";
	const html = renderToStaticMarkup(await renderMarkdown(notes, { release }));
	assert.match(html, /<button[^>]+aria-label="Enlarge Preview"/);
	assert.doesNotMatch(html, /<dialog|<a[^>]*><button/);
	assert.match(html, /href="https:\/\/example.com\/full-image.png"[^>]*><img/);
});

test("feature sections start open, maintenance sections start closed, and unrelated headings remain plain", async () => {
	const notes = "### Bug Fixes\n\n* A correction.\n\n### Features\n\nA visible improvement. " +
		"[Jump to features](#features)\n\n`ai-status update`\n\n### Details\n\nMore context.\n\n" +
		"### Dependencies\n\n* Updated dependency.";
	const html = renderToStaticMarkup(await renderMarkdown(notes, { release, headingPrefix: "release-1-" }));
	assert.match(html, /<details class="changelog-section"><summary><h3 id="release-1-bug-fixes">Bug Fixes/);
	assert.match(html, /A correction/);
	assert.match(html, /<details class="changelog-section" open=""><summary><h3 id="release-1-features">Features/);
	assert.match(html, /A visible improvement/);
	assert.match(html, /href="#release-1-features"/);
	assert.match(html, /<code>ai-status update<\/code>/);
	assert.match(html, /<\/details>[\s\S]*<h3 id="release-1-details">Details<\/h3>/);
	assert.match(html, /More context/);
	assert.match(html, /<details class="changelog-section"><summary><h3 id="release-1-dependencies">Dependencies/);
	assert.match(html, /Updated dependency/);
	assert.equal((html.match(/open=""/g) ?? []).length, 1);
});

test("GFM footnotes and accessible references stay within their own release", async () => {
	const notes = "A change with a note.[^1]\n\n[^1]: More details.";
	const first = renderToStaticMarkup(await renderMarkdown(notes, { release, headingPrefix: "release-1-" }));
	const second = renderToStaticMarkup(await renderMarkdown(notes, { release, headingPrefix: "release-2-" }));
	assert.match(first, /id="release-1-user-content-fn-1"/);
	assert.match(second, /id="release-2-user-content-fn-1"/);
	assert.match(first, /href="#release-1-user-content-fn-1"/);
	assert.match(first, /href="#release-1-user-content-fnref-1"/);
	assert.match(first, /aria-describedby="release-1-footnote-label"/);
	assert.match(first, /id="release-1-footnote-label"/);
});

test("Unicode local fragments target their release while unmatched and malformed fragments are preserved", async () => {
	const notes = "### Correções\n\n[Unicode](#correções) [Encoded](#corre%C3%A7%C3%B5es) " +
		"[Unmatched](#ausência) [Malformed](#bad%ZZ) [Incomplete](#bad%C3)";
	const html = renderToStaticMarkup(await renderMarkdown(notes, { release, headingPrefix: "release-1-section-" }));
	assert.match(html, /id="release-1-section-correções"/);
	assert.match(html, /href="#release-1-section-correções">Unicode/);
	assert.match(html, /href="#release-1-section-correções">Encoded/);
	assert.match(html, /href="#aus%C3%AAncia">Unmatched/);
	assert.match(html, /href="#bad%ZZ">Malformed/);
	assert.match(html, /href="#bad%C3">Incomplete/);
});
