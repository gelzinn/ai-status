import { HighlightedCodeBlock } from "./code-highlight";
import { InstallTabs } from "./install-tabs";
import { site, repo } from "@/lib/env";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { GithubIcon } from "@/components/github-icon";

export function Cta() {
	const installCmd = `curl -fsSL ${site.installUrl} | bash`;
	const installCmdMac = `curl -fsSL ${site.installUrlMac} | bash`;
	return (
		<section className="relative mt-24 overflow-hidden rounded-3xl border border-border bg-card/40 p-6 sm:text-center sm:px-16 sm:py-20">
			{/* Grid pattern */}
      <div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_70%_at_50%_50%,#000_10%,transparent_80%)] opacity-30" />

			{/* Ambient glow */}
			<div className="pointer-events-none absolute left-1/2 top-1/2 h-72 w-full max-w-xl -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/5 blur-[100px]" />

			<div className="relative z-10 flex flex-col sm:items-center gap-8">
				<div className="flex flex-col sm:items-center gap-4">
					<span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur-md">
						<span className="relative flex size-1.5">
							<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-foreground/40" />
							<span className="relative inline-flex size-1.5 rounded-full bg-foreground/70" />
						</span>
						Ready in seconds
					</span>

					<div className="flex flex-col sm:items-center gap-3">
						<h2 className="font-heading text-3xl font-semibold tracking-tight text-balance text-foreground sm:text-4xl">
							Ready to monitor your AI?
						</h2>
						<p className="max-w-md text-base text-muted-foreground sm:text-lg">
							One command installs the module and keeps it updated
							automatically.
						</p>
					</div>
				</div>

				<div className="w-full max-w-xl text-left">
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
								code={installCmdMac}
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

				<div className="flex w-full flex-col items-center justify-center gap-3 sm:flex-row sm:gap-4">
					<a
						href={repo.url}
						target="_blank"
						rel="noreferrer"
						className="flex w-full items-center justify-center gap-2 rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-background transition-colors hover:bg-foreground/90 sm:w-auto"
					>
						<GithubIcon className="size-4" />
						Star on GitHub
					</a>
					<Link
						href="/providers"
						className="flex w-full items-center justify-center gap-2 rounded-full border border-border bg-background px-5 py-2.5 text-sm font-medium transition-colors hover:bg-muted sm:w-auto"
					>
						View Providers
						<ArrowRight className="size-4" />
					</Link>
				</div>
			</div>
		</section>
	);
}
