import Link from "next/link";
import { GithubIcon } from "@/components/github-icon";
import { Logo } from "@/components/logo";
import { site, repo } from "@/lib/env";
import { cn } from "@/lib/utils";

// Last count we read successfully — reused when a later request fails (rate
// limit / transient error) so the badge doesn't disappear once it has shown.
let cachedStars: number | null = null;

async function getStarCount(): Promise<number | null> {
	try {
		const res = await fetch(repo.apiRepo, {
			headers: {
				// GitHub returns 403 for API requests without a User-Agent.
				"User-Agent": site.name,
				Accept: "application/vnd.github+json",
				// Use a token if one is configured (60/h → 5000/h).
				...(process.env.GITHUB_TOKEN
					? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` }
					: {}),
			},
			// Fetch at most every 6h — one request every few hours stays well
			// under the 60/h anonymous limit, and the value is cached in between.
			next: { revalidate: 21600 },
			signal: AbortSignal.timeout(5000),
		});
		if (res.ok) {
			const data = await res.json();
			if (typeof data.stargazers_count === "number") {
				cachedStars = data.stargazers_count;
			}
		}
	} catch (error) {
		console.error("Failed to fetch GitHub stars:", error);
	}
	return cachedStars;
}

export async function Header() {
	const stars = await getStarCount();

	return (
		<header className="flex items-center justify-between">
			<Link href="/" className="flex items-center gap-2 font-mono text-sm font-medium transition-colors hover:text-muted-foreground">
				<Logo className="size-5" />
				{site.name}
			</Link>
			<div className="flex items-center gap-4 sm:gap-6">
				<Link href="/changelog" className="text-sm text-muted-foreground transition-colors hover:text-foreground">Changelog</Link>
				<a
					href={repo.url}
					target="_blank"
					rel="noreferrer"
					className={cn(
						"flex items-center gap-2 rounded-full bg-white pl-4 py-1.5 text-sm font-medium text-black transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background hover:bg-white/90",
						stars !== null ? "pr-1.5" : "pr-4",
					)}
				>
					<GithubIcon className="-ml-1 size-4" />
					<span className="hidden sm:inline">Star on GitHub</span>
					<span className="sm:hidden">Star</span>
					{stars !== null && (
						<div className="flex items-center justify-center rounded-full bg-black/10 px-2.5 py-1 text-xs font-semibold">
							<span>{stars.toLocaleString()}</span>
						</div>
					)}
				</a>
			</div>
		</header>
	);
}
