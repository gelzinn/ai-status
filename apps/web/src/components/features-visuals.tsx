import type { ReactNode } from "react";
import { GripVertical, Layers, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { PROVIDERS, type Provider } from "@ai-status/shared";

// ── base building blocks ────────────────────────────────────────────
// Small, presentational pieces shared across the feature visuals below.
// Every visual lives inside a `group` card, so hover states use `group-hover`.

/** The square stage every feature visual is rendered into. */
function VisualStage({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("relative flex h-full w-full", className)}>{children}</div>
  );
}

/** A provider's logo image. */
function ProviderLogo({
  provider,
  className,
}: {
  provider: Provider;
  className?: string;
}) {
  return <img src={provider.logo} alt={provider.name} className={className} />;
}

/** A provider logo inside a bordered dot — the orbiting badges. */
function OrbitDot({
  provider,
  className,
}: {
  provider: Provider;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "absolute flex h-6 w-6 items-center justify-center rounded-full border border-border bg-background",
        className,
      )}
    >
      <ProviderLogo provider={provider} className="h-3.5 w-3.5" />
    </div>
  );
}

/** A small pill toggle. Track/knob classes carry the on/off + animation. */
function ToggleSwitch({
  trackClassName,
  knobClassName,
}: {
  trackClassName?: string;
  knobClassName?: string;
}) {
  return (
    <div className={cn("ml-auto flex h-4 w-7 rounded-full p-0.5", trackClassName)}>
      <div className={cn("h-3 w-3 rounded-full bg-background", knobClassName)} />
    </div>
  );
}

/** A draggable provider row — grip handle, logo, name, and a toggle. */
function ProviderRow({
  provider,
  className,
  gripClassName,
  logoClassName,
  toggle,
}: {
  provider: Provider;
  className?: string;
  gripClassName?: string;
  logoClassName?: string;
  toggle: ReactNode;
}) {
  return (
    <div
      className={cn(
        "absolute flex h-10 w-full items-center gap-2.5 rounded-lg border border-border px-2.5",
        className,
      )}
    >
      <GripVertical className={cn("size-3.5", gripClassName)} />
      <ProviderLogo
        provider={provider}
        className={cn("h-4 w-4 opacity-70", logoClassName)}
      />
      <span className="text-xs font-medium text-foreground">{provider.name}</span>
      {toggle}
    </div>
  );
}

/** A 3D flip card — the front rotates on hover to reveal the back. */
function FlipCard({
  front,
  back,
  className,
}: {
  front: ReactNode;
  back: ReactNode;
  className?: string;
}) {
  const face =
    "absolute inset-0 flex items-center justify-center rounded-2xl border border-border shadow-sm backface-hidden";
  return (
    <div
      className={cn(
        "relative h-16 w-16 transition-transform duration-700 ease-[cubic-bezier(0.175,0.885,0.32,1.275)] transform-3d group-hover:transform-[rotateX(180deg)]",
        className,
      )}
    >
      <div className={cn(face, "bg-card/50")}>{front}</div>
      <div className={cn(face, "bg-card transform-[rotateX(180deg)]")}>{back}</div>
    </div>
  );
}

/** Flip-card back label. */
function FlipLabel({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-sm font-semibold tracking-wider text-foreground">
      {children}
    </span>
  );
}

// ── feature visuals ─────────────────────────────────────────────────

function MultiProvider() {
  return (
    <VisualStage className="items-center justify-center">
      <div className="absolute flex h-32 w-32 items-center justify-center rounded-full border border-border transition-transform duration-700 ease-out group-hover:scale-110">
        <OrbitDot provider={PROVIDERS.COPILOT} className="-top-3 left-1/2 -translate-x-1/2" />
        <OrbitDot provider={PROVIDERS.CLAUDE} className="-bottom-3 left-1/2 -translate-x-1/2" />
      </div>

      <div className="absolute flex h-48 w-48 items-center justify-center rounded-full border border-border/50 transition-transform duration-1000 ease-out delay-75 group-hover:scale-105">
        <OrbitDot provider={PROVIDERS.OPENCODE} className="top-1/2 -right-3 -translate-y-1/2" />
        <OrbitDot provider={PROVIDERS.CODEX} className="top-1/2 -left-3 -translate-y-1/2" />
      </div>

      <div className="relative z-10 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-secondary backdrop-blur-md transition-colors duration-500 group-hover:bg-secondary/80">
        <Layers className="size-7 text-foreground" />
      </div>
    </VisualStage>
  );
}

function LiveUpdates() {
  return (
    <VisualStage className="flex-col items-center justify-center">
      {/* Background data stream */}
      <div className="absolute top-6 flex w-full justify-center opacity-100 transition-all duration-700 ease-out mask-[linear-gradient(to_bottom,white_40%,transparent_90%)] group-hover:-translate-y-4 group-hover:opacity-0">
        <div className="flex w-44 flex-col gap-1 font-mono text-[9px] leading-none text-primary/40">
          <div className="text-foreground/50">fetching quotas...</div>
          <div className="ml-2">{"{"}</div>
          <div className="ml-4">{PROVIDERS.CLAUDE.name}: 460,</div>
          <div className="ml-4">{PROVIDERS.OPENCODE.name}: 150,</div>
          <div className="ml-4">{PROVIDERS.COPILOT.name}: 850</div>
          <div className="ml-2">{"}"}</div>
          <div className="mt-0.5 text-emerald-500/60">{">"} 200 OK</div>
        </div>
      </div>

      {/* Mock Waybar segment */}
      <div className="relative z-10 flex h-12 translate-y-10 items-center justify-center rounded-full border border-transparent bg-transparent px-2 transition-all duration-700 ease-out group-hover:translate-y-0 group-hover:border-border/60 group-hover:bg-card/40">
        {/* 3 Extra Borders */}
        <div className="pointer-events-none absolute -inset-2.5 rounded-full border border-border/50 opacity-0 delay-0 transition-opacity duration-700 group-hover:opacity-100 group-hover:delay-150" />
        <div className="pointer-events-none absolute -inset-5 rounded-full border border-border/30 opacity-0 delay-0 transition-opacity duration-700 group-hover:opacity-100 group-hover:delay-300" />
        <div className="pointer-events-none absolute -inset-7.5 rounded-full border border-border/10 opacity-0 delay-0 transition-opacity duration-700 group-hover:opacity-100 group-hover:delay-450" />

        {/* AI Status Module */}
        <div className="relative flex h-8 items-center justify-center gap-2 rounded-full border border-border bg-card/50 px-3 pl-8 transition-colors duration-500 group-hover:bg-card">
          <div className="absolute left-3 flex h-4 w-4 items-center justify-center">
            <div className="absolute h-3 w-3 animate-spin rounded-full border-[1.5px] border-border border-t-foreground transition-opacity duration-500 group-hover:opacity-0" />
            <ProviderLogo
              provider={PROVIDERS.CLAUDE}
              className="absolute h-3.5 w-3.5 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
            />
          </div>
          <span className="text-xs font-medium text-foreground">92%</span>
        </div>
      </div>
    </VisualStage>
  );
}

function TooltipDetail() {
  return (
    <VisualStage className="flex-col items-center p-4 pt-8">
      {/* Mock Waybar segment */}
      <div className="relative z-20 flex h-10 w-48 items-center justify-between rounded-full border border-border bg-card/80 px-4 backdrop-blur-md transition-colors duration-500 group-hover:bg-card">
        <div className="flex items-center gap-2">
          <ProviderLogo
            provider={PROVIDERS.CLAUDE}
            className="h-4 w-4 opacity-70 transition-opacity group-hover:opacity-100"
          />
          <span className="text-xs font-medium text-foreground">
            {PROVIDERS.CLAUDE.name}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">92%</span>
      </div>

      {/* Tooltip always visible but dim */}
      <div className="absolute top-20 z-10 flex w-54 translate-y-3 flex-col gap-2 rounded-xl border border-border bg-card/40 p-3 opacity-60 backdrop-blur-xl transition-all duration-500 group-hover:translate-y-1 group-hover:bg-card/95 group-hover:opacity-100">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-foreground">Rolling Usage</span>
          </div>

          <div className="h-1.5 w-full overflow-hidden rounded-full bg-foreground/5">
            <div className="h-full w-10 rounded-full bg-red-500 transition-all duration-1000 ease-out group-hover:w-[92%]" />
          </div>
        </div>

        <div className="mt-2 flex items-center gap-1.5 border-t border-border/50 pt-2 text-[9px] text-muted-foreground">
          <div className="flex h-2 w-2 items-center justify-center rounded-full bg-primary/10 transition-colors group-hover:bg-primary/20">
            <div className="h-1 w-1 rounded-full bg-primary opacity-30 transition-opacity group-hover:animate-pulse group-hover:opacity-100" />
          </div>
          Resets in 12 mins
        </div>
      </div>
    </VisualStage>
  );
}

function Configurable() {
  return (
    <VisualStage className="items-center justify-center pt-2">
      <div className="relative h-34 w-48">
        <ProviderRow
          provider={PROVIDERS.CLAUDE}
          className="top-0 z-10 bg-card/60 transition-all duration-700 ease-in-out group-hover:top-[48px] group-hover:scale-95 group-hover:opacity-40"
          gripClassName="text-muted-foreground/30"
          toggle={<ToggleSwitch trackClassName="bg-foreground" knobClassName="translate-x-3" />}
        />

        <ProviderRow
          provider={PROVIDERS.COPILOT}
          className="top-12 z-20 bg-card/80 shadow-sm backdrop-blur-md transition-all duration-700 ease-in-out group-hover:top-0 group-hover:scale-105 group-hover:bg-card"
          gripClassName="text-muted-foreground/50 transition-colors group-hover:text-primary/50"
          logoClassName="transition-opacity group-hover:opacity-100"
          toggle={
            <ToggleSwitch
              trackClassName="bg-border transition-colors duration-700 group-hover:bg-foreground"
              knobClassName="transition-all duration-700 group-hover:translate-x-3"
            />
          }
        />

        <ProviderRow
          provider={PROVIDERS.OPENCODE}
          className="top-24 z-10 bg-card/60 transition-all duration-700 ease-in-out group-hover:opacity-80"
          gripClassName="text-muted-foreground/30"
          toggle={<ToggleSwitch trackClassName="bg-foreground" knobClassName="translate-x-3" />}
        />
      </div>
    </VisualStage>
  );
}

function SelfUpdating({
  latestVersion,
  oldVersion,
}: {
  latestVersion: string;
  oldVersion: string;
}) {
  return (
    <VisualStage className="flex-col items-center justify-center">
      {/* Mock Waybar segment */}
      <div className="relative z-10 flex h-12 items-center justify-center rounded-full border border-border bg-card px-2 shadow-sm backdrop-blur-md transition-all duration-700 ease-out group-hover:border-border/60 group-hover:bg-card/60">
        {/* Self Update Module */}
        <div className="relative flex h-8 items-center justify-center gap-4 overflow-hidden rounded-full border border-border bg-card/50 px-4 transition-colors duration-500 group-hover:bg-card">
          {/* Old Version */}
          <div className="relative z-10 flex items-center gap-2 transition-all duration-700 group-hover:opacity-40">
            <span className="font-mono text-[10px] font-medium text-muted-foreground">
              {oldVersion}
            </span>
          </div>

          {/* Icon */}
          <div className="relative z-10 flex items-center justify-center">
            <RefreshCw className="size-3 text-muted-foreground transition-all duration-1000 group-hover:rotate-360 group-hover:text-foreground" />
          </div>

          {/* New Version */}
          <div className="relative z-10 flex items-center gap-2">
            <span className="font-mono text-[10px] font-medium text-foreground transition-all duration-500 delay-500 group-hover:scale-110">
              {latestVersion}
            </span>
          </div>
        </div>
      </div>

      {/* Status text */}
      <div className="absolute bottom-6 flex translate-y-2 items-center gap-1.5 opacity-0 transition-all delay-100 duration-500 group-hover:translate-y-0 group-hover:opacity-100">
        <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground" />
        <span className="text-[10px] font-medium text-muted-foreground">
          Auto-updated in background
        </span>
      </div>
    </VisualStage>
  );
}

function ZeroDependencies() {
  return (
    <VisualStage className="items-center justify-center perspective-[1000px]">
      <div className="relative flex items-center justify-center gap-6 px-4">
        <FlipCard
          front={
            <img src="https://svgl.app/library/python.svg" className="h-8 w-8" alt="Python" />
          }
          back={<FlipLabel>ZERO</FlipLabel>}
        />

        {/* Center '+' */}
        <div className="text-2xl font-light text-muted-foreground transition-all duration-400 group-hover:scale-0 group-hover:opacity-0">
          +
        </div>

        <FlipCard
          className="delay-150"
          front={
            <img
              src="https://svgl.app/library/bash.svg"
              className="h-8 w-8 dark:invert"
              alt="Bash"
            />
          }
          back={<FlipLabel>DEPS</FlipLabel>}
        />
      </div>
    </VisualStage>
  );
}

// ── export ──────────────────────────────────────────────────────────

export const FeatureVisuals = {
  MultiProvider,
  LiveUpdates,
  TooltipDetail,
  Configurable,
  SelfUpdating,
  ZeroDependencies,
};
