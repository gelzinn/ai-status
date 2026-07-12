import { HighlightedCodeBlock } from "@/components/code-highlight";
import { ArrowRight, ArrowRightIcon } from "lucide-react";
import { site } from "@/lib/env";
import { InstallTabs } from "@/components/install-tabs";
import Link from "next/link";

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

      <Link
        href="/llms.txt"
        className="inline-flex items-center gap-1 text-sm font-medium text-foreground hover:text-muted-foreground transition-colors w-fit mt-1"
      >
        Copy-paste install guide for LLMs <ArrowRight className="size-3.5" />
      </Link>
		</section>
	);
}
