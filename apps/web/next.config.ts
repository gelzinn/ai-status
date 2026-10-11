import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.resolve(__dirname, "../.."),
  outputFileTracingIncludes: {
    "/": ["../../packages/lib/VERSION"],
    "/opengraph-image": ["../../packages/lib/VERSION"],
    "/macos": ["../../packages/lib/MACOS.md"],
  },
};

export default nextConfig;
