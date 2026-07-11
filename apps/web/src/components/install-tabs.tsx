"use client";

import { useState } from "react";
import { AppleIcon, LinuxIcon, WindowsIcon } from "@/components/os-icons";

import { cn } from "@/lib/utils";

export function InstallTabs({
	linux,
	mac,
	win,
	align = "start",
}: {
	linux: React.ReactNode;
	mac: React.ReactNode;
	win: React.ReactNode;
	align?: "start" | "center";
}) {
	const [activeOs, setActiveOs] = useState("Linux");

	const platforms = [
		{ name: "Linux", available: true, id: "Linux", icon: <LinuxIcon className="size-4" /> },
		{ name: "macOS", available: false, id: "macOS", icon: <AppleIcon className="size-4" /> },
		{ name: "Windows", available: false, id: "Windows", icon: <WindowsIcon className="size-4" /> },
	];

	return (
		<div className={cn("flex w-full min-w-0 flex-col gap-4 motion-safe:animate-fade-up [animation-delay:200ms]", align === "center" ? "items-center" : "items-start")}>
			<div className="w-full">
				<div className={activeOs === "Linux" ? "block" : "hidden"}>{linux}</div>
				<div className={activeOs === "macOS" ? "block" : "hidden"}>{mac}</div>
				<div className={activeOs === "Windows" ? "block" : "hidden"}>{win}</div>
			</div>

			<div className={cn("flex flex-wrap items-center gap-3 mt-1 text-sm font-medium", align === "center" && "sm:justify-center")}>
				{platforms.map((p) => {
          const isActive = activeOs === p.id;

					return (
						<button
							key={p.id}
							onClick={() => p.available && setActiveOs(p.id)}
							type="button"
							disabled={!p.available}
							className={cn(
								"flex items-center gap-2 px-4 py-2 rounded-full border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
								isActive ? "border-border bg-secondary/50 text-foreground" : "border-transparent text-muted-foreground opacity-50",
								!p.available ? "cursor-not-allowed grayscale" : "hover:opacity-100 hover:bg-secondary/20 cursor-pointer"
							)}
						>
							{p.icon}
							{p.name}
							{!p.available && (
								<span className="text-[10px] uppercase tracking-wider bg-border/50 px-1.5 py-0.5 rounded-sm text-foreground">
									Soon
								</span>
							)}
						</button>
					);
				})}
			</div>
		</div>
	);
}
