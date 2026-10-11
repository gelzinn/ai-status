import Link from "next/link";
import { ArrowRight, Download, KeyRound, MousePointer2, Power } from "lucide-react";
import { HighlightedCodeBlock } from "@/components/code-highlight";
import { site } from "@/lib/env";

export function MacosConfiguration() {
  return (
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">macOS Setup</h2>
        <p className="max-w-xl text-muted-foreground">
          Install {site.name}, connect your accounts and keep usage a click away
          in your menu bar.
        </p>
      </div>

      <div className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card">
        {[
          {
            icon: Download,
            title: "Install and launch",
            description: <>Requires macOS 13 or newer, Python 3.10 or newer and Xcode Command Line Tools. Install the tools with <code>xcode-select --install</code>, then run the command below. The installer builds and starts the native menu bar app.</>,
          },
          {
            icon: KeyRound,
            title: "Connect your providers and accounts",
            description: <>Sign in through your providers’ apps or CLIs, or configure their API credentials. Manage additional accounts with <code>~/.local/bin/ai-status accounts</code>. Each connection keeps its own label and credential source.</>,
          },
          {
            icon: MousePointer2,
            title: "Open your usage panel",
            description: <>Click the menu bar item to see quota bars, reset timers, API costs and balances. Select a connection or metric to update the menu bar. Use Refresh to check immediately, or Settings to enable and reorder connections and choose the icon and displayed fields, including Usage value.</>,
          },
          {
            icon: Power,
            title: "Start at sign-in and keep updated",
            description: <>The installer starts the app at sign-in. Pass <code>--no-autostart</code> to disable that behavior. Re-run the installer to update while keeping your preferences, or pass <code>--rollback</code> to restore the previous installation.</>,
          },
        ].map(({ icon: Icon, title, description }, index) => (
          <div key={title} className="flex gap-4 border-border p-4 not-first:border-t">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background">
              <Icon className="size-4 text-muted-foreground" />
            </div>
            <div className="flex min-w-0 flex-col gap-2">
              <h3 className="font-heading text-sm font-semibold">
                <span className="mr-2 text-muted-foreground">0{index + 1}</span>
                {title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
            </div>
          </div>
        ))}
      </div>

      <HighlightedCodeBlock
        code={`curl -fsSL ${site.installUrlMac} | bash`}
        lang="bash"
        label="Install the native menu bar app"
      />

      <p className="text-sm leading-relaxed text-muted-foreground">
        Usage refreshes every five minutes. Settings changes apply when you save.
        SwiftBar is available separately with <code>--mode stream</code> or
        {" "}<code>--mode periodic</code>.
      </p>

      <Link href="/macos" className="inline-flex w-fit items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">
        macOS setup and provider compatibility <ArrowRight className="size-3.5" />
      </Link>
    </section>
  );
}
