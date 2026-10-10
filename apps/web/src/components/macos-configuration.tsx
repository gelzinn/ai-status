import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { HighlightedCodeBlock } from "@/components/code-highlight";
import { site } from "@/lib/env";

export function MacosConfiguration() {
  return (
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">macOS Setup</h2>
        <p className="max-w-xl text-muted-foreground">
          AI Status runs in your menu bar with a native usage panel, provider settings,
          reset-credit details and About page, following the same layout as Windows and Omarchy.
        </p>
      </div>
      <HighlightedCodeBlock
        code={`curl -fsSL ${site.installUrlMac} | bash`}
        lang="bash"
        label="Install the native menu bar app"
      />
      <p className="text-sm text-muted-foreground">
        Requires macOS 13 or newer, Python 3.10 or newer and the Xcode Command Line Tools.
        The installer builds the app locally. Install the tools with <code>xcode-select --install</code>
        {" "}if needed, then run the command again.
      </p>
      <p className="text-sm text-muted-foreground">
        Sign in through your provider apps or CLIs. Click the menu bar item to see usage;
        choose a provider or limit to keep it visible. Refresh and Settings sit in the panel header.
        Re-run the installer to update while keeping your preferences.
      </p>
      <p className="text-sm text-muted-foreground">
        SwiftBar remains available as an optional integration with <code>--mode stream</code>
        {" "}or <code>--mode periodic</code>.
      </p>
      <Link href="/macos/llms.txt" className="inline-flex w-fit items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">
        macOS installation and provider setup <ArrowRight className="size-3.5" />
      </Link>
    </section>
  );
}
