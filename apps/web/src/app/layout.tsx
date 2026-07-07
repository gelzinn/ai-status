import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { DM_Sans } from "next/font/google";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { PROJECT_NAME, PROJECT_DESCRIPTION } from "@/lib/env";

import "./globals.css";

const description = PROJECT_DESCRIPTION;

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  title: `${PROJECT_NAME} | Waybar Module`,
  description,
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    title: PROJECT_NAME,
    description,
    siteName: PROJECT_NAME,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={cn(
        GeistSans.variable,
        GeistMono.variable,
        dmSans.variable,
        "font-sans",
      )}
    >
      <body className="overflow-x-clip">{children}</body>
    </html>
  );
}
