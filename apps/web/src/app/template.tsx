"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

/**
 * Single global template for route-change animations. A root template doesn't
 * re-mount on its own when only a nested dynamic leaf changes (e.g.
 * /providers/claude → /providers/codex), so we key the wrapper by pathname:
 * the div remounts on every URL change and replays `animate-page-in` — one
 * template, no nesting, no doubling.
 *
 * `animate-page-in` uses `translate` (not `transform`) with no `forwards` fill,
 * so nothing lingers to break sticky/fixed descendants once it ends.
 */
export default function Template({ children }: { children: ReactNode }) {
	const pathname = usePathname();
	return (
		<div key={pathname} className="motion-safe:animate-page-in">
			{children}
		</div>
	);
}
