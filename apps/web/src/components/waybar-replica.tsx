"use client";

import { Bot, Wifi, Bluetooth } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState, useEffect, useRef } from "react";
import { PROVIDERS } from "@ai-status/shared";
import { PROJECT_NAME } from "@/lib/env";

type Stat = {
  label: string;
  percent: number;
  resets: string;
  isPrimary?: boolean;
};
type WaybarData = {
  provider: string;
  isActive?: boolean;
  logo?: string;
  stats: Stat[];
};

const WAYBAR_DATA: WaybarData[] = [
  {
    provider: `${PROVIDERS.CLAUDE.name} (Max)`,
    logo: PROVIDERS.CLAUDE.logo,
    isActive: true,
    stats: [
      { label: "Rolling Usage:", percent: 2, resets: "Resets in 4h 55m" },
      { label: "Weekly Usage:", percent: 24, resets: "Resets in 3d 16h" },
      {
        label: "Weekly Usage:",
        percent: 53,
        resets: "Fable · Resets in 3d 16h",
      },
    ],
  },
  {
    provider: `${PROVIDERS.CODEX.name} (Plus)`,
    logo: PROVIDERS.CODEX.logo,
    stats: [
      { label: "Rolling Usage:", percent: 3, resets: "Resets in 4h 25m" },
      { label: "Weekly Usage:", percent: 25, resets: "Resets in 6d 12h" },
    ],
  },
  {
    provider: `${PROVIDERS.OPENCODE.name} (Go)`,
    logo: PROVIDERS.OPENCODE.logo,
    stats: [
      { label: "Rolling Usage:", percent: 5, resets: "Resets in 5h 0m" },
      { label: "Weekly Usage:", percent: 32, resets: "Resets in 5d 20h" },
      { label: "Monthly Usage:", percent: 91, resets: "Resets in 4d 18h" },
    ],
  },
  {
    provider: `Gemini (${PROVIDERS.ANTIGRAVITY.name})`,
    logo: PROVIDERS.ANTIGRAVITY.logo,
    stats: [
      {
        label: "Rolling Usage:",
        percent: 27,
        resets: "Resets in 2h 54m",
        isPrimary: true,
      },
      { label: "Weekly Usage:", percent: 40, resets: "Resets in 3d 15h" },
    ],
  },
  {
    provider: `${PROVIDERS.CLAUDE.name}/GPT (${PROVIDERS.ANTIGRAVITY.name})`,
    logo: PROVIDERS.ANTIGRAVITY.logo,
    stats: [
      { label: "Rolling Usage:", percent: 0, resets: "no reset available" },
      { label: "Weekly Usage:", percent: 64, resets: "Resets in 3d 14h" },
    ],
  },
  {
    provider: `${PROVIDERS.ZAI.name} Coding Plan (Max)`,
    logo: PROVIDERS.ZAI.logo,
    stats: [
      { label: "Rolling Usage:", percent: 0, resets: "no reset available" },
      { label: "Weekly Usage:", percent: 6, resets: "Resets in 7h 26m" },
      { label: "Monthly Usage:", percent: 0, resets: "Resets in 2d 7h" },
    ],
  },
];

const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

export function WaybarReplica({ version }: { version: string }) {
  const [mounted, setMounted] = useState(false);

  const [activeIdx, setActiveIdx] = useState(0);
  const [activeStatIdx, setActiveStatIdx] = useState(0);

  const [isOpen, setIsOpen] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [spinnerFrame, setSpinnerFrame] = useState(0);
  const [transform, setTransform] = useState(
    "perspective(1200px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)",
  );

  const cardRef = useRef<HTMLDivElement>(null);
  const topbarRef = useRef<HTMLDivElement>(null);

  const activeProvider = WAYBAR_DATA[activeIdx];
  const primaryStat =
    activeProvider.stats[activeStatIdx] || activeProvider.stats[0];

  // Prevent page scroll and navigate stats/providers
  useEffect(() => {
    const el = topbarRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (e.deltaY > 0) {
        // Next stat or next provider
        if (activeStatIdx + 1 < WAYBAR_DATA[activeIdx].stats.length) {
          setActiveStatIdx(activeStatIdx + 1);
        } else {
          setActiveIdx((activeIdx + 1) % WAYBAR_DATA.length);
          setActiveStatIdx(0);
        }
      } else if (e.deltaY < 0) {
        // Prev stat or prev provider
        if (activeStatIdx - 1 >= 0) {
          setActiveStatIdx(activeStatIdx - 1);
        } else {
          const nextIdx =
            activeIdx === 0 ? WAYBAR_DATA.length - 1 : activeIdx - 1;
          setActiveIdx(nextIdx);
          setActiveStatIdx(WAYBAR_DATA[nextIdx].stats.length - 1);
        }
      }
    };

    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, [activeIdx, activeStatIdx]);

  // Animate progress bars on mount
  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 100);
    return () => clearTimeout(timer);
  }, []);

  // Spinner animation for refreshing state
  useEffect(() => {
    if (!isRefreshing) return;
    const interval = setInterval(() => {
      setSpinnerFrame((f) => (f + 1) % SPINNER_FRAMES.length);
    }, 80);
    return () => clearInterval(interval);
  }, [isRefreshing]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;

    const prefersReducedMotion = typeof window !== "undefined" && (window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    if (prefersReducedMotion) return;


    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Calculate 3D tilt
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -4; // Max 4 deg
    const rotateY = ((x - centerX) / centerX) * 4;

    setTransform(
      `perspective(1200px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`,
    );
  };

  const handleMouseLeave = () => {
    setTransform(
      "perspective(1200px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)",
    );
  };

  return (
    <div
      ref={cardRef}
      className="relative w-full h-full rounded-2xl border border-border bg-black bg-[url('/omarchy-wallpaper.jpeg')] bg-contain bg-no-repeat bg-center shadow-[0_0_60px_rgba(0,0,0,0.6)] font-mono text-xs flex flex-col overflow-hidden transition-all duration-300 ease-out group"
      style={{ transform, transformStyle: "preserve-3d" }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {/* Fake Waybar Full Width */}
      <div className="relative w-full shrink-0 h-10 bg-card backdrop-blur-md border-b border-border flex items-center justify-between px-4 z-20">
        {/* Left Workspaces */}
        <div className="flex items-center gap-3 opacity-50">
          {Array.from({ length: 6 }).map((_, idx) => (
            <div
              key={idx}
              className="w-3 h-3 rounded-full bg-muted-foreground/30"
            />
          ))}
        </div>

        {/* Right Tray */}
        <div className="flex items-center gap-4">
          {/* AI Status Module (Top bar part) */}
          <div
            ref={topbarRef}
            className="relative flex items-center gap-2 cursor-pointer hover:bg-foreground/10 px-2 py-1 -mx-2 rounded-md transition-colors select-none"
            onClick={() => setIsOpen(!isOpen)}
            onContextMenu={(e) => {
              e.preventDefault();
              if (isRefreshing) return;
              setIsRefreshing(true);
              setTimeout(() => setIsRefreshing(false), 2000);
            }}
          >
            <div className="relative flex items-center justify-center">
              {activeProvider.logo ? (
                <img
                  src={activeProvider.logo}
                  alt=""
                  className="size-3.5 object-contain filter brightness-110"
                />
              ) : (
                <Bot className="size-3.5 text-foreground transition-colors duration-300" />
              )}
            </div>

            <span className="text-foreground font-medium">
              {activeProvider.provider} {isRefreshing ? SPINNER_FRAMES[spinnerFrame] : `${primaryStat.percent}%`}
            </span>
          </div>

          {/* Other icons */}
          <div className="flex items-center gap-2 opacity-50 text-muted-foreground">
            <Wifi className="size-3.5" />
            <Bluetooth className="size-3.5" />
          </div>
        </div>
      </div>

      {/* Desktop Body Container */}
      <div className="relative flex-1 flex justify-end p-4 z-10 overflow-hidden">
        {/* AI Status Tooltip Dropdown */}
        <div
          className={cn(
            "relative w-[65%] h-full rounded-xl bg-card/95 backdrop-blur-2xl border border-border shadow-[0_0_50px_rgba(0,0,0,0.5)] flex flex-col overflow-hidden transition-all duration-350 ease-[cubic-bezier(0.16,1,0.3,1)] origin-top-right",
            !isOpen && "opacity-0 scale-95 pointer-events-none -translate-y-2",
          )}
        >
          <div className="flex flex-col overflow-hidden select-none">
            {/* Header */}
            <div className="flex flex-col gap-2 p-4 border-b border-border/50">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {PROJECT_NAME}
                </span>

                <span className="text-muted-foreground">{version}</span>
              </div>
            </div>

            <div className="flex flex-col overflow-hidden mask-[linear-gradient(to_bottom,black_70%,transparent_100%)] p-2">
              {WAYBAR_DATA.map((item, idx) => {
                const isActive = activeIdx === idx;

                return (
                  <div
                    key={idx}
                    className="flex flex-col gap-4 cursor-pointer p-4 rounded-xl hover:bg-foreground/5"
                    onClick={() => {
                      setActiveIdx(idx);
                      setActiveStatIdx(0);
                    }}
                  >
                    <div className="flex items-center gap-2 relative pl-4">
                      <span
                        className={cn(
                          "absolute left-0 font-medium transition-colors duration-300",
                          isActive
                            ? "text-foreground"
                            : "text-muted-foreground opacity-0",
                        )}
                      >
                        →
                      </span>

                      <img
                        src={item.logo}
                        alt={item.provider}
                        className="size-3.5 object-contain opacity-80 filter brightness-110"
                      />

                      <span
                        className={cn(
                          "font-medium transition-colors duration-300",
                          isActive
                            ? "text-foreground"
                            : "text-muted-foreground",
                        )}
                      >
                        {item.provider}
                      </span>
                    </div>

                    <div className="flex flex-col gap-4 px-4">
                      {item.stats.map((stat, statIdx) => {
                        const isStatActive =
                          isActive && statIdx === activeStatIdx;

                        return (
                          <div
                            key={statIdx}
                            className={cn(
                              "flex flex-col gap-1 pl-4 relative rounded-lg px-2 py-1 -mx-2",
                              !isStatActive && "hover:bg-foreground/5",
                            )}
                            onClick={(e) => {
                              e.stopPropagation();

                              setActiveIdx(idx);
                              setActiveStatIdx(statIdx);
                            }}
                          >
                            {isStatActive && (
                              <span className="absolute -left-2 top-1 text-foreground text-xs leading-none mt-0.5">
                                •
                              </span>
                            )}

                            <span
                              className={cn(
                                isStatActive
                                  ? "text-foreground"
                                  : "text-muted-foreground",
                              )}
                            >
                              {stat.label}
                            </span>

                            <div
                              className={cn(
                                "flex items-center gap-1",
                                isStatActive
                                  ? "text-foreground"
                                  : "text-muted-foreground",
                              )}
                            >
                              <span>[</span>

                              <div
                                className={cn(
                                  "relative flex-1 h-4 overflow-hidden rounded-[1px] border border-border/50",
                                  isRefreshing
                                    ? "bg-muted-foreground/10"
                                    : "bg-secondary/50",
                                )}
                              >
                                {isRefreshing && (
                                  <div className="absolute inset-0 w-full h-full bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.15),transparent)] animate-shimmer" />
                                )}
                                {/* Filled Bar */}
                                <div
                                  className={cn(
                                    "absolute left-0 top-0 h-full transition-all duration-1500 ease-[cubic-bezier(0.16,1,0.3,1)]",
                                    isStatActive
                                      ? "bg-foreground"
                                      : "bg-muted-foreground/50",
                                    isRefreshing && "opacity-0"
                                  )}
                                  style={{
                                    width: mounted ? `${stat.percent}%` : "0%",
                                    transitionDelay: mounted
                                      ? `${idx * 150}ms`
                                      : "0ms",
                                  }}
                                />
                              </div>

                              <span>]</span>

                              <span
                                className={cn(
                                  "w-8 tabular-nums text-right",
                                  isStatActive
                                    ? "text-foreground"
                                    : "text-muted-foreground",
                                )}
                              >
                                {isRefreshing ? SPINNER_FRAMES[spinnerFrame] : `${stat.percent}%`}
                              </span>
                            </div>

                            <span
                              className={cn(
                                "text-muted-foreground/60",
                                stat.resets === "no reset available" &&
                                "opacity-50",
                              )}
                            >
                              {stat.resets}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
