import type { ImgHTMLAttributes } from "react";

export function LinuxIcon(props: ImgHTMLAttributes<HTMLImageElement>) {
	return <img src="https://svgl.app/library/linux.svg" alt="Linux" {...props} />;
}

export function AppleIcon(props: ImgHTMLAttributes<HTMLImageElement>) {
	return <img src="https://svgl.app/library/apple_dark.svg" alt="Apple" {...props} />;
}

export function WindowsIcon(props: ImgHTMLAttributes<HTMLImageElement>) {
	return <img src="/windows-11.svg" alt="Windows" {...props} />;
}
