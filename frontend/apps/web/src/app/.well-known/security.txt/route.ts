// Contatto per chi trova una vulnerabilità (RFC 9116). La scadenza si rinnova a ogni rilascio
// dell'anno: va aggiornata entro la data indicata.

const BODY = [
  "Contact: mailto:info@corenexus.it",
  "Expires: 2027-11-21T00:00:00.000Z",
  "Preferred-Languages: it, en",
  "Canonical: https://agenda.corenexus.it/.well-known/security.txt",
  "",
].join("\n");

export function GET() {
  return new Response(BODY, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
