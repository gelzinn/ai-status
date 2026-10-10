import Link from "next/link";
import { ArrowRight, Download, Settings2, MousePointer2 } from "lucide-react";
import { site } from "@/lib/env";

export function WindowsConfiguration() {
  return (
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">
          Windows Setup
        </h2>
        <p className="max-w-xl text-muted-foreground">
          Install {site.name}, connect your providers and keep usage a click away
          in your system tray.
        </p>
      </div>

      <div className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card">
        {[
          {
            icon: Download,
            title: "Install and launch",
            description: `Run the Windows installer as your normal user, then open ${site.name} from the Start menu. The app includes its runtime; no Python or terminal setup is required.`,
          },
          {
            icon: Settings2,
            title: "Connect your providers",
            description: "Sign in through your providers’ apps or CLIs. Open Settings from the tray menu to enable providers, drag to reorder them and optionally start at sign-in.",
          },
          {
            icon: MousePointer2,
            title: "Open your usage panel",
            description: "Click the provider logo beside the clock to see usage and reset timers. Select a provider or metric to update the tray icon and tooltip; use Refresh to check immediately.",
          },
        ].map(({ icon: Icon, title, description }, index) => (
          <div key={title} className="flex gap-4 border-border p-5 not-first:border-t">
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

      <p className="text-sm leading-relaxed text-muted-foreground">
        If the icon is hidden, open the arrow beside the clock and move it into
        the visible tray. Usage refreshes every five minutes. The app keeps your
        settings when you upgrade.
      </p>

      <Link href="/windows" className="inline-flex w-fit items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">
        Windows setup and provider compatibility <ArrowRight className="size-3.5" />
      </Link>
    </section>
  );
}
