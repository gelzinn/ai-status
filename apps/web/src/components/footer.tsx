import { GithubIcon } from "./github-icon";
import { Logo } from "./logo";
import { PROJECT_NAME, REPO_URL } from "@/lib/env";

export function Footer() {
	return (
		<footer className="flex flex-col sm:flex-row items-center justify-between gap-6 border-t border-border/40 pb-8 pt-8 mt-16 text-sm text-muted-foreground">
			<div className="flex items-center gap-2 font-mono font-medium opacity-70 hover:opacity-100 transition-opacity">
				<Logo className="size-4" />
				<span>{PROJECT_NAME}</span>
			</div>
			<div className="flex items-center gap-6">
				<span className="font-mono text-xs opacity-50">MIT License</span>
				<a href={REPO_URL} target="_blank" rel="noreferrer" className="flex items-center gap-2 hover:text-foreground transition-colors">
					<GithubIcon className="size-4" />
					GitHub
				</a>
			</div>
		</footer>
	);
}
