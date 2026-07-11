import { HighlightedCodeBlock } from "@/components/code-highlight";
import { ArrowRightIcon } from "lucide-react";
import { site } from "@/lib/env";
import { InstallTabs } from "@/components/install-tabs";

export function Hero() {
	const installCmd = `curl -fsSL ${site.installUrl} | bash`;
	return (
		<section className="flex flex-col gap-8">
			<h1 className="font-heading max-w-2xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl motion-safe:animate-fade-up">
				Monitor your AI usage in Waybar
			</h1>
			<p className="max-w-xl text-lg text-muted-foreground motion-safe:animate-fade-up [animation-delay:100ms]">
				Track API usage limits across Claude, Copilot, Codex, Z.AI, Kiro, Antigravity, and OpenCode in real time.
			</p>
			<InstallTabs
				linux={
					<HighlightedCodeBlock
						code={installCmd}
						lang="bash"
						label="bash"
						className="w-full"
					/>
				}
				mac={
					<HighlightedCodeBlock
						code="# macOS support is coming soon! Stay tuned."
						lang="bash"
						label="bash"
						className="w-full"
					/>
				}
				win={
					<HighlightedCodeBlock
						code="# Windows support is coming soon! Stay tuned."
						lang="bash"
						label="bash"
						className="w-full"
					/>
				}
			/>
		</section>
	);
}
