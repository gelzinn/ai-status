"use client";

import {
	createContext,
	useContext,
	useEffect,
	useState,
	type ReactNode,
} from "react";
import Link from "next/link";
import { Terminal } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * Install CTA that reveals at the top of the sticky sidebar once the hero banner
 * (with its own button) scrolls out of view. The provider tracks the "stuck"
 * state; the sticky button springs in from just above, in the hero's direction.
 */

const StuckContext = createContext(false);

export function InstallCtaProvider({
	heroId,
	children,
}: {
	heroId: string;
	children: ReactNode;
}) {
	const [stuck, setStuck] = useState(false);

	useEffect(() => {
		const hero = document.getElementById(heroId);
		if (!hero) return;
		const observer = new IntersectionObserver(
			([entry]) => setStuck(!entry.isIntersecting),
			{ rootMargin: "-48px 0px 0px 0px", threshold: 0 },
		);
		observer.observe(hero);
		return () => observer.disconnect();
	}, [heroId]);

	return <StuckContext.Provider value={stuck}>{children}</StuckContext.Provider>;
}

function InstallButton({
	href,
	label,
	full,
}: {
	href: string;
	label: string;
	full?: boolean;
}) {
	return (
		<Link
			href={href}
			className={cn(
				"flex items-center justify-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-medium text-black transition-colors hover:bg-white/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
				full && "w-full",
			)}
		>
			<Terminal className="-ml-1 size-4" />
			{label}
		</Link>
	);
}

/** Install button as it sits in the hero banner. */
export function HeroInstallCta({
	href = "/",
	label,
}: {
	href?: string;
	label: string;
}) {
	return <InstallButton href={href} label={label} />;
}

/** Install button revealed at the top of the sticky sidebar (desktop only). */
export function StickyInstallCta({
	href = "/",
	label,
}: {
	href?: string;
	label: string;
}) {
	const stuck = useContext(StuckContext);

	return (
		<AnimatePresence initial={false}>
			{stuck && (
				<motion.div
					key="sticky-install"
					className="hidden overflow-hidden lg:block"
					initial={{ height: 0, opacity: 0, y: -8 }}
					animate={{ height: "auto", opacity: 1, y: 0 }}
					exit={{ height: 0, opacity: 0, y: -8 }}
					transition={{ type: "spring", bounce: 0.15, duration: 0.4 }}
				>
					<InstallButton href={href} label={label} full />
				</motion.div>
			)}
		</AnimatePresence>
	);
}
