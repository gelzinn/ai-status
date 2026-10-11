import { readFile } from "node:fs/promises";
import path from "node:path";
import { resolveLibGuideLinks } from "@/lib/guide-links";

export const dynamic = "force-static";

export async function GET() {
  const content = resolveLibGuideLinks(await readFile(path.resolve(process.cwd(), "../../packages/lib/WINDOWS.md"), "utf-8"));
  return new Response(content, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
