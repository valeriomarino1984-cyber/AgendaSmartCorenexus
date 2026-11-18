// Area piattaforma nel browser: prima configurazione via email → password e app dei codici
// (QR) → pannello → nuovo studio con invito al titolare → sospensione → uscita → accesso con
// password + codice a 6 cifre.
//
// Uso: backend su :8000 con EMAIL_BACKEND=file, PLATFORM_SECRET_KEY (≥32 caratteri) e
// PLATFORM_BOOTSTRAP_EMAIL=<email>, tabelle platform_* vuote; frontend su :3000
//   node frontend/e2e/flusso-piattaforma.cjs <cartella> <email-bootstrap>
const { chromium } = require('playwright');
const crypto = require('crypto');
const fs = require('fs'); const path = require('path');
const S = process.argv[2]; const BOOT = process.argv[3]; const MAIL = path.join(S, 'mail'); const BASE = 'http://localhost:3000';
const stamp = Date.now().toString(36);

function lastLink(pathPart, to) {
  for (const f of fs.readdirSync(MAIL).sort().reverse()) {
    const raw = fs.readFileSync(path.join(MAIL, f), 'utf8').replace(/=\r?\n/g, '').replace(/=3D/g, '=');
    if (to && !raw.includes(`To: ${to}`)) continue;
    const m = raw.match(new RegExp(`${pathPart.replace(/\//g, '\\/')}\\?token=([A-Za-z0-9_-]+)`));
    if (m) return `${BASE}${pathPart}?token=${m[1]}`;
  }
  throw new Error('email non trovata per ' + pathPart);
}
function b32decode(s) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'; let bits = ''; const out = [];
  for (const c of s.replace(/[\s=]/g, '')) bits += alphabet.indexOf(c).toString(2).padStart(5, '0');
  for (let i = 0; i + 8 <= bits.length; i += 8) out.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(out);
}
function totp(secret, offset = 0) { // come un'app di autenticazione
  const step = Math.floor(Date.now() / 30000) + offset; const buf = Buffer.alloc(8); buf.writeBigUInt64BE(BigInt(step));
  const mac = crypto.createHmac('sha1', secret).update(buf).digest(); const o = mac[mac.length - 1] & 15;
  return String((mac.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, '0');
}
const step = (n) => console.log('✓', n);

(async () => {
  const browser = await chromium.launch(); const errors = [];
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  global.__page = page; page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(`${BASE}/piattaforma`);
  await page.getByRole('heading', { name: 'Prima configurazione' }).waitFor();
  await page.getByLabel('Email', { exact: true }).fill(BOOT);
  await page.getByRole('button', { name: 'Invia il link' }).click();
  await page.getByText(/riceverai un'email/).waitFor();
  step('prima configurazione: link richiesto con l\'email prevista');

  await page.goto(lastLink('/piattaforma/invito', BOOT));
  await page.getByRole('heading', { name: "Configura l'accesso" }).waitFor();
  await page.locator('svg').filter({ has: page.locator('path') }).first().waitFor();
  const secret = b32decode(await page.locator('p.select-all').innerText());
  await page.getByLabel('Nome e cognome').fill('Valeria Marino');
  await page.getByLabel('Password', { exact: true }).fill('Piattaforma-sicura-2026');
  await page.getByLabel('Ripeti la password').fill('Piattaforma-sicura-2026');
  await page.getByLabel("Codice a 6 cifre mostrato dall'app").fill(totp(secret));
  await page.screenshot({ path: `${S}/pf-1-invito.png`, fullPage: true });
  await page.getByRole('button', { name: "Attiva l'accesso" }).click();
  await page.waitForURL(`${BASE}/piattaforma`);
  await page.getByRole('heading', { name: 'Pannello CoreNexus' }).waitFor();
  step('password scelta, app collegata con il QR, codice verificato → pannello');

  const owner = `titolare.${stamp}@example.com`;
  await page.getByText('Nuovo studio').click();
  await page.getByLabel('Nome dello studio').fill(`Fisioterapia Lago ${stamp}`);
  await page.getByLabel('Attività').selectOption('fisioterapista');
  await page.getByLabel('Nome del titolare').fill('Giorgio Lago');
  await page.getByLabel('Email del titolare').fill(owner);
  await page.getByRole('button', { name: 'Crea studio e invita il titolare' }).click();
  await page.getByText(`Studio creato: invito inviato a ${owner}`).waitFor();
  lastLink('/invito', owner);
  await page.getByText(`Fisioterapia Lago ${stamp}`, { exact: true }).click();
  await page.getByText('Invito in attesa').first().waitFor();
  await page.screenshot({ path: `${S}/pf-2-studi.png`, fullPage: true });
  step('studio creato con profilo fisioterapista, invito email al titolare');

  await page.getByRole('button', { name: 'Sospendi' }).click();
  await page.getByText('Studio sospeso').waitFor();
  await page.getByRole('button', { name: 'Riattiva in prova' }).click();
  await page.getByText('Studio riattivato in prova').waitFor();
  step('studio sospeso e riattivato');

  await page.getByRole('radio', { name: 'Registro' }).click();
  await page.getByText('Studio creato').first().waitFor();
  await page.screenshot({ path: `${S}/pf-3-registro.png`, fullPage: true });
  step('registro delle azioni');

  await page.getByRole('button', { name: 'Esci' }).click();
  await page.getByRole('heading', { name: 'Accesso piattaforma' }).waitFor();
  await page.locator('input[autocomplete=username]:visible').fill(BOOT);
  await page.locator('input[autocomplete=current-password]:visible').fill('Piattaforma-sicura-2026');
  await page.getByRole('button', { name: 'Continua' }).click();
  await page.locator('input[autocomplete=one-time-code]:visible').fill('000000');
  await page.getByRole('button', { name: 'Accedi' }).click();
  await page.getByText('Codice non valido').waitFor();
  await page.locator('input[autocomplete=one-time-code]:visible').fill(totp(secret, 1));
  await page.getByRole('button', { name: 'Accedi' }).click();
  await page.getByRole('heading', { name: 'Pannello CoreNexus' }).waitFor();
  step('uscita e nuovo accesso: password + codice (codice errato rifiutato)');

  if (errors.length) throw new Error('errori JavaScript: ' + errors.join(' | '));
  step('nessun errore JavaScript'); await browser.close();
})().catch(async (e) => { console.error('✗', e.message); await global.__page?.screenshot({ path: `${S}/errore.png` }).catch(() => null); process.exit(1); });
