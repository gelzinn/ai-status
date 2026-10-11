import Link from "next/link";
import { ArrowRight, Download } from "lucide-react";
import { getWindowsDownload } from "@/lib/windows-download";

export async function WindowsInstall() {
	const download = await getWindowsDownload();
	return (
		<div className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-4 text-left">
			<p className="text-sm font-medium text-foreground">Windows 10 &amp; 11 · x64</p>
			<div className="flex flex-wrap items-center gap-4">
				<a
					href={download.href}
					target="_blank"
					rel="noreferrer"
					aria-label="Download for Windows"
					className="inline-flex items-center justify-center gap-2 rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-foreground/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
				>
					<Download className="size-4" />
					<span>Download<span className="hidden sm:inline"> for Windows</span></span>
				</a>
				<Link href="/windows" className="inline-flex items-center gap-1 text-sm font-medium transition-colors hover:text-muted-foreground">
					Setup guide <ArrowRight className="size-3.5" />
				</Link>
			</div>
		</div>
	);
}
