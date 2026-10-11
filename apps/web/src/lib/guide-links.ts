import { repo, site } from "./env";

const guidePages: Record<string, string> = {
  "MACOS.md": "/macos",
  "WINDOWS.md": "/windows",
  "PROVIDERS.md": "/providers",
};

/** Resolve repository-relative documentation links for HTML and plain-text guides. */
export function resolveLibGuideLinks(markdown: string): string {
  return markdown.replace(/\]\(([^\s)]+\.md(?:#[^\s)]*)?)\)/g, (link, target: string) => {
    if (/^(?:[a-z][a-z\d+.-]*:|\/|#)/i.test(target)) return link;
    const page = guidePages[target];
    const url = page
      ? `${site.url}${page}`
      : new URL(target, `${repo.url}/blob/main/packages/lib/`).href;
    return `](${url})`;
  });
}
