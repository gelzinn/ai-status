import { Cta } from "@/components/cta";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Hero } from "@/components/hero";
import { CodeBlock } from "@/components/code-block";
import { HighlightedCodeBlock } from "@/components/code-highlight";
import {
  MultiProviderVisual,
  LiveUpdatesVisual,
  TooltipDetailVisual,
  ConfigurableVisual,
  SelfUpdatingVisual,
  ZeroDependenciesVisual,
} from "@/components/features-visuals";
import { WaybarReplica } from "@/components/waybar-replica";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { SUPPORTED_PROVIDERS } from "@ai-status/shared";
import { REPO_API_URL, REPO_URL } from "@/lib/env";
import {
  WAYBAR_CUSTOM_MODULE,
  WAYBAR_LOGO_MODULE,
  WAYBAR_LAYOUT,
} from "@/lib/waybar-config";

export default async function Homepage() {
  let latestVersion = "v1.3.0";
  let oldVersion = "v1.2.0";

  try {
    const res = await fetch(REPO_API_URL, {
      next: { revalidate: 3600 },
    });

    if (res.ok) {
      const data = await res.json();
      if (data.tag_name) {
        latestVersion = data.tag_name;

        const parts = data.tag_name.split(".");
        if (parts.length > 0) {
          const last = parseInt(parts[parts.length - 1]);
          if (!isNaN(last) && last > 0) {
            parts[parts.length - 1] = (last - 1).toString();
            oldVersion = parts.join(".");
          } else {
            oldVersion = data.tag_name + "-old";
          }
        }
      }
    }
  } catch (e) {
    console.error("Failed to fetch github release:", e);
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-8 sm:gap-16 p-6 sm:py-16">
      <Header />

      <main className="grid items-start gap-10 mt-8 lg:mt-16 lg:grid-cols-2 lg:gap-16">
        <div className="flex min-w-0 flex-col gap-16 md:gap-32 lg:gap-48 lg:pb-32 relative z-10">
          <Hero />

          <section className="flex flex-col gap-8">
            <div className="flex flex-col gap-3">
              <h2 className="font-heading text-2xl font-semibold tracking-tight">
                Waybar Configuration
              </h2>
              <p className="max-w-xl text-muted-foreground">
                Add the module to your Waybar config to get started. The status
                bar shows the usage percentage of the active provider.
              </p>
            </div>
            <HighlightedCodeBlock
              code={WAYBAR_CUSTOM_MODULE}
              lang="json"
              label="~/.config/waybar/config.jsonc"
            />
            <p className="text-sm text-muted-foreground">
              To display the active provider's logo next to the text, add the
              image module as well. The one-command install with{" "}
              <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
                --icon-mode logo
              </code>{" "}
              sets all of this up for you. To do it by hand: use an absolute{" "}
              <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
                path
              </code>{" "}
              (Waybar does not expand{" "}
              <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
                ~
              </code>
              ), install an SVG rasterizer (imagemagick or librsvg), and enable
              logo mode in the config TUI (right-click the module, set{" "}
              <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
                Provider Icon
              </code>{" "}
              to{" "}
              <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
                Provider Logo
              </code>
              ):
            </p>
            <HighlightedCodeBlock
              code={WAYBAR_LOGO_MODULE}
              lang="json"
              label="~/.config/waybar/config.jsonc"
            />
            <p className="text-sm text-muted-foreground">
              Then, include both{" "}
              <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
                "image#ai-status"
              </code>{" "}
              and{" "}
              <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
                "custom/ai-status"
              </code>{" "}
              in your preferred layout section (e.g.{" "}
              <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
                modules-right
              </code>
              ):
            </p>
            <CodeBlock
              code={WAYBAR_LAYOUT}
              label="~/.config/waybar/config.jsonc"
            >
              <span className="text-muted-foreground/40">{"{\n"}</span>
              <span className="text-muted-foreground/30">{"    // ...\n"}</span>
              <span className="text-muted-foreground/40">
                {'    "modules-right": [\n'}
              </span>
              {"        "}
              <span className="text-[#ffcfa3]">"image#ai-status"</span>
              <span className="text-muted-foreground/40">{",\n"}</span>
              {"        "}
              <span className="text-[#ffcfa3]">"custom/ai-status"</span>
              <span className="text-muted-foreground/40">{",\n"}</span>
              <span className="text-muted-foreground/40">
                {'        "network",\n'}
              </span>
              <span className="text-muted-foreground/40">
                {'        "cpu",\n'}
              </span>
              <span className="text-muted-foreground/40">
                {'        "memory",\n'}
              </span>
              <span className="text-muted-foreground/40">
                {'        "clock",\n'}
              </span>
              <span className="text-muted-foreground/40">
                {'        "tray"\n'}
              </span>
              <span className="text-muted-foreground/40">{"    ],\n"}</span>
              <span className="text-muted-foreground/30">{"    // ...\n"}</span>
              <span className="text-muted-foreground/40">{"}"}</span>
            </CodeBlock>

            <Link
              href="/llms.txt"
              className="inline-flex items-center gap-1 text-sm font-medium text-foreground hover:text-muted-foreground transition-colors w-fit mt-1"
            >
              Copy-paste install guide for LLMs <ArrowRight className="size-3.5" />
            </Link>
          </section>

          <section className="flex flex-col gap-8 relative">
            <div className="flex flex-col gap-8 relative z-10">
              <div className="flex flex-col gap-3">
                <h2 className="font-heading text-2xl font-semibold tracking-tight">
                  Features
                </h2>
                <p className="max-w-xl text-muted-foreground">
                  Everything you need to keep track of your AI usage.
                </p>
              </div>
              <div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  {[
                    {
                      title: "Multi-Provider",
                      description:
                        "Tracks API usage limits across seven AI services simultaneously.",
                      visual: MultiProviderVisual,
                    },
                    {
                      title: "Live Updates",
                      description:
                        "Auto-refreshes every 5 minutes with animated loading states.",
                      visual: LiveUpdatesVisual,
                    },
                    {
                      title: "Tooltip Detail",
                      description:
                        "Per-provider breakdown with progress bars, percentages, and reset timers.",
                      visual: TooltipDetailVisual,
                    },
                    {
                      title: "Configurable",
                      description:
                        "Enable, disable, or reorder providers via an interactive TUI (right-click).",
                      visual: ConfigurableVisual,
                    },
                    {
                      title: "Self-Updating",
                      description:
                        "One command installs and keeps the module up to date automatically.",
                      visual: () => (
                        <SelfUpdatingVisual
                          latestVersion={latestVersion}
                          oldVersion={oldVersion}
                        />
                      ),
                    },
                    {
                      title: "Zero Dependencies",
                      description:
                        "Written in pure Python and Bash. No heavy runtimes required.",
                      visual: ZeroDependenciesVisual,
                    },
                  ].map((feature) => (
                    <div
                      key={feature.title}
                      className="group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card transition-all"
                    >
                      {/* Visual Header */}
                      <div className="relative flex h-52 w-full items-center justify-center overflow-hidden border-b border-border bg-background/50">
                        {/* Subtle Grid Background */}
                        <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-size-[24px_24px] mask-[linear-gradient(to_bottom,white,transparent)] opacity-50" />
                        <feature.visual />
                      </div>
                      {/* Content */}
                      <div className="flex flex-col gap-2 p-4">
                        <h3 className="font-heading text-lg font-semibold text-foreground">
                          {feature.title}
                        </h3>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                          {feature.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className="flex flex-col gap-8 relative z-10">
            <div className="flex flex-col gap-3">
              <h2 className="font-heading text-2xl font-semibold tracking-tight">
                Supported Providers
              </h2>
              <p className="max-w-xl text-muted-foreground">
                Keep track of limits for the most popular AI services used
                inside companies.
              </p>
            </div>

            <div className="flex flex-wrap gap-2 items-center mt-4">
              {SUPPORTED_PROVIDERS.map((provider) => (
                <div
                  key={provider.name}
                  className="group flex cursor-default items-center gap-2 rounded-full bg-card border border-border px-4 py-2 shadow-sm backdrop-blur-md transition-all hover:border-border hover:bg-card/80 hover:shadow-md"
                >
                  <img
                    src={provider.logo}
                    alt={provider.name}
                    className="h-5 w-5 rounded-sm"
                  />

                  <span className="font-heading text-base font-medium text-foreground/80 transition-colors group-hover:text-foreground">
                    {provider.name}
                  </span>
                </div>
              ))}

              <a
                target="_blank"
                rel="noreferrer"
                href={`${REPO_URL}/issues/new`}
                className="group flex items-center gap-2 rounded-full border border-dashed border-border bg-card px-4 py-2 transition-all text-muted-foreground/50"
              >
                <span className="flex size-5 items-center justify-center rounded-sm transition-colors group-hover:text-foreground">
                  +
                </span>

                <span className="font-heading text-base font-medium transition-colors group-hover:text-foreground">
                  Add provider
                </span>
              </a>
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

      <Cta />

      <Footer />
    </div>
  );
}
