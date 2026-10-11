"use client";

import { AppleIcon, LinuxIcon, WindowsIcon } from "@/components/os-icons";
import { useInstallPlatform, type InstallPlatform } from "@/components/install-platform";

import { cn } from "@/lib/utils";

export function InstallTabs({
	linux,
	mac,
	win,
}: {
	linux: React.ReactNode;
	mac: React.ReactNode;
	win: React.ReactNode;
}) {
	const { activeOs, setActiveOs } = useInstallPlatform();

	const platforms: { name: string; available: boolean; id: InstallPlatform; icon: React.ReactNode }[] = [
		{ name: "Linux", available: true, id: "Linux", icon: <LinuxIcon className="size-4" /> },
		{ name: "macOS", available: true, id: "macOS", icon: <AppleIcon className="size-4" /> },
		{ name: "Windows", available: true, id: "Windows", icon: <WindowsIcon className="size-4" /> },
	];

	return (
		<div className="flex w-full min-w-0 flex-col items-start gap-4 motion-safe:animate-fade-up [animation-delay:200ms]">
			<div className="grid w-full min-w-0">
				<div
					className={cn("col-start-1 row-start-1 min-w-0 self-start", activeOs !== "Linux" && "invisible")}
					aria-hidden={activeOs !== "Linux"}
					inert={activeOs !== "Linux"}
				>{linux}</div>
				<div
					className={cn("col-start-1 row-start-1 min-w-0 self-start", activeOs !== "macOS" && "invisible")}
					aria-hidden={activeOs !== "macOS"}
					inert={activeOs !== "macOS"}
				>{mac}</div>
				<div
					className={cn("col-start-1 row-start-1 min-w-0 self-start", activeOs !== "Windows" && "invisible")}
					aria-hidden={activeOs !== "Windows"}
					inert={activeOs !== "Windows"}
				>{win}</div>
			</div>

			<div className="mt-1 flex flex-wrap items-center gap-3 text-sm font-medium">
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
