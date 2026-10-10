import type { Metadata } from "next";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { WindowsInstall } from "@/components/windows-install";
import { renderMarkdown } from "@/lib/markdown";
import { site } from "@/lib/env";

export const metadata: Metadata = {
	title: `Windows setup | ${site.name}`,
	description: "Install the native AI Status tray app on Windows 10 and 11, connect your providers and monitor usage from your desktop.",
};

export default async function WindowsPage() {
	const guide = await readFile(path.resolve(process.cwd(), "../../packages/lib/WINDOWS.md"), "utf-8");
	return (
		<div className="mx-auto flex max-w-7xl flex-col gap-8 p-6 sm:gap-16 sm:py-16">
			<Header />
			<main className="flex max-w-3xl flex-col gap-8">
				<WindowsInstall />
				<article className="md-guide">{await renderMarkdown(guide)}</article>
			</main>
			<Footer />
		</div>
	);
}
