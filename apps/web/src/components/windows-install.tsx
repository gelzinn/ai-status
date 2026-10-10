import Link from "next/link";
import { ArrowRight, Download } from "lucide-react";
import { cn } from "@/lib/utils";
import { getWindowsDownload } from "@/lib/windows-download";

export async function WindowsInstall({ align = "start" }: { align?: "start" | "center" }) {
	const download = await getWindowsDownload();
	const centered = align === "center";
	return (
		<div className={cn("flex flex-col gap-4 rounded-2xl border border-border bg-card p-4", centered ? "items-center text-center" : "text-left")}>
			<div className={cn("flex flex-col gap-1", centered && "items-center")}>
				<p className="text-sm font-medium text-foreground">Windows 10 &amp; 11 · x64</p>
				<p className={cn("text-sm leading-relaxed text-muted-foreground", centered && "max-w-md")}>
					Install the app and monitor usage from your system tray. No terminal setup required.
				</p>
			</div>
			<div className={cn("flex flex-wrap items-center gap-4", centered && "w-full flex-col justify-center gap-2 sm:w-auto sm:flex-row sm:gap-4")}>
				<a
					href={download.href}
					target="_blank"
					rel="noreferrer"
					className={cn("inline-flex items-center justify-center gap-2 rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-foreground/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", centered && "min-h-11 w-full max-w-xs sm:min-h-0 sm:w-auto")}
				>
					<Download className="size-4" />
					Download for Windows
				</a>
				<Link href="/windows" className={cn("inline-flex items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground", centered && "min-h-11 sm:min-h-0")}>
					Setup guide <ArrowRight className="size-3.5" />
				</Link>
			</div>
			{download.kind === "preview" && (
				<p className={cn("text-xs leading-relaxed text-muted-foreground", centered && "max-w-md")}>
					Downloads currently open preview builds. A GitHub account is required to download previews.
				</p>
			)}
		</div>
	);
}
