import Link from "next/link";
import { GithubIcon } from "./github-icon";
import { Logo } from "./logo";
import { site, repo } from "@/lib/env";

export function Footer() {
	return (
		<footer className="flex flex-col sm:flex-row items-center justify-between gap-6 mt-16 text-sm text-muted-foreground">
			<div className="flex items-center gap-2 font-mono font-medium opacity-70 hover:opacity-100 transition-opacity">
				<Logo className="size-4" />
				<span>{site.name}</span>
			</div>

			<div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
				<nav aria-label="Setup guides" className="flex flex-wrap items-center justify-center gap-4">
					<Link href="/linux" className="transition-colors hover:text-foreground">Linux</Link>
					<Link href="/windows" className="transition-colors hover:text-foreground">Windows</Link>
					<Link href="/macos" className="transition-colors hover:text-foreground">macOS</Link>
					<Link href="/llms.txt" className="transition-colors hover:text-foreground">LLM guide</Link>
					<Link href="/changelog" className="transition-colors hover:text-foreground">Changelog</Link>
				</nav>

				<a href={`${repo.url}/blob/main/LICENSE`} target="_blank" rel="noreferrer" className="font-mono text-xs opacity-50 hover:text-foreground hover:opacity-100 transition-colors">
					MIT License
				</a>

				<a href={repo.url} target="_blank" rel="noreferrer" className="flex items-center gap-2 hover:text-foreground transition-colors">
					<GithubIcon className="size-4" />
					GitHub
				</a>
			</div>
		</footer>
	);
}
