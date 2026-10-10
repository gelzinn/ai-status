import { HighlightedCodeBlock } from "@/components/code-highlight";
import { ArrowRight } from "lucide-react";
import { site } from "@/lib/env";
import { InstallTabs } from "@/components/install-tabs";
import Link from "next/link";
import { WindowsInstall } from "@/components/windows-install";
import { PlatformContent } from "@/components/install-platform";

export function Hero() {
	const installCmd = `curl -fsSL ${site.installUrl} | bash`;
	return (
		<section className="flex flex-col gap-8">
			<h1 className="font-heading max-w-2xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl motion-safe:animate-fade-up">
				Monitor your AI usage on your desktop
			</h1>
			<p className="max-w-xl text-lg text-muted-foreground motion-safe:animate-fade-up [animation-delay:100ms]">
				Track API usage limits across Claude, Copilot, Codex, Z.AI, Kiro, Antigravity, OpenCode, and Command Code in real time.
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
				win={<WindowsInstall />}
      />

      <PlatformContent
        linux={<Link href="/llms.txt" className="inline-flex w-fit items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">Copy-paste install guide for LLMs <ArrowRight className="size-3.5" /></Link>}
        windows={<Link href="/windows/llms.txt" className="inline-flex w-fit items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">Copy-paste Windows guide for LLMs <ArrowRight className="size-3.5" /></Link>}
      />
		</section>
	);
}
