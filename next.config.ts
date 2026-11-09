import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["node:sqlite"],
  devIndicators: false,
  outputFileTracingExcludes: {
    "/*": ["./data/**/*", "./outputs/**/*", "./sources/**/*", "./artifacts/**/*", "./workbook/**/*"],
  },
};

export default nextConfig;
