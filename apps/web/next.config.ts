import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.resolve(__dirname, "../.."),
  outputFileTracingIncludes: {
    "/": ["../../package.json"],
    "/opengraph-image": ["../../package.json"],
    "/macos": ["../../packages/lib/MACOS.md"],
  },
};

export default nextConfig;
