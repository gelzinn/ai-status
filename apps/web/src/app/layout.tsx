import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { DM_Sans } from "next/font/google";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { site } from "@/lib/env";

import "./globals.css";

const description = site.description;

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  title: `${site.name} | Waybar Module`,
  description,
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    title: site.name,
    description,
    siteName: site.name,
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
