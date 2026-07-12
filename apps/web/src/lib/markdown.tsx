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
import { CodeBlock } from "@/components/code-block";

/** Concatenate a hast node's text — the raw code, for the copy button. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function hastText(node: any): string {
	if (!node) return "";
	if (node.type === "text") return node.value ?? "";
	if (Array.isArray(node.children)) return node.children.map(hastText).join("");
	return "";
}

const components: Partial<Components> = {
	// External links open in a new tab; in-app links stay put.
	a: ({ href, children, ...rest }) => {
		const external = typeof href === "string" && /^https?:\/\//.test(href);
		return (
			<a
				href={href}
				{...(external ? { target: "_blank", rel: "noreferrer" } : {})}
				{...rest}
			>
				{children}
			</a>
		);
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
export async function renderMarkdown(md: string): Promise<ReactNode> {
	const file = await unified()
		.use(remarkParse)
		.use(remarkGfm)
		.use(remarkRehype)
		.use(rehypeShiki, { theme: CODE_THEME, addLanguageClass: true })
		.use(rehypeReact, { Fragment, jsx, jsxs, components, passNode: true })
		.process(md);

	return file.result;
}
