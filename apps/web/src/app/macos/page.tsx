import type { Metadata } from "next";
import { readFile } from "node:fs/promises";
import path from "node:path";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ArrowUpRight, CircleDot, KeyRound, ShieldCheck } from "lucide-react";
import { SUPPORTED_PROVIDERS } from "@ai-status/shared";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { GithubIcon } from "@/components/github-icon";
import { AppleIcon } from "@/components/os-icons";
import { HighlightedCodeBlock } from "@/components/code-highlight";
import { InstallCtaProvider, HeroInstallCta, StickyInstallCta } from "@/components/install-cta";
import { renderMarkdown } from "@/lib/markdown";
import { resolveLibGuideLinks } from "@/lib/guide-links";
import { repo, site } from "@/lib/env";

export const metadata: Metadata = {
  title: `macOS setup | ${site.name}`,
  description: "Install the native AI Status menu bar app on macOS, connect your accounts and configure usage, reset timers, API costs and balances.",
};

const guideSource = `${repo.url}/blob/main/packages/lib/MACOS.md`;

export default async function MacosPage() {
  const markdown = await readFile(path.resolve(process.cwd(), "../../packages/lib/MACOS.md"), "utf-8");
  const guide = await renderMarkdown(resolveLibGuideLinks(markdown.replace(/^# .+\r?\n\r?\n/, "")));

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-8 p-6 sm:gap-16 sm:py-16">
      <Header />

      <InstallCtaProvider heroId="macos-hero">
        <main className="flex flex-col gap-10">
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Link href="/" className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground">
              <ArrowLeft className="size-3.5" /> Home
            </Link>
            <span className="text-border">/</span>
            <span className="text-foreground">macOS</span>
          </nav>

          <section id="macos-hero" className="relative overflow-hidden rounded-3xl border border-border bg-card p-4">
            <div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_80%_at_30%_0%,#000_20%,transparent_100%)] opacity-30" />
            <div className="pointer-events-none absolute -top-24 left-1/4 h-64 w-full max-w-md -translate-x-1/2 rounded-full bg-foreground/5 blur-[100px]" />
            <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <div className="flex [--tile:4rem] size-(--tile) shrink-0 items-center justify-center rounded-[calc(var(--tile)/4)] border border-border bg-background shadow-sm">
                  <AppleIcon className="[--logo:2.25rem] size-(--logo) object-contain" />
                </div>
                <h1 className="font-heading text-xl font-semibold tracking-tight text-foreground sm:text-2xl lg:text-3xl">macOS Setup</h1>
              </div>
              <div className="flex shrink-0 flex-col gap-2.5 sm:flex-row sm:items-center">
                <HeroInstallCta href="#install" label="Install for macOS" />
                <a href={guideSource} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-2 rounded-full border border-border bg-background px-5 py-2.5 text-sm font-medium text-foreground transition-all hover:bg-muted">
                  <GithubIcon className="-ml-1 size-4" /> View source
                </a>
              </div>
            </div>
          </section>

          <div className="grid gap-10 lg:grid-cols-[1fr_260px] lg:gap-12">
            <article className="min-w-0">
              <section id="install" className="mb-10 flex scroll-mt-8 flex-col gap-4">
                <h2 className="font-heading text-2xl font-semibold tracking-tight text-foreground">Install the native menu bar app</h2>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  With Python 3.10 or newer and Xcode Command Line Tools installed, run this command in Terminal.
                  Re-run it to update while keeping your preferences.
                </p>
                <HighlightedCodeBlock code={`curl -fsSL ${site.installUrlMac} | bash`} lang="bash" label="Terminal" />
              </section>

              <h2 className="mb-4 font-heading text-2xl font-semibold tracking-tight text-foreground">Installation guide</h2>
              <div className="md-guide">{guide}</div>
            </article>

            <aside className="flex flex-col gap-4 lg:sticky lg:top-8 lg:self-start">
              <StickyInstallCta href="#install" label="Install for macOS" />

              <div className="overflow-hidden rounded-2xl border border-border bg-card">
                <div className="flex flex-col gap-2 p-4">
                  <span className="text-xs text-muted-foreground/70">Requirements</span>
                  <span className="text-sm text-foreground">macOS 13 or newer · Python 3.10+ · Xcode Command Line Tools</span>
                  <p className="text-sm leading-relaxed text-muted-foreground">The installer builds the native app locally. Sign in through your providers’ apps or CLIs, or configure API credentials.</p>
                </div>
                <footer className="flex items-center gap-2 border-t border-border bg-muted p-4 text-xs text-muted-foreground/80">
                  <KeyRound className="size-3.5 shrink-0" /> Local provider credentials
                </footer>
              </div>

              <div className="overflow-hidden rounded-2xl border border-border bg-card">
                <div className="flex flex-col gap-2 p-4 text-sm">
                  <span className="font-medium text-foreground">Native app by default</span>
                  <p className="leading-relaxed text-muted-foreground">SwiftBar is optional. Use the stream or periodic installer mode if you prefer its dropdown integration.</p>
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-border bg-card">
                <Link href="/macos/llms.txt" className="flex items-center justify-between gap-2 p-4 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                  Guide for LLMs <ArrowRight className="size-3.5 shrink-0" />
                </Link>
                <a href={`${repo.url}/issues/new`} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-2 border-t border-border p-4 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                  <span className="inline-flex items-center gap-2"><CircleDot className="size-4" /> Report an issue</span>
                  <ArrowUpRight className="size-3.5 shrink-0" />
                </a>
                <Link href="/security" className="flex items-center justify-between gap-2 border-t border-border p-4 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                  <span className="inline-flex items-center gap-2"><ShieldCheck className="size-4" /> Security &amp; privacy</span>
                  <ArrowUpRight className="size-3.5 shrink-0" />
                </Link>
              </div>
            </aside>
          </div>

          <section className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="font-heading text-xl font-semibold tracking-tight text-foreground">Supported providers</h2>
              <Link href="/providers" className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground">View all <ArrowRight className="size-3.5" /></Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {SUPPORTED_PROVIDERS.map((provider) => (
                <Link key={provider.slug} href={`/providers/${provider.slug}`} className="group flex items-center gap-3 rounded-2xl border border-border bg-card p-3 transition-all hover:-translate-y-0.5 hover:bg-card">
                  <div className="flex [--tile:2.25rem] size-(--tile) shrink-0 items-center justify-center rounded-[calc(var(--tile)/4)] border border-border bg-background">
                    <img src={provider.logo} alt={provider.name} className="[--logo:1.25rem] size-(--logo) rounded-[calc(var(--logo)/6)] object-contain" />
                  </div>
                  <span className="font-heading text-sm font-semibold text-foreground">{provider.name}</span>
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
