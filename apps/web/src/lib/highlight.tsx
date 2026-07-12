import { codeToHast } from "shiki";
import { toJsxRuntime } from "hast-util-to-jsx-runtime";
import { Fragment, type ReactNode } from "react";
import { jsx, jsxs } from "react/jsx-runtime";

export const CODE_THEME = "vesper";

/**
 * Highlight code to React nodes via shiki's hast output — never an HTML string,
 * so no `dangerouslySetInnerHTML`. The standalone code block uses this directly;
 * the markdown pipeline highlights the same way (shiki via rehype). One shared
 * approach, zero innerHTML.
 */
export async function highlightToReact(
	code: string,
	lang: string,
): Promise<ReactNode> {
	const hast = await codeToHast(code, { lang, theme: CODE_THEME });
	return toJsxRuntime(hast, { Fragment, jsx, jsxs });
}
