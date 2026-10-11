import Link from "next/link";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { SUPPORTED_PROVIDERS } from "@/lib/providers";
import { site, LIB_NAME } from "@/lib/env";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { ProviderSearch } from "@/components/provider-search";
import type { Metadata } from "next";

export const metadata: Metadata = {
	title: `Supported Providers | ${site.name}`,
	description: `Every AI provider ${LIB_NAME} can track in your status bar — what each one reports and where it reads your credentials from.`,
};

export default function ProvidersPage() {
	return (
		<div className="mx-auto flex max-w-7xl flex-col gap-8 sm:gap-16 p-6 sm:py-16">
			<Header />

			<main className="flex flex-col gap-8 sm:gap-16 mt-8 lg:mt-0">
				{/* Hero — plain text, like the home hero */}
				<section className="flex flex-col gap-8">
					<h1 className="font-heading max-w-2xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
						Supported Providers
					</h1>
					<p className="max-w-2xl text-lg text-muted-foreground">
						Every AI service {LIB_NAME} can track on Linux, Windows and macOS —
						what each one reports, and where it reads your credentials from.
					</p>
				</section>

				{/* Search + provider grid */}
				<ProviderSearch providers={SUPPORTED_PROVIDERS} />

				{/* Security note */}
				<section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 text-sm">
					<div className="flex items-start gap-3">
						<ShieldCheck className="mt-0.5 size-5 shrink-0 text-foreground/70" />
						<p className="leading-relaxed text-muted-foreground">
							<span className="font-medium text-foreground">
								Credentials are read locally.
							</span>{" "}
							{site.name} reads existing sessions or configured key sources
							and sends authenticated requests directly to each provider.
							No intermediary server or telemetry.
						</p>
					</div>

					<Link
						href="/security"
						className="inline-flex w-fit items-center gap-1 pl-8 text-sm font-medium text-foreground transition-colors hover:text-muted-foreground"
					>
						How {site.name} handles your credentials
						<ArrowRight className="size-3.5" />
					</Link>
				</section>
			</main>

			<Footer />
		</div>
	);
}
