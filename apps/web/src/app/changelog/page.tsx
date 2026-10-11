import type { Metadata } from "next";
import Link from "next/link";
import { Inter } from "next/font/google";
import { ArrowLeft, ArrowRight, Bell } from "lucide-react";
import { ChangelogShell } from "@/components/changelog-shell";
import { ChangelogSearch } from "@/components/changelog-search";
import { PILL_CONTROL } from "@/components/search-input";
import { getReleases } from "@/lib/releases";
import { selectReleases } from "@/lib/changelog";
import { renderMarkdown } from "@/lib/markdown";
import { repo, site } from "@/lib/env";
import "./changelog.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-changelog" });

export const metadata: Metadata = {
	title: `Changelog | ${site.name}`,
	description: `The latest features, improvements and fixes in ${site.name}.`,
	alternates: { canonical: "/changelog" },
	openGraph: { title: `Changelog | ${site.name}`, url: "/changelog" },
};

function pageHref(page: number, query: string) {
	const params = new URLSearchParams();
	if (query) params.set("q", query);
	if (page > 1) params.set("page", String(page));
	return `/changelog${params.size ? `?${params}` : ""}`;
}

const dateFormat = new Intl.DateTimeFormat("en-US", { dateStyle: "long", timeZone: "UTC" });

export default async function ChangelogPage({ searchParams }: {
	searchParams: Promise<{ q?: string | string[]; page?: string | string[] }>;
}) {
	const params = await searchParams;
	const result = await getReleases();
	const selection = selectReleases(result.releases, {
		query: typeof params.q === "string" ? params.q : "",
		page: typeof params.page === "string" ? Number(params.page) : 1,
	});
	const articles = await Promise.all(selection.releases.map(async (release) => {
		const id = `release-${release.id}`;
		return (
			<article key={release.id} id={id} className="changelog-entry" aria-labelledby={`${id}-title`}>
				<div className="changelog-date"><a href={`#${id}`}><time dateTime={release.publishedAt}>{dateFormat.format(new Date(release.publishedAt))}</time></a></div>
				<div className="changelog-article">
					<h2 id={`${id}-title`} className="changelog-release-title"><a href={release.url}>{release.name}</a></h2>
					{release.name !== release.tagName && <p className="changelog-version">{release.tagName}</p>}
					<div className="changelog-prose">
						{release.body.trim() ? await renderMarkdown(release.body, { release, headingPrefix: `${id}-section-` }) : <p>No release notes were provided. <a href={release.url}>View this release on GitHub.</a></p>}
					</div>
					<a href={release.url} className="changelog-release-link">View release on GitHub <ArrowRight size={14} aria-hidden="true" /></a>
				</div>
			</article>
		);
	}));
	return (
		<ChangelogShell className={inter.variable}>
			<main id="changelog-content" className="changelog-container">
				<div className="changelog-page-header">
					<h1>Changelog</h1>
					<div className="changelog-toolbar">
						<nav aria-label="Updates"><Link href="/changelog" aria-current="page">Changelog</Link></nav>
						<div className="changelog-tools">
							<ChangelogSearch query={selection.query} />
							<a href={`${repo.url}/releases.atom`} className={`${PILL_CONTROL} inline-flex size-10 shrink-0 items-center justify-center border-border bg-card text-muted-foreground outline-none hover:text-foreground focus-visible:border-foreground/30`} aria-label="Subscribe to release updates"><Bell className="size-4" aria-hidden="true" /></a>
						</div>
					</div>
				</div>
				<div className="changelog-list">
					{selection.query && <div className="changelog-search-results"><p>{selection.total} {selection.total === 1 ? "release" : "releases"} matching “{selection.query}”</p><Link href="/changelog">Clear search</Link></div>}
					{result.status === "unavailable" ? <div className="changelog-empty" role="status"><h2>Release updates are temporarily unavailable</h2><p>Please try again shortly, or <a href={`${repo.url}/releases`}>read the releases on GitHub</a>.</p></div> : articles.length ? articles : <div className="changelog-empty" role="status"><h2>{selection.query ? "No releases found" : "No releases published yet"}</h2><p>{selection.query ? "Try another version, title or keyword." : "Published stable releases will appear here."}</p><a href={`${repo.url}/releases`}>View GitHub Releases <ArrowRight size={14} aria-hidden="true" /></a></div>}
				</div>
				{selection.pageCount > 1 && <nav className="changelog-pagination" aria-label="Release pages">
					{selection.page > 1 && <Link href={pageHref(selection.page - 1, selection.query)} rel="prev"><ArrowLeft size={14} aria-hidden="true" />Newer updates</Link>}
					<span>Page {selection.page} of {selection.pageCount}</span>
					{selection.page < selection.pageCount && <Link href={pageHref(selection.page + 1, selection.query)} rel="next">Older updates<ArrowRight size={14} aria-hidden="true" /></Link>}
				</nav>}
			</main>
		</ChangelogShell>
	);
}
