import { GithubIcon } from "@/components/github-icon";
import { Logo } from "@/components/logo";
import { site, repo } from "@/lib/env";

export async function Header() {
	let stars = null;
	try {
		const res = await fetch("https://api.github.com/repos/gelzinn/ai-status", {
			next: { revalidate: 3600 },
		});
		if (res.ok) {
			const data = await res.json();
			stars = data.stargazers_count;
		}
	} catch (error) {
		console.error("Failed to fetch GitHub stars:", error);
	}

	return (
		<header className="flex items-center justify-between">
			<span className="flex items-center gap-2 font-mono text-sm font-medium">
				<Logo className="size-5" />
				{site.name}
			</span>
			<a
				href={repo.url}
				target="_blank"
				rel="noreferrer"
				className="flex items-center gap-2 rounded-full bg-white pl-4 pr-1.5 py-1.5 text-sm font-medium text-black transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background hover:bg-white/90"
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
		</header>
	);
}
