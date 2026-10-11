import type { ReactNode } from "react";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";

export function ChangelogShell({ children, className }: { children: ReactNode; className: string }) {
	return (
		<div className={`changelog ${className}`}>
			<a href="#changelog-content" className="changelog-skip">Skip to content</a>
			<div className="mx-auto max-w-7xl px-6 pt-6 font-sans sm:pt-16">
				<Header />
			</div>
			{children}
			<div className="mx-auto max-w-7xl px-6 pb-6 font-sans sm:pb-16">
				<Footer />
			</div>
		</div>
	);
}
