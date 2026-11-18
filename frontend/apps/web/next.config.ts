import type { NextConfig } from "next";
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { headerRules } = require("./security-headers.js");

// Tenere allineato con frontend/deploy/cpanel/next.config.js (copia usata in produzione su cPanel).
const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  // In basso a sinistra coprirebbe l'account nella barra laterale (solo sviluppo).
  devIndicators: { position: "bottom-right" },
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
  // Solo in sviluppo: /api va al backend locale. In produzione su cPanel /api è servito
  // direttamente dall'app Python (stesso dominio), quindi niente inoltro.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    const target = process.env.AGENDA_API_DEV_URL ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
};

export default nextConfig;
