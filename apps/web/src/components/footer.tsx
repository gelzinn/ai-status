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

			<div className="flex items-center gap-6">
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
