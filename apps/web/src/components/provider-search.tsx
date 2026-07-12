"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Check, ChevronDown, KeyRound, Plus, Search } from "lucide-react";
import { repo } from "@/lib/env";
import { cn } from "@/lib/utils";
import type { Provider } from "@ai-status/shared";

/** Chips: how each provider authenticates (from `authType`). */
const AUTH_FILTERS: { id: string; label: string; authType?: string }[] = [
	{ id: "all", label: "All" },
	{ id: "cli", label: "Native CLI", authType: "cli" },
	{ id: "opencode", label: "Via OpenCode", authType: "opencode" },
	{ id: "scraping", label: "Scraping", authType: "scraping" },
];

/** Select: which usage period a provider tracks (derived from `tracks`). */
const PERIOD_FILTERS: { id: string; label: string; keywords?: string[] }[] = [
	{ id: "all", label: "Any period" },
	{ id: "rolling", label: "5-hour", keywords: ["5-hour", "5h", "rolling", "session"] },
	{ id: "weekly", label: "Weekly", keywords: ["weekly"] },
	{ id: "monthly", label: "Monthly", keywords: ["monthly"] },
];

// Shared control height so the input, chips and dropdown line up.
const CONTROL = "h-10 rounded-full border text-sm transition-colors";

/**
 * Custom period dropdown — a native <select> renders its text baseline and
 * open menu differently from the pill chips, so we roll our own trigger
 * (identical to a chip) plus a card-styled menu.
 */
function PeriodDropdown({
	value,
	onChange,
}: {
	value: string;
	onChange: (id: string) => void;
}) {
	const [open, setOpen] = useState(false);
	const ref = useRef<HTMLDivElement>(null);
	const current = PERIOD_FILTERS.find((p) => p.id === value) ?? PERIOD_FILTERS[0];
	const active = value !== "all";

	useEffect(() => {
		if (!open) return;
		const onPointer = (e: MouseEvent) => {
			if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
		};
		const onKey = (e: KeyboardEvent) => {
			if (e.key === "Escape") setOpen(false);
		};
		document.addEventListener("mousedown", onPointer);
		document.addEventListener("keydown", onKey);
		return () => {
			document.removeEventListener("mousedown", onPointer);
			document.removeEventListener("keydown", onKey);
		};
	}, [open]);

	return (
		<div ref={ref} className="relative shrink-0 sm:ml-auto">
			<button
				type="button"
				onClick={() => setOpen((o) => !o)}
				aria-haspopup="listbox"
				aria-expanded={open}
				aria-label="Filter by tracked period"
				className={cn(
					CONTROL,
					"flex items-center gap-2 pl-4 pr-3 font-medium",
					active
						? "border-transparent bg-foreground text-background"
						: "border-border bg-card text-muted-foreground hover:bg-card hover:text-foreground",
				)}
			>
				{current.label}
				<ChevronDown
					className={cn("size-4 transition-transform", open && "rotate-180")}
				/>
			</button>

			{open && (
				<div
					role="listbox"
					className="absolute left-0 z-20 mt-2 min-w-[11rem] overflow-hidden rounded-2xl border border-border bg-card p-1 shadow-lg sm:left-auto sm:right-0"
				>
					{PERIOD_FILTERS.map((p) => (
						<button
							key={p.id}
							type="button"
							role="option"
							aria-selected={p.id === value}
							onClick={() => {
								onChange(p.id);
								setOpen(false);
							}}
							className={cn(
								"flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left text-sm transition-colors",
								p.id === value
									? "bg-muted text-foreground"
									: "text-muted-foreground hover:bg-muted hover:text-foreground",
							)}
						>
							{p.label}
							{p.id === value && <Check className="size-3.5 shrink-0" />}
						</button>
					))}
				</div>
			)}
		</div>
	);
}

/** Search + filters (auth-method chips × tracked-period select) + live count. */
export function ProviderSearch({ providers }: { providers: Provider[] }) {
	const [query, setQuery] = useState("");
	const [authFilter, setAuthFilter] = useState("all");
	const [periodFilter, setPeriodFilter] = useState("all");
	const q = query.trim().toLowerCase();

	const filtered = useMemo(() => {
		const authType = AUTH_FILTERS.find((f) => f.id === authFilter)?.authType;
		const keywords = PERIOD_FILTERS.find((f) => f.id === periodFilter)?.keywords;
		return providers.filter((p) => {
			const matchesQuery =
				!q ||
				[p.name, p.tracks, p.auth].some((f) => f.toLowerCase().includes(q));
			const matchesAuth = !authType || p.authType === authType;
			const matchesPeriod =
				!keywords || keywords.some((k) => p.tracks.toLowerCase().includes(k));
			return matchesQuery && matchesAuth && matchesPeriod;
		});
	}, [providers, q, authFilter, periodFilter]);

	const isFullList = !q && authFilter === "all" && periodFilter === "all";

	// Edge fade for the chip strip when it scrolls horizontally (mobile only).
	// Each side is full width (MAX) whenever it has room to scroll, so both fades
	// match; the CSS transition eases them in/out instead of popping.
	const chipsRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const el = chipsRef.current;
		if (!el) return;
		const MAX = 96; // 6rem — matches the page's horizontal padding
		const update = () => {
			const max = el.scrollWidth - el.clientWidth;
			const left = el.scrollLeft > 1 ? MAX : 0;
			const right = max - el.scrollLeft > 1 ? MAX : 0;
			el.style.setProperty("--fade-left", `${left}px`);
			el.style.setProperty("--fade-right", `${right}px`);
		};
		update();
		el.addEventListener("scroll", update, { passive: true });
		const observer = new ResizeObserver(update);
		observer.observe(el);
		return () => {
			el.removeEventListener("scroll", update);
			observer.disconnect();
		};
	}, []);

	return (
		<div className="flex flex-col gap-6">
			{/* Search + count */}
			<div className="flex flex-col gap-4">
				<div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
					<div className="relative w-full sm:max-w-sm">
						<Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
						<input
							type="text"
							value={query}
							onChange={(e) => setQuery(e.target.value)}
							placeholder="Search providers…"
							aria-label="Search providers"
							className={cn(
								CONTROL,
								"w-full border-border bg-card pl-10 pr-4 text-foreground outline-none placeholder:text-muted-foreground/70 focus:border-foreground/30 focus:bg-card",
							)}
						/>
					</div>

					<span className="hidden shrink-0 text-sm text-muted-foreground tabular-nums sm:block">
						{filtered.length} {filtered.length === 1 ? "provider" : "providers"}
						{!isFullList && (
							<span className="text-muted-foreground/60"> of {providers.length}</span>
						)}
					</span>
				</div>

				{/* Filters: auth-method chips + period dropdown.
				    Mobile: chips scroll in a single swipeable row, dropdown drops below. */}
				<div className="flex flex-col gap-2 sm:flex-row sm:items-center">
					<div
						ref={chipsRef}
						className="scroll-fade-x-live -mx-6 flex gap-2 overflow-x-auto px-6 pb-1 [-ms-overflow-style:none] [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0 [&::-webkit-scrollbar]:hidden"
						role="group"
						aria-label="Filter by auth method"
					>
						{AUTH_FILTERS.map((f) => (
							<button
								key={f.id}
								type="button"
								onClick={() => setAuthFilter(f.id)}
								aria-pressed={authFilter === f.id}
								className={cn(
									CONTROL,
									"shrink-0 px-4 font-medium",
									authFilter === f.id
										? "border-transparent bg-foreground text-background"
										: "border-border bg-card text-muted-foreground hover:bg-card hover:text-foreground",
								)}
							>
								{f.label}
							</button>
						))}
					</div>

					<PeriodDropdown value={periodFilter} onChange={setPeriodFilter} />
				</div>
			</div>

			{/* Grid */}
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
				{filtered.map((provider) => (
					<Link
						key={provider.name}
						href={`/providers/${provider.slug}`}
						className="group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm backdrop-blur-md transition-transform hover:-translate-y-0.5 hover:bg-card hover:shadow-md"
					>
						<div className="flex flex-col gap-4 p-4">
							<header className="flex items-center gap-3">
								<div className="flex [--tile:2.75rem] size-(--tile) shrink-0 items-center justify-center rounded-[calc(var(--tile)/4)] border border-border bg-background shadow-sm">
									<img
										src={provider.logo}
										alt={provider.name}
										className="[--logo:1.5rem] size-(--logo) rounded-[calc(var(--logo)/6)] object-contain"
									/>
								</div>
								<h2 className="font-heading text-lg font-semibold text-foreground">
									{provider.name}
								</h2>
							</header>

							<p className="flex-1 text-sm leading-relaxed text-muted-foreground">
								{provider.tracks}
							</p>
						</div>

						<footer className="mt-auto flex items-center gap-1.5 border-t border-border bg-muted p-4 text-xs text-muted-foreground/80">
							<KeyRound className="size-3.5 shrink-0" />
							<span className="truncate font-mono" title={provider.auth}>
								{provider.auth}
							</span>
						</footer>
					</Link>
				))}

				{/* Add provider — only in the full, unfiltered list */}
				{isFullList && (
					<a
						href={`${repo.url}/issues/new`}
						target="_blank"
						rel="noreferrer"
						className="group flex min-h-40 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border/60 bg-transparent p-5 text-center transition-all hover:border-foreground/30 hover:bg-card/40"
					>
						<span className="flex size-10 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground transition-colors group-hover:text-foreground">
							<Plus className="size-5" />
						</span>
						<span className="font-heading text-base font-semibold text-muted-foreground transition-colors group-hover:text-foreground">
							Add a provider
						</span>
						<span className="text-xs text-muted-foreground/70">
							Open an issue on GitHub
						</span>
					</a>
				)}
			</div>

			{/* Empty state */}
			{filtered.length === 0 && (
				<div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-border/60 py-12 text-center">
					<span className="text-sm text-muted-foreground">
						No providers match your search.
					</span>
					<a
						href={`${repo.url}/issues/new`}
						target="_blank"
						rel="noreferrer"
						className="text-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
					>
						Request one on GitHub
					</a>
				</div>
			)}
		</div>
	);
}
