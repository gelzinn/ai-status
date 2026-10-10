import { readFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-static";

export async function GET() {
  const content = await readFile(path.resolve(process.cwd(), "../../packages/lib/WINDOWS.md"), "utf-8");
  return new Response(content, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
