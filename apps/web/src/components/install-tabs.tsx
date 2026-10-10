"use client";

import { AppleIcon, LinuxIcon, WindowsIcon } from "@/components/os-icons";
import { useInstallPlatform, type InstallPlatform } from "@/components/install-platform";

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
	const { activeOs, setActiveOs } = useInstallPlatform();

	const platforms: { name: string; available: boolean; id: InstallPlatform; icon: React.ReactNode }[] = [
		{ name: "Linux", available: true, id: "Linux", icon: <LinuxIcon className={cn("size-4", align === "center" && "max-sm:size-3.5")} /> },
		{ name: "macOS", available: false, id: "macOS", icon: <AppleIcon className={cn("size-4", align === "center" && "max-sm:size-3.5")} /> },
		{ name: "Windows", available: true, id: "Windows", icon: <WindowsIcon className={cn("size-4", align === "center" && "max-sm:size-3.5")} /> },
	];

	return (
		<div className={cn("flex w-full min-w-0 flex-col gap-4 motion-safe:animate-fade-up [animation-delay:200ms]", align === "center" ? "items-center" : "items-start")}>
			<div className="w-full">
				<div className={activeOs === "Linux" ? "block" : "hidden"}>{linux}</div>
				<div className={activeOs === "macOS" ? "block" : "hidden"}>{mac}</div>
				<div className={activeOs === "Windows" ? "block" : "hidden"}>{win}</div>
			</div>

			<div className={cn("mt-1 items-center text-sm font-medium", align === "center" ? "grid w-full grid-cols-3 gap-1 pb-2 sm:flex sm:w-auto sm:flex-wrap sm:justify-center sm:gap-3 sm:pb-0" : "flex flex-wrap gap-3")}>
				{platforms.map((p) => {
          const isActive = activeOs === p.id;

					return (
						<button
							key={p.id}
							aria-label={p.name}
							aria-pressed={isActive}
							onClick={() => p.available && setActiveOs(p.id)}
							type="button"
							disabled={!p.available}
							className={cn(
								"flex items-center gap-2 px-4 py-2 rounded-full border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
								align === "center" && "relative min-h-11 min-w-0 justify-center gap-1 px-0.5 text-xs sm:min-h-0 sm:gap-2 sm:px-4 sm:text-sm",
								isActive ? "border-border bg-secondary/50 text-foreground" : "border-transparent text-muted-foreground opacity-50",
								!p.available ? "cursor-not-allowed grayscale" : "hover:opacity-100 hover:bg-secondary/20 cursor-pointer"
							)}
						>
							{p.icon}
							{p.name}
							{!p.available && (
								<span className={cn("text-[10px] uppercase tracking-wider bg-border/50 px-1.5 py-0.5 rounded-sm text-foreground", align === "center" && "absolute -bottom-2 left-1/2 -translate-x-1/2 sm:static sm:translate-x-0")}>
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
