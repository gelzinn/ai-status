import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { QuickshellConfiguration } from "@/components/quickshell-configuration";
import { Hero } from "@/components/hero";
import { Features } from "@/components/features";
import { InstallPlatformProvider, PlatformContent } from "@/components/install-platform";
import { WaybarConfiguration } from "@/components/waybar-configuration";
import { WindowsConfiguration } from "@/components/windows-configuration";
import { MacosConfiguration } from "@/components/macos-configuration";
import { WaybarReplica } from "@/components/waybar-replica";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, Plus, ShieldCheck } from "lucide-react";

import { SUPPORTED_PROVIDERS } from "@ai-status/shared";
import { site, repo } from "@/lib/env";
import { getLatestVersion } from "@/lib/version";

export default async function Homepage() {
  const latestVersion = await getLatestVersion();

  return (
    <InstallPlatformProvider>
    <div className="mx-auto flex max-w-7xl flex-col gap-8 sm:gap-16 p-6 sm:py-16">
      <Header />

      <main className="grid items-start gap-10 mt-8 lg:mt-0 lg:grid-cols-2 lg:gap-16">
        <div className="flex min-w-0 flex-col gap-16 md:gap-32 lg:gap-48 lg:pb-32 relative z-10">
          <Hero />

          <div role="region" aria-label="Interactive app preview" className="h-[420px] w-full sm:h-[480px] lg:hidden">
            <WaybarReplica version={latestVersion} compact />
          </div>

          <PlatformContent
            linux={<><QuickshellConfiguration /><WaybarConfiguration /></>}
            mac={<MacosConfiguration />}
            windows={<WindowsConfiguration />}
          />

          <Features latestVersion={latestVersion} />

          <section className="flex flex-col gap-8 relative z-10">
            <div className="flex flex-col gap-3">
              <h2 className="font-heading text-2xl font-semibold tracking-tight">
                Supported Providers
              </h2>
              <p className="max-w-xl text-muted-foreground">
                See which providers are supported and how to connect each one.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {SUPPORTED_PROVIDERS.map((provider) => (
                <Link
                  key={provider.slug}
                  href={`/providers/${provider.slug}`}
                  className="group flex items-center gap-3 rounded-2xl border border-border bg-card p-3 transition-all hover:-translate-y-0.5 hover:border-foreground/20"
                >
                  <div className="flex [--tile:2.25rem] size-(--tile) shrink-0 items-center justify-center rounded-[calc(var(--tile)/4)] border border-border bg-background">
                    <img
                      src={provider.logo}
                      alt={provider.name}
                      className="[--logo:1.25rem] size-(--logo) rounded-[calc(var(--logo)/6)] object-contain"
                    />
                  </div>
                  <span className="font-heading text-sm font-semibold text-foreground">
                    {provider.name}
                  </span>
                  <ArrowUpRight className="ml-auto size-4 text-muted-foreground/40 transition-colors group-hover:text-foreground" />
                </Link>
              ))}

              <a
                target="_blank"
                rel="noreferrer"
                href={`${repo.url}/issues/new`}
                className="group flex items-center gap-3 rounded-2xl border border-dashed border-border bg-card p-3 text-muted-foreground transition-all hover:-translate-y-0.5 hover:border-foreground/20 hover:text-foreground"
              >
                <div className="flex [--tile:2.25rem] size-(--tile) shrink-0 items-center justify-center rounded-[calc(var(--tile)/4)] border border-border bg-background">
                  <Plus className="size-4" />
                </div>
                <span className="font-heading text-sm font-semibold">
                  Add a provider
                </span>
                <ArrowUpRight className="ml-auto size-4 text-muted-foreground/40 transition-colors group-hover:text-foreground" />
              </a>
            </div>

            <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 text-sm">
              <div className="flex items-start gap-3">
                <ShieldCheck className="mt-0.5 size-5 shrink-0 text-foreground/70" />
                <p className="text-pretty leading-relaxed text-muted-foreground">
                  <span className="font-medium text-foreground">
                    Your credentials never leave your machine.
                  </span>{" "}
                  {site.name} reads tokens from your local auth files and talks
                  straight to each provider — no server, no telemetry.
                </p>
              </div>

              <Link
                href="/security"
                className="inline-flex w-fit items-center gap-1 pl-8 text-sm font-medium text-foreground transition-colors hover:text-muted-foreground"
              >
                How {site.name} handles your credentials
                <ArrowRight className="size-3.5" />
              </Link>
            </div>

            <Link
              href="/providers"
              className="inline-flex items-center gap-1 text-sm font-medium text-foreground hover:text-muted-foreground transition-colors w-fit mt-1"
            >
              View supported providers <ArrowRight className="size-3.5" />
            </Link>
          </section>
        </div>

        <aside className="hidden lg:block lg:sticky z-0 lg:top-8 lg:self-start lg:h-[calc(100vh-4rem)]">
          <WaybarReplica version={latestVersion} />
        </aside>
      </main>

      <Footer />
    </div>
    </InstallPlatformProvider>
  );
}
