import type { Metadata } from "next";
import {
	ArrowUpRight,
	Database,
	EyeOff,
	FileCode2,
	Gauge,
	Image as ImageIcon,
	KeyRound,
	RadioTower,
	ServerOff,
	Terminal,
} from "lucide-react";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { GithubIcon } from "@/components/github-icon";
import { SUPPORTED_PROVIDERS } from "@ai-status/shared";
import { site, repo } from "@/lib/env";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
	title: `Security & Privacy | ${site.name}`,
	description: `How ${site.name} handles your credentials — read locally from files other tools already created, used only to call each provider's own API, never proxied, stored, or tracked.`,
};

/** Exactly where each provider's token comes from, grounded in its query script. */
const CREDENTIAL_SOURCES: Record<string, { source: string; note: string }> = {
	claude: {
		source: "~/.claude/.credentials.json",
		note: "The OAuth token Claude Code already saved (falls back to OpenCode).",
	},
	codex: {
		source: "~/.codex/auth.json",
		note: "The token the Codex CLI already saved.",
	},
	copilot: {
		source: "~/.local/share/opencode/auth.json",
		note: "The GitHub Copilot token OpenCode already saved.",
	},
	opencode: {
		source: "~/.local/share/opencode/auth.json",
		note: "The OpenCode token; usage is scraped from your own workspace dashboard.",
	},
	zai: {
		source: "~/.local/share/opencode/account.json",
		note: "The Z.AI account token OpenCode already saved.",
	},
	antigravity: {
		source: "agy CLI",
		note: "Runs the official agy CLI and reads its /usage output — no file touched.",
	},
	kiro: {
		source: "kiro-cli",
		note: "Runs the official kiro-cli and reads its session usage — no file touched.",
	},
	commandcode: {
		source: "~/.commandcode/auth.json",
		note: "The API key the cmd CLI saved on login.",
	},
};

const NEVER = [
	{
		icon: KeyRound,
		title: "Ship API keys",
		body: `${site.name} bundles no keys, tokens, or secrets of its own. It only ever reads the ones already on your disk.`,
	},
	{
		icon: ServerOff,
		title: "Proxy your requests",
		body: `There is no ${site.name} server. Your machine talks straight to each provider — there is nothing in the middle to route data through.`,
	},
	{
		icon: EyeOff,
		title: "Send telemetry",
		body: "No analytics, no crash reporting, no usage tracking. Nothing about you or your machine is collected.",
	},
	{
		icon: Database,
		title: "Store your tokens",
		body: "Tokens are read at query time and used for that one request. Nothing is copied, logged, or persisted.",
	},
];

const STEPS = [
	{
		icon: KeyRound,
		title: "Read",
		body: `${site.name} reads a token that an existing tool — Claude Code, Codex, OpenCode — already stored on your disk. It never creates new credentials.`,
	},
	{
		icon: RadioTower,
		title: "Ask",
		body: "Your machine calls the provider's own API directly with that token, exactly like the official app would. The request never leaves your control.",
	},
	{
		icon: Gauge,
		title: "Show",
		body: "The response — a usage percentage and reset time — is rendered in your bar. Nothing is written back or sent anywhere else.",
	},
];

/** The complete set of hosts the module ever reaches — shown in the visual. */
const ENDPOINTS = [
	{ icon: RadioTower, label: "Providers" },
	{ icon: GithubIcon, label: "GitHub" },
	{ icon: ImageIcon, label: "Logos" },
];

// Clean curved routes, all from the machine's right-center (56, 88) to each
// chip's left edge (148, 40 / 88 / 136). Fixed 288×176 coordinate space so the
// SVG lines up with the absolutely-placed HTML nodes. No tails — packets fade
// out as they land in the chip, so nothing sits or stops.
const OUTBOUND_PATHS = [
	"M56 88 C 102 88, 102 40, 148 40",
	"M56 88 C 102 88, 102 88, 148 88",
	"M56 88 C 102 88, 102 136, 148 136",
];
const CHIP_TOP = ["top-[22px]", "top-[70px]", "top-[118px]"];

/** Animated "Your machine → 3 destinations" diagram — curved links from one
    origin; glowing packets stream out and dissolve into each chip on arrival. */
function OutboundVisual() {
	return (
		<div className="relative z-10 h-44 w-72">
			{/* Curved routes + traveling packets */}
			<svg
				viewBox="0 0 288 176"
				fill="none"
				className="absolute inset-0 h-full w-full overflow-visible"
				aria-hidden="true"
			>
				{OUTBOUND_PATHS.map((d, i) => (
					<path
						key={`route-${i}`}
						id={`ob-path-${i}`}
						d={d}
						stroke="var(--border)"
						strokeWidth="1.5"
						strokeLinecap="round"
					/>
				))}

				<g className="motion-reduce:hidden">
					{OUTBOUND_PATHS.map((_, i) => (
						<circle key={`packet-${i}`} r="3" fill="var(--foreground)" opacity="0">
							<animateMotion
								dur="1.8s"
								begin={`${i * 0.6}s`}
								repeatCount="indefinite"
								calcMode="linear"
							>
								<mpath href={`#ob-path-${i}`} />
							</animateMotion>
							<animate
								attributeName="opacity"
								dur="1.8s"
								begin={`${i * 0.6}s`}
								repeatCount="indefinite"
								values="0;1;1;0"
								keyTimes="0;0.15;0.8;1"
							/>
						</circle>
					))}
				</g>
			</svg>

			{/* Your machine — right-center sits at (56, 88) */}
			<div className="absolute left-2 top-[64px] flex size-12 items-center justify-center rounded-2xl border border-border bg-background shadow-sm">
				<div className="pointer-events-none absolute -inset-1.5 rounded-[1.375rem] border border-foreground/40 opacity-[0.12] motion-safe:[animation:outbound-glow_3s_ease-in-out_infinite]" />
				<Terminal className="size-5 text-foreground/80" />
			</div>
			<span className="absolute left-8 top-[118px] -translate-x-1/2 whitespace-nowrap text-xs font-medium text-muted-foreground">
				Your machine
			</span>

			{/* Destination chips — left edge at x=148, uniform width */}
			{ENDPOINTS.map((endpoint, i) => (
				<div
					key={endpoint.label}
					className={cn(
						"absolute left-[148px] flex w-28 items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5",
						CHIP_TOP[i],
					)}
				>
					<endpoint.icon className="size-4 shrink-0 text-foreground/70" />
					<span className="text-sm font-medium text-foreground">
						{endpoint.label}
					</span>
				</div>
			))}
		</div>
	);
}

function sourceUrl(slug: string) {
	return `${repo.url}/tree/main/packages/lib/src/providers/${slug}`;
}

export default function SecurityPage() {
	return (
		<div className="mx-auto flex max-w-7xl flex-col gap-8 sm:gap-16 p-6 sm:py-16">
			<Header />

			<main className="flex flex-col gap-16 mt-8 lg:mt-0">
				{/* Hero */}
				<section className="flex flex-col gap-8">
					<h1 className="font-heading max-w-2xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
						Your credentials never leave your machine
					</h1>
					<p className="max-w-2xl text-lg text-muted-foreground">
						{site.name} is a status bar module, not a service — no account, no
						server, no middleman. Here's exactly what it reads and who it talks
						to.
					</p>
				</section>

				{/* What it never does */}
				<section className="flex flex-col gap-6">
					<div className="flex flex-col gap-2">
						<h2 className="font-heading text-2xl font-semibold tracking-tight">
							What {site.name} never does
						</h2>
						<p className="max-w-2xl text-muted-foreground">
							The privacy guarantees come from what the code simply doesn't
							contain.
						</p>
					</div>

					<div className="grid gap-4 sm:grid-cols-2">
						{NEVER.map((item) => (
							<div
								key={item.title}
								className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5"
							>
								<div className="flex size-10 shrink-0 items-center justify-center rounded-2xl border border-border bg-background text-foreground/70">
									<item.icon className="size-5" />
								</div>
								<h3 className="font-heading text-base font-semibold text-foreground">
									<span className="text-muted-foreground/60">Never </span>
									{item.title.toLowerCase()}
								</h3>
								<p className="text-sm leading-relaxed text-muted-foreground">
									{item.body}
								</p>
							</div>
						))}
					</div>
				</section>

				{/* How it works */}
				<section className="flex flex-col gap-6">
					<div className="flex flex-col gap-2">
						<h2 className="font-heading text-2xl font-semibold tracking-tight">
							How it actually works
						</h2>
						<p className="max-w-2xl text-muted-foreground">
							Every refresh is the same three local steps.
						</p>
					</div>

					<div className="grid gap-4 sm:grid-cols-3">
						{STEPS.map((step, i) => (
							<div
								key={step.title}
								className="relative flex flex-col gap-3 overflow-hidden rounded-2xl border border-border bg-card p-5"
							>
								<span className="absolute right-4 top-4 font-heading text-3xl font-semibold text-foreground/[0.06]">
									{i + 1}
								</span>
								<div className="flex size-10 shrink-0 items-center justify-center rounded-2xl border border-border bg-background text-foreground/70">
									<step.icon className="size-5" />
								</div>
								<h3 className="font-heading text-base font-semibold text-foreground">
									{step.title}
								</h3>
								<p className="text-sm leading-relaxed text-muted-foreground">
									{step.body}
								</p>
							</div>
						))}
					</div>
				</section>

				{/* Where each provider reads from */}
				<section className="flex flex-col gap-6">
					<div className="flex flex-col gap-2">
						<h2 className="font-heading text-2xl font-semibold tracking-tight">
							Where each provider reads from
						</h2>
						<p className="max-w-2xl text-muted-foreground">
							Every token comes from a file another tool created, or from the
							provider's own CLI. {site.name} writes to none of them.
						</p>
					</div>

					<div className="overflow-hidden rounded-2xl border border-border bg-card">
						<div className="flex items-center justify-between gap-2 border-b border-border bg-muted px-4 py-2.5 text-xs font-medium text-muted-foreground">
							<span>Provider</span>
							<span>Reads from</span>
						</div>
						<ul className="divide-y divide-border">
							{SUPPORTED_PROVIDERS.map((provider) => {
								const src = CREDENTIAL_SOURCES[provider.slug];
								return (
									<li key={provider.slug}>
										<a
											href={sourceUrl(provider.slug)}
											target="_blank"
											rel="noreferrer"
											aria-label={`View ${provider.name} source`}
											className="group flex flex-col gap-3 p-4 hover:bg-muted sm:flex-row sm:items-center sm:justify-between sm:gap-6"
										>
											<div className="flex items-center gap-3">
												<div className="flex [--tile:2.25rem] size-(--tile) shrink-0 items-center justify-center rounded-[calc(var(--tile)/4)] border border-border bg-background">
													<img
														src={provider.logo}
														alt={provider.name}
														className="[--logo:1.25rem] size-(--logo) rounded-[calc(var(--logo)/6)] object-contain"
													/>
												</div>
												<div className="flex flex-col">
													<span className="font-heading text-sm font-semibold text-foreground">
														{provider.name}
													</span>
													<span className="text-xs text-muted-foreground/80">
														{src?.note}
													</span>
												</div>
											</div>

											<div className="flex items-center gap-3 sm:shrink-0">
												<code className="w-fit rounded-2xl bg-muted px-2 py-1 font-mono text-xs text-foreground">
													{src?.source}
												</code>
												<ArrowUpRight className="size-4 shrink-0 text-muted-foreground/50 group-hover:text-foreground" />
											</div>
										</a>
									</li>
								);
							})}
						</ul>
					</div>
				</section>

				{/* Every outbound connection */}
				<section className="flex flex-col gap-6">
					<div className="flex flex-col gap-2">
						<h2 className="font-heading text-2xl font-semibold tracking-tight">
							Every outbound connection
						</h2>
						<p className="max-w-2xl text-muted-foreground">
							The complete list of what your machine talks to. There is nothing
							else — no {site.name} endpoint exists for data to be proxied,
							stored, or analyzed.
						</p>
					</div>

					<div className="group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card">
						{/* Visual */}
						<div className="relative flex h-52 w-full items-center justify-center overflow-hidden border-b border-border bg-background/50">
							<div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] opacity-50 [mask-image:linear-gradient(to_bottom,white,transparent)]" />
							<OutboundVisual />
						</div>

						{/* Caption */}
						<div className="flex flex-col gap-2 p-4">
							<h3 className="font-heading text-lg font-semibold text-foreground">
								Direct, and nothing else
							</h3>
							<p className="text-sm leading-relaxed text-muted-foreground">
								Every request starts on your own machine. It reads the token a
								tool you already use has saved, then calls that provider's
								official API directly — the very same endpoint the provider's own
								app talks to. The only other hosts it ever reaches are GitHub, to
								install and self-update, and each provider's public logo image.
								There is no {site.name} server anywhere in that path: nothing is
								proxied through us, nothing is logged, and nothing about your
								usage or credentials is ever collected.
							</p>
						</div>
					</div>
				</section>

				{/* Audit */}
				<section className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 sm:p-10">
					<div className="pointer-events-none absolute inset-0 z-0 hidden bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] opacity-30 [mask-image:radial-gradient(ellipse_60%_80%_at_30%_0%,#000_20%,transparent_100%)] sm:block" />

					<div className="relative z-10 flex flex-col gap-5">
						<div className="flex flex-col gap-2">
							<h2 className="font-heading text-2xl font-semibold tracking-tight">
								Don't trust us — read the code
							</h2>
							<p className="max-w-2xl text-muted-foreground">
								{site.name} is fully open source and dependency-light (pure
								Python and Bash). Every query is a short, readable script you can
								audit line by line.
							</p>
						</div>

						<div className="flex flex-wrap gap-2">
							<a
								href={`${repo.url}/tree/main/packages/lib/src/providers`}
								target="_blank"
								rel="noreferrer"
								className="flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-medium text-black transition-all hover:bg-white/90"
							>
								<FileCode2 className="-ml-1 size-4" />
								Read the query scripts
							</a>
							<a
								href={repo.url}
								target="_blank"
								rel="noreferrer"
								className="flex items-center gap-2 rounded-full border border-border bg-background px-5 py-2.5 text-sm font-medium text-foreground transition-all hover:bg-muted"
							>
								<GithubIcon className="-ml-1 size-4" />
								View on GitHub
							</a>
						</div>
					</div>
				</section>
			</main>

			<Footer />
		</div>
	);
}
