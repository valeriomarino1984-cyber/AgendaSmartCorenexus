/** Copia di runtime di apps/web/next.config.ts (sul server non serve TypeScript). Tenerle allineate. */
const { headerRules } = require("./security-headers.js");

module.exports = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  // Vedi apps/web/next.config.ts: niente riscritture su disco delle pagine in cache.
  experimental: { isrFlushToDisk: false },
  async headers() {
    return headerRules();
  },
};
