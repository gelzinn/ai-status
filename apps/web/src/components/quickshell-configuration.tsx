import { HighlightedCodeBlock } from "@/components/code-highlight";
import { site, repo } from "@/lib/env";

export function QuickshellConfiguration() {
  return (
<section className="flex flex-col gap-8">
            <div className="flex flex-col gap-3">
              <h2 className="font-heading text-2xl font-semibold tracking-tight">
                Omarchy Quickshell
              </h2>
              <p className="max-w-xl text-muted-foreground">
                On the new Omarchy desktop, AI Status is a native bar widget.
                Click to open a usage panel with all your providers, limits,
                reset timers, and a refresh button.
              </p>
            </div>
            <HighlightedCodeBlock
              code={`omarchy plugin add ${repo.url}.git --enable`}
              lang="bash"
              label="Install directly with Omarchy"
            />
            <p className="text-sm text-muted-foreground">
              The plugin includes its Python backend and uses your existing
              provider logins. No separate AI Status install is required.
              Right-click to open settings inside the panel, scroll to switch provider,
              and middle-click to cycle through limits.
            </p>
            <HighlightedCodeBlock
              code={`curl -fsSL ${site.installUrl} | bash -s -- --bar quickshell --configure-bar true --no-interactive`}
              lang="bash"
              label="Install with the AI Status CLI"
            />
            <p className="text-sm text-muted-foreground">
              The regular installer detects your active bar. You can also select
              Waybar or Quickshell in the wizard, or pass <code>--bar waybar</code>
              {" "}or <code>--bar quickshell</code>. It configures only the bar you choose.
            </p>
          </section>
  );
}
