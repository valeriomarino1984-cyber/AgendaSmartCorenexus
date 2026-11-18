import type { NextConfig } from "next";
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { headerRules } = require("./security-headers.js");

// Tenere allineato con frontend/deploy/cpanel/next.config.js (copia usata in produzione su cPanel).
const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return headerRules();
  },
};

export default nextConfig;
