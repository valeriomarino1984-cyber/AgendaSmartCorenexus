// File di avvio per cPanel "Setup Node.js App" (Passenger / LiteSpeed), come in Presenze.
// Passenger intercetta listen(): la porta conta solo se lo si avvia a mano.
const fs = require("fs");
const http = require("http");
const path = require("path");
const next = require("next");

// Cache delle pagine che Next.js scrive su disco (.next/server/route-cache): il deploy non la
// tocca e sopravvive ai riavvii, quindi dopo un aggiornamento potrebbe servire pagine della
// versione precedente. La scrittura è disattivata (isrFlushToDisk: false in next.config.js);
// per sicurezza la cartella viene svuotata a ogni avvio.
fs.rmSync(path.join(__dirname, ".next", "server", "route-cache"), { recursive: true, force: true });

const port = Number(process.env.PORT) || 3000;
const hostname = "localhost";
const app = next({ dev: false, dir: __dirname, hostname, port });
const handle = app.getRequestHandler();

// Riavvio dopo un deploy: il workflow carica una nuova tmp/restart.txt. Su Netsons il server
// web non sempre riavvia l'app Node.js da solo, e Next.js continuerebbe a servire dalla memoria
// le pagine della versione precedente (che puntano a CSS/JS ormai cancellati).
// Se il file cambia dopo l'avvio, il processo termina e il server web ne avvia uno nuovo.
const RESTART_FILE = path.join(__dirname, "tmp", "restart.txt");
function restartStamp() {
  try {
    return fs.statSync(RESTART_FILE).mtimeMs;
  } catch {
    return 0;
  }
}
const bootStamp = restartStamp();
setInterval(() => {
  if (restartStamp() > bootStamp) {
    console.log("Nuova versione caricata: riavvio del processo");
    process.exit(0);
  }
}, 5000).unref();

app.prepare().then(() => {
  http
    .createServer((req, res) => handle(req, res))
    .listen(port, () => {
      console.log(`Agenda (web) avviata (NODE_ENV=${process.env.NODE_ENV})`);
    });
});
