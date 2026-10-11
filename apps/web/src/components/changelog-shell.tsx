import type { ReactNode } from "react";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";

export function ChangelogShell({ children, className }: { children: ReactNode; className: string }) {
	return (
		<div className={`changelog ${className}`}>
			<a href="#changelog-content" className="changelog-skip">Skip to content</a>
			<div className="mx-auto max-w-7xl px-6 py-6 sm:py-16">
				<div className="font-sans"><Header /></div>
				{children}
				<div className="font-sans"><Footer /></div>
			</div>
		</div>
	);
}
