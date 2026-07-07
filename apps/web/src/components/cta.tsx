import { HighlightedCodeBlock } from "./code-highlight";
import { InstallTabs } from "./install-tabs";
import { REPO_URL, REPO_RAW_INSTALL_URL } from "@/lib/env";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { GithubIcon } from "@/components/github-icon";

export function Cta() {
	const installCmd = `curl -fsSL ${REPO_RAW_INSTALL_URL} | bash`;
	return (
		<section className="relative flex flex-col items-center gap-8 rounded-3xl sm:rounded-[2rem] border border-border bg-card/50 px-6 py-12 sm:p-16 sm:py-24 text-center mt-24 overflow-hidden shadow-2xl">
			{/* Ambient Glowing Background */}
			<div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-[600px] h-full max-h-[400px] bg-foreground/5 blur-[100px] rounded-full pointer-events-none" />
			
			{/* Grid Pattern */}
			<div className="absolute inset-0 z-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_80%_80%_at_50%_50%,#000_20%,transparent_100%)] opacity-20 pointer-events-none" />
			
			<div className="relative z-10 flex flex-col items-center gap-4">
				<h2 className="font-heading text-3xl sm:text-5xl font-bold tracking-tight text-balance text-foreground">
					Ready to monitor your AI?
				</h2>
				<p className="max-w-xl text-base sm:text-xl text-muted-foreground">
					One simple command installs the module and keeps it updated automatically. Start tracking in seconds.
				</p>
			</div>
			
			<div className="relative z-10 w-full max-w-2xl mt-4 text-left">
				<InstallTabs
					align="center"
					linux={
						<HighlightedCodeBlock
							code={installCmd}
							lang="bash"
							label="bash"
							className="w-full m-0!"
						/>
					}
					mac={
						<HighlightedCodeBlock
							code="# macOS support is coming soon! Stay tuned."
							lang="bash"
							label="bash"
							className="w-full m-0!"
						/>
					}
					win={
						<HighlightedCodeBlock
							code="# Windows support is coming soon! Stay tuned."
							lang="bash"
							label="bash"
							className="w-full m-0!"
						/>
					}
				/>
			</div>

			<div className="relative z-10 flex w-full flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 mt-6">
				<a
					href={REPO_URL}
					target="_blank"
					rel="noreferrer"
					className="flex w-full sm:w-auto items-center justify-center gap-2 rounded-full bg-foreground px-8 py-3 text-sm font-semibold text-background transition-colors hover:bg-foreground/90 shadow-sm"
				>
					<GithubIcon className="size-4" />
					Star on GitHub
				</a>
				<Link
					href="/providers"
					className="flex w-full sm:w-auto items-center justify-center gap-2 rounded-full border border-border bg-background px-8 py-3 text-sm font-semibold transition-colors hover:bg-muted shadow-sm"
				>
					View Providers
					<ArrowRight className="size-4" />
				</Link>
			</div>
		</section>
	);
}
