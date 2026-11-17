/** Copia di runtime di apps/web/next.config.ts (sul server non serve TypeScript). Tenerle allineate. */
const { headerRules } = require("./security-headers.js");

module.exports = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  async headers() {
    return headerRules();
  },
};
