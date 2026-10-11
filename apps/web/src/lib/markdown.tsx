import { Fragment, type ReactNode } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeShiki from "@shikijs/rehype";
import rehypeReact from "rehype-react";
import type { Components } from "hast-util-to-jsx-runtime";
import { CODE_THEME } from "./highlight";
import { LIB_NAME, site } from "./env";
import { CodeBlock } from "@/components/code-block";
import { ChangelogImage } from "@/components/changelog-image";

/** Concatenate a hast node's text — the raw code, for the copy button. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function hastText(node: any): string {
	if (!node) return "";
	if (node.type === "text") return node.value ?? "";
	if (Array.isArray(node.children)) return node.children.map(hastText).join("");
	return "";
}

/** Keep guide fragments usable without introducing another rendering dependency. */
function guideHeadingIds({ prefix = "" }: { prefix?: string }) {
	return (tree: { children?: unknown[] }) => {
		const used = new Set<string>();
		const fragments = new Map<string, string>();
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		function visit(node: any) {
			const existingId = typeof node.properties?.id === "string" ? node.properties.id : undefined;
			if (node.type === "element" && /^h[1-6]$/.test(node.tagName)) {
				const base = existingId ?? hastText(node).toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, "").replace(/\s/g, "-");
				let id = base;
				let suffix = 0;
				while (used.has(id)) id = `${base}-${++suffix}`;
				used.add(id);
				fragments.set(id, `${prefix}${id}`);
				if (existingId) fragments.set(existingId, `${prefix}${id}`);
				node.properties = { ...node.properties, id: `${prefix}${id}` };
			} else if (existingId && prefix) {
				fragments.set(existingId, `${prefix}${existingId}`);
				node.properties.id = `${prefix}${existingId}`;
			}
			for (const child of node.children ?? []) visit(child);
		}
		visit(tree);
		// Release sections often reuse the same heading names. Keep their local
		// links within the corresponding release when articles share a page.
		function linkFragments(node: any) {
			const href = node.properties?.href;
			if (typeof href === "string" && href.startsWith("#")) {
				let fragment = href.slice(1);
				try {
					// remark encodes Unicode in hrefs while heading IDs retain it.
					fragment = decodeURIComponent(fragment);
				} catch {
					// A malformed fragment stays as authored, without failing the page.
				}
				if (fragments.has(fragment)) node.properties.href = `#${fragments.get(fragment)}`;
			}
			for (const property of ["ariaDescribedBy", "ariaLabelledBy"]) {
				const value = node.properties?.[property];
				if (Array.isArray(value)) node.properties[property] = value.map((id) => fragments.get(id) ?? id);
				else if (typeof value === "string") node.properties[property] = value.split(/\s+/).map((id) => fragments.get(id) ?? id).join(" ");
			}
			for (const child of node.children ?? []) linkFragments(child);
		}
		if (prefix) linkFragments(tree);
	};
}

type MarkdownOptions = {
	headingPrefix?: string;
	release?: { tagName: string; publishedAt: string };
};

/** Remove only Release Please's redundant first version/date heading. */
function releaseHeading({ release }: MarkdownOptions) {
	return (tree: { children: any[] }) => {
		if (!release) return;
		const first = tree.children[0];
		function text(node: any): string {
			return node.value ?? (node.children ?? []).map(text).join("");
		}
		const version = release.tagName.replace(/^v/, "");
		const date = release.publishedAt.slice(0, 10);
		const versionLink = first?.children?.[0];
		if (first?.type === "heading" && first.depth === 2 &&
			text(first) === `${version} (${date})` && versionLink?.type === "link" &&
			typeof versionLink.url === "string" && versionLink.url.startsWith("https://github.com/") &&
			versionLink.url.includes("/compare/")) {
			tree.children.shift();
		}
	};
}

/** GitHub notes are external input: allow ordinary links and image URLs only. */
function safeMarkdownUrl(value: unknown, image = false): string | undefined {
	if (typeof value !== "string") return undefined;
	const url = value.trim();
	if (!url || /[\u0000-\u0020\u007f]/.test(url)) return undefined;
	if (/^https?:\/\//i.test(url) || (!image && /^mailto:/i.test(url))) return url;
	if (!/^[a-z][a-z\d+.-]*:/i.test(url) && !url.startsWith("//") && !url.includes("\\")) return url;
	return undefined;
}

/** Match the reference's expandable maintenance sections without losing notes. */
function releaseSections({ enabled }: { enabled: boolean }) {
	return (tree: { children: any[] }) => {
		if (!enabled) return;
		function markLinkedImages(node: any, insideLink = false) {
			if (node.type === "element" && node.tagName === "img" && insideLink) {
				node.data = { ...node.data, linked: true };
			}
			for (const child of node.children ?? []) markLinkedImages(child, insideLink || node.tagName === "a");
		}
		markLinkedImages(tree);
		const sections = new Set(["Bug Fixes", "Fixes", "Improvements", "Performance Improvements", "Dependencies", "Reverts"]);
		const children = tree.children;
		const grouped: any[] = [];
		for (let index = 0; index < children.length; index++) {
			const heading = children[index];
			if (heading.type !== "element" || !/^h[23]$/.test(heading.tagName) || !sections.has(hastText(heading))) {
				grouped.push(heading);
				continue;
			}
			const body: any[] = [];
			while (index + 1 < children.length) {
				const next = children[index + 1];
				if (next.type === "element" && /^h[1-6]$/.test(next.tagName) && next.tagName <= heading.tagName) break;
				body.push(children[++index]);
			}
			grouped.push({ type: "element", tagName: "details", properties: { className: ["changelog-section"] }, children: [
				{ type: "element", tagName: "summary", properties: {}, children: [heading] },
				{ type: "element", tagName: "div", properties: {}, children: body },
			] });
		}
		tree.children = grouped;
	};
}

const components: Partial<Components> = {
	// External links open in a new tab; in-app links stay put.
	a: ({ href, children, node, ...rest }) => {
		void node;
		const external = typeof href === "string" && /^https?:\/\//.test(href);
		return (
			<a
				href={safeMarkdownUrl(href)}
				{...(external ? { target: "_blank", rel: "noreferrer" } : {})}
				{...rest}
			>
				{children}
			</a>
		);
	},
	img: ({ src, alt, node, ...rest }) => {
		void node;
		const safe = safeMarkdownUrl(src, true);
		return safe ? <img {...rest} src={safe} alt={alt ?? ""} loading="lazy" /> : null;
	},
	// Fenced code blocks get the SAME chrome as the landing page: shiki does the
	// highlighting (via rehype), and we wrap its <pre> in the shared CodeBlock
	// (label bar + copy button + scroll fade) instead of a bare styled <pre>.
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	pre: ({ node, children, ...rest }: any) => {
		const code = hastText(node);
		// shiki (addLanguageClass) tags the inner <code> with `language-<lang>`
		// (as a `class` array on the hast node).
		const codeEl = node?.children?.find((c: any) => c?.tagName === "code");
		const rawCls = codeEl?.properties?.className ?? codeEl?.properties?.class;
		const classList: string[] = Array.isArray(rawCls)
			? rawCls
			: typeof rawCls === "string"
				? rawCls.split(" ")
				: [];
		const lang = classList
			.find((c) => c.startsWith("language-"))
			?.slice("language-".length);
		return (
			<CodeBlock code={code} label={lang} className="my-5">
				<pre {...rest}>{children}</pre>
			</CodeBlock>
		);
	},
	// Tables get the same chrome as the code blocks: a rounded, bordered card
	// (bg-muted <thead> acting as the header bar) that scrolls inside itself.
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	table: ({ node, children, ...rest }: any) => {
		void node;
		return (
			<div className="my-5 overflow-hidden rounded-2xl border border-border bg-card">
				<div className="overflow-x-auto">
					<table {...rest}>{children}</table>
				</div>
			</div>
		);
	},
};

/**
 * Render a markdown string to React nodes — GFM tables/lists, shiki-highlighted
 * fenced code wrapped in the shared CodeBlock — entirely as real React elements
 * via rehype-react. No HTML string is produced, so nothing is
 * `dangerouslySetInnerHTML`'d.
 *
 * Wrap the returned node in `<div className="md-guide">…</div>` for styling.
 */
export async function renderMarkdown(md: string, options: MarkdownOptions = {}): Promise<ReactNode> {
	const processor = unified()
		.use(remarkParse)
		.use(remarkGfm)
		.use(releaseHeading, options)
		.use(remarkRehype)
		.use(guideHeadingIds, { prefix: options.headingPrefix })
		.use(releaseSections, { enabled: Boolean(options.release) });
	// Ordinary release notes have no code fences. Avoid loading the syntax
	// highlighter on each dynamic request unless there is code to highlight.
	if (!options.release || /`{3}|~{3}/.test(md)) {
		processor.use(rehypeShiki, { theme: CODE_THEME, addLanguageClass: true, fallbackLanguage: "text" });
	}
	const file = await processor.use(rehypeReact, { Fragment, jsx, jsxs, components: options.release ? {
			...components,
			img: ({ src, alt, node }: { src?: string; alt?: string; node?: { data?: { linked?: boolean } } }) => {
				const safe = safeMarkdownUrl(src, true);
				return safe ? <ChangelogImage src={safe} alt={alt ?? ""} zoomable={!node?.data?.linked} /> : null;
			},
		} : components, passNode: true })
		// Guides are authored with the literal names; swap the product name
		// ("AI Status") for site.name and the command/path ("ai-status") for
		// LIB_NAME, so a rename flows through the docs too. (No-op while equal;
		// the two casings never overlap.)
		.process(md.replaceAll("AI Status", site.name).replaceAll("ai-status", LIB_NAME));

	return file.result;
}
