import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { SUPPORTED_PROVIDERS } from "@ai-status/shared";
import { site, repo } from "@/lib/env";
import { KeyRound, Plus, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
	title: `Supported Providers | ${site.name}`,
	description:
		"Every AI provider ai-status can track in your Waybar — what each one reports and where it reads your credentials from.",
};

export default function ProvidersPage() {
	return (
		<div className="mx-auto flex max-w-7xl flex-col gap-8 sm:gap-16 p-6 sm:py-16">
			<Header />

			<main className="flex flex-col gap-12">
				{/* Hero */}
				<section className="relative overflow-hidden rounded-3xl border border-border bg-card/40 px-6 py-12 sm:px-12 sm:py-16">
					{/* Grid pattern */}
					<div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_70%_80%_at_50%_0%,#000_20%,transparent_100%)] opacity-30" />
					{/* Ambient glow */}
					<div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-64 w-full max-w-2xl rounded-full bg-foreground/5 blur-[100px]" />

					<div className="relative z-10 flex flex-col gap-4">
						<span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur-md">
							<span className="relative flex size-1.5">
								<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-foreground/40" />
								<span className="relative inline-flex size-1.5 rounded-full bg-foreground/70" />
              </span>

							{SUPPORTED_PROVIDERS.length} providers supported
            </span>

						<h1 className="font-heading text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
							Supported Providers
            </h1>

						<p className="max-w-2xl text-lg text-muted-foreground">
							Every AI service ai-status can track in your Waybar — what each one
							reports, and where it reads your credentials from. Scroll, hover,
							and cycle through their limits right from the status bar.
						</p>
					</div>
				</section>

				{/* Provider grid */}
				<section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{SUPPORTED_PROVIDERS.map((provider) => (
						<Link
              key={provider.name}
              href={`/providers/${provider.slug}`}
							className="group relative flex flex-col gap-4 rounded-2xl border border-border bg-card/50 shadow-sm backdrop-blur-md transition-transform hover:-translate-y-0.5 hover:bg-card hover:shadow-md overflow-hidden"
						>
              <div className="flex flex-col gap-4 p-4">
                <header className="flex items-center gap-3">
  								<div className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-border bg-background shadow-sm">
  									<img
  										src={provider.logo}
  										alt={provider.name}
  										className="size-6 object-contain rounded-sm"
  									/>
                  </div>

  								<h2 className="font-heading text-lg font-semibold text-foreground">
  									{provider.name}
  								</h2>
  							</header>

  							<p className="flex-1 text-sm leading-relaxed text-muted-foreground">
  								{provider.tracks}
  							</p>
							</div>

							<footer className="flex items-center gap-1.5 bg-muted border-t border-border p-4 text-xs text-muted-foreground/80 mt-auto">
								<KeyRound className="size-3.5 shrink-0" />
								<span className="truncate font-mono" title={provider.auth}>
									{provider.auth}
								</span>
							</footer>
						</Link>
					))}

					{/* Add provider */}
					<a
						href={`${repo.url}/issues/new`}
						target="_blank"
						rel="noreferrer"
						className="group flex min-h-40 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border/60 bg-transparent p-5 text-center transition-all"
					>
						<span className="flex size-10 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground transition-colors group-hover:text-foreground">
							<Plus className="size-5" />
            </span>

						<span className="font-heading text-base font-semibold text-muted-foreground transition-colors group-hover:text-foreground">
							Add a provider
						</span>
						<span className="text-xs text-muted-foreground/70">
							Open an issue on GitHub
						</span>
					</a>
				</section>

				{/* Security note */}
				<section className="flex items-start gap-4 rounded-2xl border border-emerald-500/10 bg-emerald-500/10 p-4 text-sm">
          <ShieldCheck className="mt-0.5 size-5 shrink-0 text-emerald-500" />

          <div className="flex flex-col gap-2 leading-relaxed">
            <span className="font-medium text-emerald-500">
              Your credentials never leave your machine.
            </span>

            <div className="text-muted-foreground">
              <p>
                {site.name} ships zero API keys. Every provider reads its tokens directly from the auth files you already keep on disk — OAuth sessions, config files, cookies. Your machine talks straight to
                each provider's API. Nothing passes through us. No telemetry, no cloud proxy, no remote storage. Credentials live and die on your machine.
              </p>
            </div>
          </div>
				</section>
			</main>

			<Footer />
		</div>
	);
}
