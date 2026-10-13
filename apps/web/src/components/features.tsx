"use client";

import { WEB_SUPPORTED_PROVIDERS as SUPPORTED_PROVIDERS } from "@ai-status/shared";
import { FeatureVisuals } from "@/components/features-visuals";
import { useInstallPlatform } from "@/components/install-platform";

export function Features({ latestVersion }: { latestVersion: string }) {
  const { activeOs } = useInstallPlatform();
  const windows = activeOs === "Windows";
  const mac = activeOs === "macOS";
  const nativePanel = windows || mac;
  const features = [
    {
      title: "Multi-Provider",
      description: `Tracks usage limits across ${SUPPORTED_PROVIDERS.length} AI services simultaneously.`,
      visual: <FeatureVisuals.MultiProvider />,
    },
    {
      title: "Usage Refresh",
      description: "Choose automatic refresh from 5 to 60 minutes in native Settings. Refresh manually whenever you need an update.",
      visual: <FeatureVisuals.LiveUpdates windows={nativePanel} />,
    },
    {
      title: nativePanel ? "Usage Panel" : "Tooltip Detail",
      description: nativePanel
        ? `Click the ${mac ? "menu bar item" : "tray icon"} for usage bars, reset timers and Claude/Codex reset-credit details.`
        : "Per-provider breakdown with progress bars, percentages, and reset timers.",
      visual: <FeatureVisuals.TooltipDetail windows={nativePanel} />,
    },
    {
      title: "Configurable",
      description: mac
        ? "Enable, disable or reorder providers in the native Settings page. Choose the limit and menu bar display."
        : windows
        ? "Enable, disable or drag to reorder providers in Settings. Choose whether to start at sign-in."
        : "Enable, disable, or reorder providers via an interactive TUI (right-click).",
      visual: <FeatureVisuals.Configurable />,
    },
    {
      title: windows ? "Update Checks" : "Simple Updates",
      description: windows
        ? "Open the latest version from the app menu. Run the new installer to upgrade and keep your settings."
        : "Run the install command again to update the module and keep your configuration.",
      visual: <FeatureVisuals.Updates latestVersion={latestVersion} />,
    },
    {
      title: windows ? "Standalone App" : "Lightweight Runtime",
      description: windows
        ? "The installer includes the app runtime. No Python, Bash or WSL setup required."
        : mac
        ? "Native SwiftUI menu bar app with the shared Python backend. Requires Python 3.10+ and Xcode Command Line Tools."
        : "Runs with Python 3, Bash and Waybar. Connect providers through their apps or CLIs.",
      visual: windows ? <FeatureVisuals.Standalone /> : <FeatureVisuals.Lightweight />,
    },
  ];

  return (
    <section className="relative flex flex-col gap-8">
      <div className="relative z-10 flex flex-col gap-3">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Features</h2>
        <p className="max-w-xl text-muted-foreground">Usage limits, reset timers and provider settings on your desktop.</p>
      </div>
      <div className="relative z-10 grid grid-cols-1 gap-8 sm:grid-cols-2 sm:gap-4">
        {features.map((feature) => (
          <div key={feature.title} className="group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card transition-all">
            <div className="relative flex h-52 w-full items-center justify-center overflow-hidden border-b border-border bg-background/50">
              <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-size-[24px_24px] mask-[linear-gradient(to_bottom,white,transparent)] opacity-50" />
              {feature.visual}
            </div>
            <div className="flex flex-col gap-2 p-4">
              <h3 className="font-heading text-lg font-semibold text-foreground">{feature.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
