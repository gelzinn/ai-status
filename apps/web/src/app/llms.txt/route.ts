import { readFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-static";

export async function GET() {
  const mdPath = path.resolve(
    process.cwd(),
    "../../packages/lib/INSTALL.md",
  );
  const content = await readFile(mdPath, "utf-8");
  return new Response(content, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
