import type { MetadataRoute } from "next";
import { SUPPORTED_PROVIDERS } from "@ai-status/shared";
import { site } from "@/lib/env";

export default function sitemap(): MetadataRoute.Sitemap {
  const pages = ["", "/linux", "/windows", "/macos", "/providers", "/security", "/changelog"];
  return [
    ...pages.map((page) => ({ url: `${site.url}${page}` })),
    ...SUPPORTED_PROVIDERS.map((provider) => ({
      url: `${site.url}/providers/${provider.slug}`,
    })),
  ];
}
