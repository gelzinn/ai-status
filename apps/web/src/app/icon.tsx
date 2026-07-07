import { ImageResponse } from "next/og";
import { Logo } from "@/components/logo";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
	return new ImageResponse(
		<Logo style={{ width: "100%", height: "100%" }} />,
		{ ...size }
	);
}
