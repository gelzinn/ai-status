import { readFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-static";

// Serves packages/lib/install.sh from a short, memorable URL so users can run
//   curl -fsSL https://ai-status.gelzin.com/install | bash
// instead of the long raw.githubusercontent.com path. Same approach as
// /llms.txt — the file is read from the repo at build time.
export async function GET() {
  const scriptPath = path.resolve(
    process.cwd(),
    "../../packages/lib/install.sh",
  );
  const content = await readFile(scriptPath, "utf-8");
  return new Response(content, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
