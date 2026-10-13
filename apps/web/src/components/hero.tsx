import { HighlightedCodeBlock } from "@/components/code-highlight";
import { ArrowRight } from "lucide-react";
import { site } from "@/lib/env";
import { InstallTabs } from "@/components/install-tabs";
import Link from "next/link";
import { WindowsInstall } from "@/components/windows-install";
import { PlatformContent } from "@/components/install-platform";

export function Hero() {
	const installCmd = `curl -fsSL ${site.installUrl} | bash`;
	const installCmdMac = `curl -fsSL ${site.installUrlMac} | bash`;
	return (
		<section className="flex flex-col gap-8">
			<h1 className="font-heading max-w-2xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl motion-safe:animate-fade-up">
				Monitor your AI usage on your desktop
			</h1>
			<p className="max-w-xl text-lg text-muted-foreground motion-safe:animate-fade-up [animation-delay:100ms]">
				Track usage limits across Claude, Copilot, Codex, Z.AI, Kiro, Antigravity, OpenCode, and Command Code. Choose automatic refresh from 5 to 60 minutes.
      </p>

			<InstallTabs
				linux={
					<HighlightedCodeBlock
						code={installCmd}
						lang="bash"
						label="bash"
						className="w-full [&_pre]:leading-[21px]"
					/>
				}
				mac={
					<HighlightedCodeBlock
						code={installCmdMac}
						lang="bash"
						label="bash"
						className="w-full [&_pre]:leading-[21px]"
					/>
				}
				win={<WindowsInstall />}
      />

      <PlatformContent
        linux={<Link href="/linux/llms.txt" className="inline-flex w-fit items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">Copy-paste Linux guide for LLMs <ArrowRight className="size-3.5" /></Link>}
        mac={<Link href="/macos/llms.txt" className="inline-flex w-fit items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">Copy-paste macOS guide for LLMs <ArrowRight className="size-3.5" /></Link>}
        windows={<Link href="/windows/llms.txt" className="inline-flex w-fit items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">Copy-paste Windows guide for LLMs <ArrowRight className="size-3.5" /></Link>}
      />
		</section>
	);
}
