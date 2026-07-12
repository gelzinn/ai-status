import { readFile } from "node:fs/promises";
import path from "node:path";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import {
	ArrowLeft,
	ArrowRight,
	ArrowUpRight,
	CircleDot,
	KeyRound,
	ShieldCheck,
} from "lucide-react";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { GithubIcon } from "@/components/github-icon";
import {
	InstallCtaProvider,
	HeroInstallCta,
	StickyInstallCta,
} from "@/components/install-cta";
import { SUPPORTED_PROVIDERS, type Provider } from "@ai-status/shared";
import { site, repo, LIB_NAME } from "@/lib/env";
import { renderMarkdown } from "@/lib/markdown";

function getProvider(slug: string): Provider | undefined {
	return SUPPORTED_PROVIDERS.find((p) => p.slug === slug);
}

function sourceUrl(slug: string) {
	return `${repo.url}/tree/main/packages/lib/src/providers/${slug}`;
}

/** Read the provider's auth guide markdown, or null if one hasn't been written yet. */
async function getGuide(slug: string): Promise<string | null> {
	try {
		const file = path.resolve(process.cwd(), "content/providers", `${slug}.md`);
		return await readFile(file, "utf-8");
	} catch {
		return null;
	}
}

export function generateStaticParams() {
	return SUPPORTED_PROVIDERS.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
	params,
}: {
	params: Promise<{ slug: string }>;
}): Promise<Metadata> {
	const { slug } = await params;
	const provider = getProvider(slug);
	if (!provider) return { title: `Provider not found | ${site.name}` };
	return {
		title: `${provider.name} | ${site.name}`,
		description: `How to authenticate ${provider.name} in your Waybar with ${LIB_NAME} — ${provider.tracks}.`,
	};
}

export default async function ProviderPage({
	params,
}: {
	params: Promise<{ slug: string }>;
}) {
	const { slug } = await params;
	const provider = getProvider(slug);
	if (!provider) notFound();

	const guideMd = await getGuide(slug);
  const guide = guideMd ? await renderMarkdown(guideMd) : null;

	const others = SUPPORTED_PROVIDERS.filter((p) => p.slug !== slug);

	return (
		<div className="mx-auto flex max-w-7xl flex-col gap-8 sm:gap-16 p-6 sm:py-16">
			<Header />

			<InstallCtaProvider heroId="provider-hero">
				<main className="flex flex-col gap-10">
				{/* Breadcrumb */}
				<nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
					<Link
						href="/providers"
						className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground"
					>
						<ArrowLeft className="size-3.5" />
						Providers
					</Link>
					<span className="text-border">/</span>
					<span className="text-foreground">{provider.name}</span>
				</nav>

				{/* Hero */}
				<section
					id="provider-hero"
					className="relative overflow-hidden rounded-3xl border border-border bg-card p-4"
				>
					<div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_80%_at_30%_0%,#000_20%,transparent_100%)] opacity-30" />
					<div className="pointer-events-none absolute -top-24 left-1/4 h-64 w-full max-w-md -translate-x-1/2 rounded-full bg-foreground/5 blur-[100px]" />

					<div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
						<div className="flex items-center gap-4">
							<div className="flex [--tile:4rem] size-(--tile) shrink-0 items-center justify-center rounded-[calc(var(--tile)/4)] border border-border bg-background shadow-sm">
								<img
									src={provider.logo}
									alt={provider.name}
									className="[--logo:2.25rem] size-(--logo) rounded-[calc(var(--logo)/6)] object-contain"
								/>
              </div>

							<h1 className="font-heading text-xl sm:text-2xl lg:text-3xl font-semibold tracking-tight text-foreground">
								{provider.name}
							</h1>
						</div>

						<div className="flex shrink-0 flex-col gap-2.5 sm:flex-row sm:items-center">
							<HeroInstallCta label={`Install ${site.name}`} />

							<a
								href={sourceUrl(slug)}
								target="_blank"
								rel="noreferrer"
								className="flex items-center justify-center gap-2 rounded-full border border-border bg-background px-5 py-2.5 text-sm font-medium text-foreground transition-all hover:bg-muted"
							>
								<GithubIcon className="-ml-1 size-4" />
								View source
							</a>
						</div>
					</div>
				</section>

				{/* Body: guide + sidebar */}
				<div className="grid gap-10 lg:grid-cols-[1fr_260px] lg:gap-12">
					<article className="min-w-0">
						<h2 className="mb-4 font-heading text-2xl font-semibold tracking-tight text-foreground">
							Authentication guide
            </h2>

						{guide ? (
							<div className="md-guide">{guide}</div>
						) : (
							<div className="flex flex-col gap-4 rounded-2xl border border-dashed border-border bg-card p-6 text-sm leading-relaxed text-muted-foreground">
								<p>
									A step-by-step guide for {provider.name} is coming soon. In the
									meantime, {site.name} reads its credentials from{" "}
									<code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-foreground">
										{provider.auth}
									</code>
									.
                  </p>

								<a
									href={sourceUrl(slug)}
									target="_blank"
									rel="noreferrer"
									className="inline-flex items-center gap-1 font-medium text-foreground underline underline-offset-4 decoration-border hover:decoration-foreground"
								>
									View the provider source on GitHub
									<ArrowUpRight className="size-3.5" />
								</a>
							</div>
						)}
					</article>

					<aside className="flex flex-col gap-4 lg:sticky lg:top-8 lg:self-start">
						{/* Install CTA — morphs in from the hero once it scrolls off. */}
						<StickyInstallCta label={`Install ${site.name}`} />

						{/* Details card — mirrors the provider listing card:
						    content + a bg-muted footer bar with the auth source. */}
						<div className="overflow-hidden rounded-2xl border border-border bg-card">
							<div className="flex flex-col gap-2 p-4">
								<span className="text-xs text-muted-foreground/70">Tracks</span>
								<span className="text-sm text-foreground">{provider.tracks}</span>
							</div>

							<footer className="flex items-center gap-2 border-t border-border bg-muted p-4 text-xs text-muted-foreground/80">
								<KeyRound className="size-3.5 shrink-0" />
								<span className="truncate font-mono" title={provider.auth}>
									{provider.auth}
								</span>
							</footer>
						</div>

						{/* Links card */}
						<div className="overflow-hidden rounded-2xl border border-border bg-card">
							<a
								href={sourceUrl(slug)}
								target="_blank"
								rel="noreferrer"
								className="flex items-center justify-between gap-2 p-4 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
							>
								<span className="inline-flex items-center gap-2">
									<GithubIcon className="size-4" />
									View source
                </span>

								<ArrowUpRight className="size-3.5" />
              </a>

							<a
								href={`${repo.url}/issues/new`}
								target="_blank"
								rel="noreferrer"
								className="flex items-center justify-between gap-2 border-t border-border p-4 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
							>
								<span className="inline-flex items-center gap-2">
									<CircleDot className="size-4" />
									Report an issue
                </span>

								<ArrowUpRight className="size-3.5" />
							</a>
								<Link
									href="/security"
									className="flex items-center justify-between gap-2 border-t border-border p-4 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
								>
									<span className="inline-flex items-center gap-2">
										<ShieldCheck className="size-4" />
										Security &amp; privacy
									</span>
									<ArrowUpRight className="size-3.5" />
								</Link>
						</div>
					</aside>
				</div>

				{/* Other providers */}
				<section className="flex flex-col gap-4">
					<div className="flex items-center justify-between">
						<h2 className="font-heading text-xl font-semibold tracking-tight text-foreground">
							Other providers
						</h2>
						<Link
							href="/providers"
							className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
						>
							View all <ArrowRight className="size-3.5" />
						</Link>
					</div>
					<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
						{others.map((p) => (
							<Link
								key={p.slug}
								href={`/providers/${p.slug}`}
								className="group flex items-center gap-3 rounded-2xl border border-border bg-card p-3 transition-all hover:-translate-y-0.5 hover:bg-card"
							>
								<div className="flex [--tile:2.25rem] size-(--tile) shrink-0 items-center justify-center rounded-[calc(var(--tile)/4)] border border-border bg-background">
									<img
										src={p.logo}
										alt={p.name}
										className="[--logo:1.25rem] size-(--logo) rounded-[calc(var(--logo)/6)] object-contain"
									/>
								</div>
								<span className="font-heading text-sm font-semibold text-foreground">
									{p.name}
								</span>
								<ArrowUpRight className="ml-auto size-4 text-muted-foreground/40 transition-colors group-hover:text-foreground" />
							</Link>
						))}
					</div>
				</section>
			</main>
			</InstallCtaProvider>

			<Footer />
		</div>
	);
}
