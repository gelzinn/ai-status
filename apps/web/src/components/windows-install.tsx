import Link from "next/link";
import { ArrowRight, Download } from "lucide-react";

export function WindowsInstall() {
	return (
		<div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 text-left">
			<div className="flex flex-col gap-1">
				<p className="text-sm font-medium text-foreground">Windows 10 &amp; 11 · x64</p>
				<p className="text-sm leading-relaxed text-muted-foreground">
					Install the app and monitor usage from your system tray. No terminal setup required.
				</p>
			</div>
			<div className="flex flex-wrap items-center gap-4">
				<a
					href="/download/windows"
					target="_blank"
					rel="noreferrer"
					className="inline-flex items-center justify-center gap-2 rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-foreground/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
				>
					<Download className="size-4" />
					Download for Windows
				</a>
				<Link href="/windows" className="inline-flex items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">
					Setup guide <ArrowRight className="size-3.5" />
				</Link>
			</div>
			<p className="text-xs leading-relaxed text-muted-foreground">
				Before the first Windows release, downloads open the preview builds. A GitHub account is required to download previews.
			</p>
		</div>
	);
}
