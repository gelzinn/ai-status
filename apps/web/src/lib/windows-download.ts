import { repo } from "./env";

export type WindowsDownload = {
  kind: "release" | "preview";
  href: string;
};

/** Keep download links and preview notices based on the same release metadata. */
export async function getWindowsDownload(): Promise<WindowsDownload> {
  try {
    const response = await fetch(repo.apiUrl, {
      headers: { Accept: "application/vnd.github+json" },
      next: { revalidate: 300 },
      signal: AbortSignal.timeout(5000),
    });
    if (response.ok) {
      const release = await response.json();
      const installer = Array.isArray(release?.assets)
        ? release.assets.find((asset: { name?: unknown; browser_download_url?: unknown } | null) =>
            typeof asset?.name === "string" &&
            /^ai-status-.+-windows-x64-setup\.exe$/.test(asset.name) &&
            typeof asset.browser_download_url === "string" &&
            asset.browser_download_url.startsWith(`${repo.url}/releases/download/`),
          )
        : undefined;
      if (installer) return { kind: "release", href: installer.browser_download_url };
    }
  } catch {
    // Release metadata may be unavailable; preview builds remain reachable.
  }
  return { kind: "preview", href: `${repo.url}/actions/workflows/windows.yml` };
}
