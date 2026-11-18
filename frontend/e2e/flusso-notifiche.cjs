// Notifiche email nel browser: impostazioni → prenotazione per un cliente con consenso →
// email di conferma (mittente con il nome dello studio) → scheda appuntamento e pagina Notifiche →
// spostamento e annullamento con i relativi avvisi → cliente senza consenso "Non inviata".
//
// Uso: come flusso-accesso.cjs (backend su :8000 con EMAIL_BACKEND=file, frontend su :3000)
//   node frontend/e2e/flusso-notifiche.cjs <cartella>
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const S = process.argv[2]; const MAIL = path.join(S, 'mail'); const BASE = 'http://localhost:3000';
const stamp = Date.now().toString(36);
const owner = { email: `rita.${stamp}@example.com`, password: 'Tramonto-sul-lago-7' };
const cliente = `sara.${stamp}@example.com`;

const mails = (to) => fs.readdirSync(MAIL).sort().map((f) => fs.readFileSync(path.join(MAIL, f), 'utf8').replace(/=\r?\n/g, '').replace(/=3D/g, '=')).filter((raw) => raw.includes(`To: ${to}`));
function lastLink(pathPart, to) {
  for (const raw of mails(to).reverse()) {
    const m = raw.match(new RegExp(`${pathPart.replace(/\//g, '\\/')}\\?token=([A-Za-z0-9_-]+)`));
    if (m) return `${BASE}${pathPart}?token=${m[1]}`;
  }
  throw new Error('email non trovata per ' + pathPart);
}
async function waitMail(to, subjectPart) {
  for (let i = 0; i < 40; i++) {
    const found = mails(to).find((m) => {
      const subj = (m.match(/^Subject: (.*)$/m) || [])[1] || '';
      const decoded = subj.includes('=?utf-8?') ? Buffer.from(subj.replace(/.*\?b\?|\?=.*/gi, ''), 'base64').toString() : subj;
      return decoded.includes(subjectPart) || m.includes(subjectPart);
    });
    if (found) return found;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`email "${subjectPart}" non arrivata a ${to}`);
}
const step = (n) => console.log('✓', n);

(async () => {
  const browser = await chromium.launch(); const errors = [];
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Europe/Rome' })).newPage();
  global.__page = page; page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(`${BASE}/registrati`);
  await page.getByLabel('Nome dello studio', { exact: true }).fill('Fisioterapia Monti');
  await page.getByLabel('Attività', { exact: true }).selectOption('fisioterapista');
  await page.getByLabel('Nome e cognome', { exact: true }).fill('Rita Monti');
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Password', { exact: true }).fill(owner.password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Crea il tuo studio' }).click();
  await page.getByText('Controlla la tua email').waitFor();
  await page.goto(lastLink('/verifica-email', owner.email));
  await page.waitForURL(`${BASE}/app`);

  await page.getByRole('link', { name: 'Impostazioni', exact: true }).first().click();
  await page.getByText('Notifiche ai clienti').waitFor();
  await page.getByLabel('Email di contatto', { exact: true }).fill('segreteria@monti.example');
  await page.getByLabel('Promemoria', { exact: true }).selectOption('48');
  await page.getByRole('button', { name: 'Salva', exact: true }).click();
  await page.getByText('Impostazioni salvate').waitFor();
  await page.screenshot({ path: `${S}/nt-1-impostazioni.png`, fullPage: true });
  step('impostazioni: conferme attive, promemoria 48 ore prima');

  const ids = await page.evaluate(async ({ email }) => {
    const j = (r) => r.json();
    const post = (u, b, m = 'POST') => fetch(`/api/v1${u}`, { method: m, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(j);
    const prof = (await fetch('/api/v1/professionals').then(j))[0];
    await post(`/professionals/${prof.id}/availability`, { rules: [1, 2, 3, 4, 5].map((d) => ({ weekday: d, start_time: '09:00', end_time: '13:00' })) }, 'PUT');
    const c1 = await post('/clients', { first_name: 'Sara', last_name: 'Galli', email, email_consent: true });
    const c2 = await post('/clients', { first_name: 'Marco', last_name: 'Neri', email: 'marco.' + email, email_consent: false });
    return { c1: c1.id, c2: c2.id };
  }, { email: cliente });
  step('orario e due clienti (uno con consenso, uno senza)');

  await page.getByRole('link', { name: 'Agenda', exact: true }).first().click();
  await page.getByRole('button', { name: 'Successivo' }).click();
  const col = page.locator('[data-day]').first(); await col.waitFor();
  const box = await col.boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + (10 - 7) * 56 + 4);
  const sheet = page.getByRole('dialog');
  await sheet.getByPlaceholder('Cerca per nome o telefono').fill('galli');
  await sheet.getByRole('button', { name: /Galli Sara/ }).click();
  await sheet.getByRole('button', { name: 'Prenota' }).click();
  await sheet.waitFor({ state: 'detached' });
  const conf = await waitMail(cliente, 'Appuntamento confermato');
  if (!conf.includes('From: "Fisioterapia Monti via Agenda"') && !conf.includes('From: Fisioterapia Monti via Agenda')) throw new Error('mittente senza nome dello studio');
  if (!conf.includes('Reply-To: segreteria@monti.example')) throw new Error('risposta non indirizzata allo studio');
  step('prenotazione dalla griglia → email "Appuntamento confermato" da "Fisioterapia Monti via Agenda"');

  await page.getByRole('button', { name: /^10:00 Sara Galli/ }).click();
  await sheet.getByText('Email al cliente').waitFor();
  await sheet.getByText('Inviata').waitFor();
  await sheet.getByText('In attesa').waitFor();
  await page.screenshot({ path: `${S}/nt-2-scheda.png` });
  step('scheda appuntamento: conferma "Inviata", promemoria "In attesa"');

  await sheet.getByRole('button', { name: 'Sposta o modifica' }).click();
  await sheet.getByLabel('Ora', { exact: true }).fill('11:30');
  await sheet.getByRole('button', { name: 'Salva modifiche' }).click();
  await waitMail(cliente, 'Appuntamento spostato');
  step('spostamento → email "Appuntamento spostato"');

  await sheet.getByRole('button', { name: 'Disdici' }).click();
  await sheet.getByRole('radio', { name: 'Lo studio' }).click();
  await sheet.getByRole('button', { name: 'Conferma disdetta' }).click();
  await waitMail(cliente, 'Appuntamento annullato');
  await sheet.getByRole('button', { name: 'Chiudi' }).first().click();
  step('annullamento → email "Appuntamento annullato"');

  await page.evaluate(async ({ c2 }) => {
    const services = await fetch('/api/v1/services').then((r) => r.json());
    const prof = (await fetch('/api/v1/professionals').then((r) => r.json()))[0];
    const start = new Date(Date.now() + 6 * 86400000); start.setUTCHours(8, 0, 0, 0);
    await fetch('/api/v1/appointments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client_id: c2, professional_id: prof.id, service_id: services[0].id, start_at: start.toISOString(), force: true }) });
  }, ids);
  await page.getByRole('link', { name: 'Notifiche', exact: true }).first().click();
  await page.getByRole('heading', { name: 'Notifiche', exact: true }).waitFor();
  await page.getByText('Manca il consenso ai promemoria via email').first().waitFor();
  await page.getByText('Appuntamento annullato · Sara Galli').waitFor();
  await page.screenshot({ path: `${S}/nt-3-notifiche.png`, fullPage: true });
  step('pagina Notifiche: inviate, in programma e "Non inviata" con il motivo');

  if (errors.length) throw new Error('errori JavaScript: ' + errors.join(' | '));
  step('nessun errore JavaScript'); await browser.close();
})().catch(async (e) => { console.error('✗', e.message); await global.__page?.screenshot({ path: `${S}/errore.png` }).catch(() => null); process.exit(1); });
