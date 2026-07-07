import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { SUPPORTED_PROVIDERS } from "@ai-status/shared";
import type { Metadata } from "next";

export const metadata: Metadata = {
	title: "Supported Providers | AI Status",
	description: "List of all supported AI providers by ai-status.",
};

export default function ProvidersPage() {
	return (
		<div className="mx-auto flex max-w-7xl flex-col gap-8 sm:gap-16 p-6 sm:py-16">
			<Header />

			<main className="flex flex-col gap-12 mt-8 lg:mt-16 min-h-[50vh]">
				<div className="flex flex-col gap-4">
					<h1 className="font-heading text-4xl font-semibold tracking-tight sm:text-5xl">
						Supported Providers
					</h1>
					<p className="max-w-2xl text-lg text-muted-foreground">
						A complete list of all AI API providers currently supported by the Waybar module.
					</p>
				</div>

				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{SUPPORTED_PROVIDERS.map((provider) => (
						<div
							key={provider.name}
							className="flex items-center gap-4 rounded-xl border border-border/50 bg-card/30 p-4 shadow-sm backdrop-blur-md transition-all hover:bg-card/80 hover:shadow-md"
						>
							<div className="flex size-12 items-center justify-center rounded-lg bg-background border border-border shadow-sm">
								<img
									src={provider.logo}
									alt={provider.name}
									className="size-6 object-contain"
								/>
							</div>
							<div className="flex flex-col">
								<span className="font-heading text-lg font-semibold text-foreground">
									{provider.name}
								</span>
							</div>
						</div>
					))}
					<a
						href="https://github.com/gelzinn/ai-status/issues/new"
						target="_blank"
						rel="noreferrer"
						className="group flex items-center justify-center gap-4 rounded-xl border-2 border-dashed border-border/50 bg-transparent p-4 shadow-sm transition-all hover:border-foreground/30 hover:bg-muted/50 min-h-22"
					>
						<span className="font-heading text-lg font-semibold text-muted-foreground transition-colors group-hover:text-foreground">
							+ Add new provider
						</span>
					</a>
				</div>
			</main>

			<Footer />
		</div>
	);
}
