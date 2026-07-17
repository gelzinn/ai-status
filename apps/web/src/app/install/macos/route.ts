import { readFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-static";

// Serves packages/lib/install-macos.sh from a short, memorable URL so users can run
//   curl -fsSL https://ai-status.gelzin.com/install/macos | bash
// The macOS installer drops a SwiftBar plugin; the Linux one (/install) wires
// Waybar. Same build-time file read as /install and /llms.txt.
export async function GET() {
  const scriptPath = path.resolve(
    process.cwd(),
    "../../packages/lib/install-macos.sh",
  );
  const content = await readFile(scriptPath, "utf-8");
  return new Response(content, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
