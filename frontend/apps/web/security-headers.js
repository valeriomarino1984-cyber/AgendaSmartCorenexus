/**
 * Header di sicurezza per tutte le pagine (da Presenze; usati da next.config.ts e dalla copia per cPanel).
 * Niente script-src restrittiva: Next.js usa script inline; si blocca invece l'incorporamento in altri siti.
 */
const securityHeaders = [
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "geolocation=(), camera=(), microphone=(), payment=(), usb=(), interest-cohort=()" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

/** Regole per next.config: stessi header su tutte le pagine (l'API Python imposta i propri). */
function headerRules() {
  return [{ source: "/:path*", headers: securityHeaders }];
}

module.exports = { securityHeaders, headerRules };
