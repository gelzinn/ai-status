import { repo } from "@/lib/env";

export const dynamic = "force-dynamic";

export async function GET() {
	try {
		const response = await fetch(repo.apiUrl, {
			headers: { Accept: "application/vnd.github+json" },
			next: { revalidate: 300 },
			signal: AbortSignal.timeout(5000),
		});
		if (response.ok) {
			const release = await response.json();
			const installer = Array.isArray(release.assets)
				? release.assets.find((asset: { name?: string; browser_download_url?: string }) =>
					/^ai-status-.+-windows-x64-setup\.exe$/.test(asset.name ?? "") &&
					asset.browser_download_url?.startsWith(`${repo.url}/releases/download/`),
				)
				: undefined;
			if (installer) return Response.redirect(installer.browser_download_url, 307);
		}
	} catch {
		// Release metadata may be unavailable; verified preview builds stay reachable.
	}
	return Response.redirect(`${repo.url}/actions/workflows/windows.yml`, 307);
}
