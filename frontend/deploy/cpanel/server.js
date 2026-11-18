// File di avvio per cPanel "Setup Node.js App" (Phusion Passenger), come in Presenze.
// Passenger intercetta listen(): la porta conta solo se lo si avvia a mano.
const http = require("http");
const next = require("next");

const port = Number(process.env.PORT) || 3000;
const hostname = "localhost";
const app = next({ dev: false, dir: __dirname, hostname, port });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  http
    .createServer((req, res) => handle(req, res))
    .listen(port, () => {
      console.log(`Agenda (web) avviata (NODE_ENV=${process.env.NODE_ENV})`);
    });
});
