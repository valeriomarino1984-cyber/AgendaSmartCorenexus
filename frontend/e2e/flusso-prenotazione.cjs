// Prenotazione online nel browser: lo studio attiva la pagina → un cliente (telefono, senza
// accesso) prenota scegliendo prestazione, giorno e ora → email di conferma → appuntamento in
// agenda → un secondo cliente sullo stesso orario viene fermato → pagina spenta "non disponibile".
//
// Uso: come flusso-accesso.cjs (backend su :8000 con EMAIL_BACKEND=file, frontend su :3000)
//   node frontend/e2e/flusso-prenotazione.cjs <cartella>
const { chromium, devices } = require('playwright');
const fs = require('fs'); const path = require('path');
const S = process.argv[2]; const MAIL = path.join(S, 'mail'); const BASE = 'http://localhost:3000';
const stamp = Date.now().toString(36);
const owner = { email: `lucia.${stamp}@example.com`, password: 'Tramonto-sul-lago-7' };
const cliente = `pietro.${stamp}@example.com`;
const mails = (to) => fs.readdirSync(MAIL).sort().map((f) => fs.readFileSync(path.join(MAIL, f), 'utf8').replace(/=\r?\n/g, '').replace(/=3D/g, '=')).filter((r) => r.includes(`To: ${to}`));
function lastLink(p, to) { for (const raw of mails(to).reverse()) { const m = raw.match(new RegExp(`${p.replace(/\//g, '\\/')}\\?token=([A-Za-z0-9_-]+)`)); if (m) return `${BASE}${p}?token=${m[1]}`; } throw new Error('email non trovata per ' + p); }
const step = (n) => console.log('✓', n);

(async () => {
  const browser = await chromium.launch(); const errors = [];
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Europe/Rome' })).newPage();
  global.__page = page; page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`${BASE}/registrati`);
  await page.getByLabel('Nome dello studio', { exact: true }).fill(`Fisio Riva ${stamp}`);
  await page.getByLabel('Attività', { exact: true }).selectOption('fisioterapista');
  await page.getByLabel('Nome e cognome', { exact: true }).fill('Lucia Riva');
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Password', { exact: true }).fill(owner.password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Crea il tuo studio' }).click();
  await page.getByText('Controlla la tua email').waitFor();
  await page.goto(lastLink('/verifica-email', owner.email));
  await page.waitForURL(`${BASE}/app`);
  await page.evaluate(async () => {
    const prof = (await fetch('/api/v1/professionals').then((r) => r.json()))[0];
    await fetch(`/api/v1/professionals/${prof.id}/availability`, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules: [1, 2, 3, 4, 5, 6, 7].map((d) => ({ weekday: d, start_time: '08:00', end_time: '20:00' })) }) });
  });

  await page.getByRole('link', { name: 'Prenotazioni online', exact: true }).first().click();
  await page.getByText('Spenta: la pagina non è visibile').waitFor();
  await page.getByLabel('Prenotazione online attiva').check();
  await page.getByLabel('Preavviso minimo').selectOption('0');
  await page.getByRole('button', { name: 'Salva', exact: true }).click();
  await page.getByText('Attiva: i clienti possono prenotare').waitFor();
  const url = (await page.locator('p.truncate.num').innerText()).trim();
  await page.screenshot({ path: `${S}/pr-1-studio.png`, fullPage: true });
  step('lo studio attiva la pagina: ' + url.replace(BASE, ''));

  const phone = await browser.newContext({ ...devices['iPhone 13'], timezoneId: 'Europe/Rome' });
  const c = await phone.newPage(); c.on('pageerror', (e) => errors.push(e.message));
  await c.goto(url);
  await c.getByRole('button', { name: /Seduta di fisioterapia/ }).click();
  const day = c.locator('button:has-text("liberi"):not([disabled])').first();
  await day.waitFor();
  await day.click();
  const times = c.locator('section').filter({ hasText: 'Scegli giorno e ora' }).locator('button.rounded-full');
  await times.first().waitFor();
  const chosen = (await times.nth(2).innerText()).trim();
  await times.nth(2).click();
  await c.getByLabel('Nome', { exact: true }).fill('Pietro');
  await c.getByLabel('Cognome', { exact: true }).fill('Sala');
  await c.getByLabel('Email', { exact: true }).fill(cliente);
  await c.getByLabel('Cellulare', { exact: true }).fill('347 111 2233');
  await c.getByText(/Acconsento al trattamento/).click();
  await c.screenshot({ path: `${S}/pr-2-dati.png`, fullPage: true });
  await c.getByRole('button', { name: 'Prenota', exact: true }).click();
  await c.getByRole('heading', { name: 'Prenotazione confermata' }).waitFor();
  await c.screenshot({ path: `${S}/pr-3-confermata.png` });
  step(`il cliente prenota da telefono alle ${chosen}: "Prenotazione confermata"`);

  for (let i = 0; i < 40 && !mails(cliente).some((m) => m.includes('Appuntamento confermato') || m.includes('QXBwdW50YW1lbnRvIGNvbmZlcm1hdG8')); i++) await new Promise((r) => setTimeout(r, 250));
  if (!mails(cliente).length) throw new Error('email di conferma non arrivata');
  step('email di conferma arrivata al cliente');

  const inAgenda = await page.evaluate(async () => {
    const from = new Date(Date.now() - 86400000).toISOString(); const to = new Date(Date.now() + 30 * 86400000).toISOString();
    return (await fetch(`/api/v1/appointments?from=${from}&to=${to}`).then((r) => r.json())).map((a) => `${a.client_name}|${a.source}`);
  });
  if (!inAgenda.includes('Pietro Sala|public_booking')) throw new Error('appuntamento non in agenda: ' + inAgenda);
  step('appuntamento in agenda con origine "prenotazione online"');

  const other = await (await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Europe/Rome' })).newPage();
  other.on('pageerror', (e) => errors.push(e.message));
  await other.goto(url);
  await other.getByRole('button', { name: /Seduta di fisioterapia/ }).click();
  await other.locator('button:has-text("liberi"):not([disabled])').first().click();
  const t2 = other.locator('section').filter({ hasText: 'Scegli giorno e ora' }).locator('button.rounded-full');
  await t2.first().waitFor();
  if ((await t2.allInnerTexts()).map((x) => x.trim()).includes(chosen)) {
    // l'orario preso non deve più comparire tra quelli liberi
    throw new Error(`orario ${chosen} ancora proposto dopo la prenotazione`);
  }
  step(`l'orario ${chosen} non è più proposto agli altri clienti`);

  await page.getByLabel('Prenotazione online attiva').uncheck();
  await page.getByRole('button', { name: 'Salva', exact: true }).click();
  await page.getByText('Spenta: la pagina non è visibile').waitFor();
  await other.goto(url);
  await other.getByText('Pagina non disponibile').waitFor();
  step('pagina spenta: "Pagina non disponibile"');

  if (errors.length) throw new Error('errori JavaScript: ' + errors.join(' | '));
  step('nessun errore JavaScript'); await browser.close();
})().catch(async (e) => { console.error('✗', e.message); await global.__page?.screenshot({ path: `${S}/errore.png` }).catch(() => null); process.exit(1); });
