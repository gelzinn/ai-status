import { repo, site } from "./env";

const guidePages: Record<string, string> = {
  "INSTALL.md": "/linux",
  "LLMS.md": "/llms.txt",
  "MACOS.md": "/macos",
  "WINDOWS.md": "/windows",
  "PROVIDERS.md": "/providers",
};

/** Resolve repository-relative documentation links for HTML and plain-text guides. */
export function resolveLibGuideLinks(markdown: string): string {
  return markdown.replace(/\]\(([^\s)]+\.md(?:#[^\s)]*)?)\)/g, (link, target: string) => {
    if (/^(?:[a-z][a-z\d+.-]*:|\/|#)/i.test(target)) return link;
    const [filename, fragment = ""] = target.split("#", 2);
    // The provider index is a catalog; detailed reference fragments live in
    // the repository's authentication guide.
    const page = filename === "PROVIDERS.md" && fragment ? undefined : guidePages[filename];
    const url = page
      ? `${site.url}${page}${fragment ? `#${fragment}` : ""}`
      : new URL(target, `${repo.url}/blob/main/packages/lib/`).href;
    return `](${url})`;
  });
}
