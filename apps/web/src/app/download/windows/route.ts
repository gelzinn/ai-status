import { getWindowsDownload } from "@/lib/windows-download";

export const dynamic = "force-dynamic";

export async function GET() {
	const download = await getWindowsDownload();
	return Response.redirect(download.href, 307);
}
