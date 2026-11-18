#!/bin/sh
# Pacchetto per cPanel "Setup Node.js App": app compilata (.next), file pubblici, server.js e un
# package.json con le sole dipendenze di runtime a versione fissa ("Run NPM Install" le installa).
set -e
cd "$(dirname "$0")/.."
pnpm --filter web build
WEB=apps/web
OUT=dist/cpanel-web
rm -rf "$OUT" dist/agenda-web-cpanel.zip
mkdir -p "$OUT/tmp"
cp -r "$WEB/.next" "$OUT/.next"
rm -rf "$OUT/.next/cache" "$OUT/.next/dev"
# Marcatore vuoto scritto da Next.js in fase di build e non letto all'avvio: i file da 0 byte
# interrompono il caricamento FTPS su Netsons (errore TLS sul canale dati).
rm -f "$OUT/.next/turbopack"
cp -r "$WEB/public" "$OUT/public"
cp deploy/cpanel/server.js deploy/cpanel/next.config.js "$WEB/security-headers.js" "$OUT/"
# Versioni esatte installate (dal lockfile pnpm), solo dipendenze di produzione.
pnpm --filter web list --prod --json --depth 0 > dist/web-deps.json
node -e '
const fs = require("fs");
const [list] = JSON.parse(fs.readFileSync("dist/web-deps.json", "utf8"));
const deps = {};
for (const [name, info] of Object.entries(list.dependencies || {})) deps[name] = info.version;
const pkg = JSON.parse(fs.readFileSync("apps/web/package.json", "utf8"));
fs.writeFileSync(process.argv[1], JSON.stringify({
  name: "agenda-web", version: pkg.version, private: true,
  scripts: { start: "node server.js" },
  engines: { node: ">=20.9" },
  dependencies: deps,
}, null, 2) + "\n");
' "$OUT/package.json"
rm -f dist/web-deps.json
if [ -n "$(find "$OUT" -type f -size 0)" ]; then
  echo "Errore: file vuoti nel pacchetto (danno errore TLS nel caricamento FTPS):" >&2
  find "$OUT" -type f -size 0 >&2
  exit 1
fi
(cd "$OUT" && zip -qr ../agenda-web-cpanel.zip .)
echo "Pacchetto pronto: frontend/dist/agenda-web-cpanel.zip"
