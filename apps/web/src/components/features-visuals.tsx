"use client";

import { useEffect, useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { PROVIDERS } from "@ai-status/shared";

export function MultiProviderVisual() {
  return (
    <div className="relative flex w-full h-full items-center justify-center">
      <div className="absolute w-32 h-32 rounded-full border border-border flex items-center justify-center group-hover:scale-110 transition-transform duration-700 ease-out">
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex h-6 w-6 items-center justify-center rounded-full bg-background border border-border">
          <img
            src={PROVIDERS.COPILOT.logo}
            className="h-3.5 w-3.5"
            alt={PROVIDERS.COPILOT.name}
          />
        </div>

        <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 flex h-6 w-6 items-center justify-center rounded-full bg-background border border-border">
          <img
            src={PROVIDERS.CLAUDE.logo}
            className="h-3.5 w-3.5"
            alt={PROVIDERS.CLAUDE.name}
          />
        </div>
      </div>

      <div className="absolute w-48 h-48 rounded-full border border-border/50 flex items-center justify-center group-hover:scale-105 transition-transform duration-1000 ease-out delay-75">
        <div className="absolute top-1/2 -right-3 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full bg-background border border-border">
          <img
            src={PROVIDERS.OPENCODE.logo}
            className="h-3.5 w-3.5"
            alt={PROVIDERS.OPENCODE.name}
          />
        </div>

        <div className="absolute top-1/2 -left-3 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full bg-background border border-border">
          <img
            src={PROVIDERS.CODEX.logo}
            className="h-3.5 w-3.5"
            alt={PROVIDERS.CODEX.name}
          />
        </div>
      </div>

      <div className="relative z-10 flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary border border-border backdrop-blur-md group-hover:bg-secondary/80 transition-colors duration-500">
        <Layers className="size-7 text-foreground" />
      </div>
    </div>
  );
}

export function LiveUpdatesVisual() {
  return (
    <div className="relative flex w-full h-full flex-col items-center justify-center">
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
            <img
              src={PROVIDERS.CLAUDE.logo}
              className="absolute h-3.5 w-3.5 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
              alt={PROVIDERS.CLAUDE.name}
            />
          </div>
          <span className="text-xs font-medium text-foreground">92%</span>
        </div>
      </div>
    </div>
  );
}

export function TooltipDetailVisual() {
  return (
    <div className="relative flex w-full h-full flex-col items-center pt-8">
      {/* Mock Waybar segment */}
      <div className="relative z-20 flex h-10 w-48 items-center justify-between rounded-full border border-border bg-card/80 px-4 backdrop-blur-md transition-colors duration-500 group-hover:bg-card">
        <div className="flex items-center gap-2">
          <img
            src={PROVIDERS.CLAUDE.logo}
            className="h-4 w-4 opacity-70 transition-opacity group-hover:opacity-100"
            alt={PROVIDERS.CLAUDE.name}
          />
          <span className="text-xs font-medium text-foreground">
            {PROVIDERS.CLAUDE.name}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">92%</span>
      </div>

      {/* Tooltip always visible but dim */}
      <div className="absolute top-20 z-10 flex w-56 translate-y-3 flex-col gap-2 rounded-xl border border-border bg-card/40 p-3 opacity-60 backdrop-blur-xl transition-all duration-500 group-hover:translate-y-1 group-hover:bg-card/95 group-hover:opacity-100">
        {/* Tooltip Content */}
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
    </div>
  );
}

import { GripVertical } from "lucide-react";

export function ConfigurableVisual() {
  return (
    <div className="relative flex w-full h-full items-center justify-center pt-2">
      <div className="relative h-34 w-48">
        {/* Item 1 */}
        <div className="absolute top-0 z-10 flex h-10 w-full items-center gap-2.5 rounded-lg border border-border bg-card/60 px-2.5 transition-all duration-700 ease-in-out group-hover:top-[48px] group-hover:scale-95 group-hover:opacity-40">
          <GripVertical className="size-3.5 text-muted-foreground/30" />
          <img
            src={PROVIDERS.CLAUDE.logo}
            className="h-4 w-4 opacity-70"
            alt={PROVIDERS.CLAUDE.name}
          />

          <span className="text-xs font-medium text-foreground">
            {PROVIDERS.CLAUDE.name}
          </span>

          <div className="ml-auto flex h-4 w-7 rounded-full bg-foreground p-0.5">
            <div className="h-3 w-3 translate-x-3 rounded-full bg-background" />
          </div>
        </div>

        {/* Item 2 */}
        <div className="absolute top-12 z-20 flex h-10 w-full items-center gap-2.5 rounded-lg border border-border bg-card/80 px-2.5 shadow-sm backdrop-blur-md transition-all duration-700 ease-in-out group-hover:top-0 group-hover:scale-105 group-hover:bg-card">
          <GripVertical className="size-3.5 text-muted-foreground/50 transition-colors group-hover:text-primary/50" />

          <img
            src={PROVIDERS.COPILOT.logo}
            className="h-4 w-4 opacity-70 transition-opacity group-hover:opacity-100"
            alt={PROVIDERS.COPILOT.name}
          />

          <span className="text-xs font-medium text-foreground">
            {PROVIDERS.COPILOT.name}
          </span>

          <div className="ml-auto flex h-4 w-7 rounded-full bg-border p-0.5 transition-colors duration-700 group-hover:bg-foreground">
            <div className="h-3 w-3 rounded-full bg-background transition-all duration-700 group-hover:translate-x-3" />
          </div>
        </div>

        {/* Item 3 */}
        <div className="absolute top-24 z-10 flex h-10 w-full items-center gap-2.5 rounded-lg border border-border bg-card/60 px-2.5 transition-all duration-700 ease-in-out group-hover:opacity-80">
          <GripVertical className="size-3.5 text-muted-foreground/30" />

          <img
            src={PROVIDERS.OPENCODE.logo}
            className="h-4 w-4 opacity-70"
            alt={PROVIDERS.OPENCODE.name}
          />

          <span className="text-xs font-medium text-foreground">
            {PROVIDERS.OPENCODE.name}
          </span>

          <div className="ml-auto flex h-4 w-7 rounded-full bg-foreground p-0.5">
            <div className="h-3 w-3 translate-x-3 rounded-full bg-background" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function SelfUpdatingVisual({
  latestVersion,
  oldVersion,
}: {
  latestVersion: string;
  oldVersion: string;
}) {
  return (
    <div className="relative flex w-full h-full flex-col items-center justify-center">
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
    </div>
  );
}

export function ZeroDependenciesVisual() {
  return (
    <div className="relative flex w-full h-full items-center justify-center perspective-[1000px]">
      <div className="relative flex items-center justify-center gap-6 px-4">
        {/* Python 3D Flip Card */}
        <div className="relative h-16 w-16 transition-transform duration-700 ease-[cubic-bezier(0.175,0.885,0.32,1.275)] transform-3d group-hover:transform-[rotateX(180deg)]">
          {/* Front */}
          <div className="absolute inset-0 flex items-center justify-center rounded-2xl border border-border bg-card/50 shadow-sm backface-hidden">
            <img
              src="https://svgl.app/library/python.svg"
              className="h-8 w-8"
              alt="Python"
            />
          </div>
          {/* Back */}
          <div className="absolute inset-0 flex items-center justify-center rounded-2xl border border-border bg-card shadow-sm backface-hidden transform-[rotateX(180deg)]">
            <span className="font-mono text-sm font-semibold tracking-wider text-foreground">
              ZERO
            </span>
          </div>
        </div>

        {/* Center '+' */}
        <div className="text-2xl font-light text-muted-foreground transition-all duration-400 group-hover:scale-0 group-hover:opacity-0">
          +
        </div>

        {/* Bash 3D Flip Card */}
        <div className="relative h-16 w-16 transition-transform duration-700 delay-150 ease-[cubic-bezier(0.175,0.885,0.32,1.275)] transform-3d group-hover:transform-[rotateX(180deg)]">
          {/* Front */}
          <div className="absolute inset-0 flex items-center justify-center rounded-2xl border border-border bg-card/50 shadow-sm backface-hidden">
            <img
              src="https://svgl.app/library/bash.svg"
              className="h-8 w-8 dark:invert"
              alt="Bash"
            />
          </div>
          {/* Back */}
          <div className="absolute inset-0 flex items-center justify-center rounded-2xl border border-border bg-card shadow-sm backface-hidden transform-[rotateX(180deg)]">
            <span className="font-mono text-sm font-semibold tracking-wider text-foreground">
              DEPS
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
