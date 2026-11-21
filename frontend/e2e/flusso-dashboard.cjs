// Dashboard nel browser: studio nuovo senza numeri → tre appuntamenti (uno disdetto) → riquadri,
// andamento con dettagli al passaggio del mouse, prestazioni → cambio periodo → vista telefono.
//
// Uso: come flusso-accesso.cjs (backend su :8000 con EMAIL_BACKEND=file, frontend su :3000)
//   node frontend/e2e/flusso-dashboard.cjs <cartella>
const { chromium, devices } = require('playwright');
const fs = require('fs'); const path = require('path');
const S = process.argv[2]; const MAIL = path.join(S, 'mail'); const BASE = 'http://localhost:3000';
const stamp = Date.now().toString(36);
const owner = { email: `chiara.${stamp}@example.com`, password: 'Tramonto-sul-lago-7' };
const mails = (to) => fs.readdirSync(MAIL).sort().map((f) => fs.readFileSync(path.join(MAIL, f), 'utf8').replace(/=\r?\n/g, '').replace(/=3D/g, '=')).filter((r) => r.includes(`To: ${to}`));
function lastLink(p, to) { for (const raw of mails(to).reverse()) { const m = raw.match(new RegExp(`${p.replace(/\//g, '\\/')}\\?token=([A-Za-z0-9_-]+)`)); if (m) return `${BASE}${p}?token=${m[1]}`; } throw new Error('email non trovata per ' + p); }
const step = (n) => console.log('✓', n);

// Domani a Roma, e il periodo del menu che lo contiene (il mese, salvo l'ultimo giorno del mese).
const romeDay = (d) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Rome' }).format(d);
const tomorrow = romeDay(new Date(Date.now() + 864e5));
const todayStr = romeDay(new Date());
const period = tomorrow.slice(0, 7) === todayStr.slice(0, 7) ? 'month' : tomorrow.slice(0, 4) === todayStr.slice(0, 4) ? 'year' : 'week';

(async () => {
  const browser = await chromium.launch(); const errors = [];
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Europe/Rome' })).newPage();
  global.__page = page; page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(`${BASE}/registrati`);
  await page.getByLabel('Nome dello studio', { exact: true }).fill('Fisio Conti');
  await page.getByLabel('Attività', { exact: true }).selectOption('nutrizionista');
  await page.getByLabel('Nome e cognome', { exact: true }).fill('Chiara Conti');
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Password', { exact: true }).fill(owner.password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Crea il tuo studio' }).click();
  await page.getByText('Controlla la tua email').waitFor();
  await page.goto(lastLink('/verifica-email', owner.email));
  await page.waitForURL(`${BASE}/app`);
  await page.getByRole('heading', { name: 'I numeri dello studio' }).waitFor();
  await page.getByText('Nessun appuntamento nel periodo').waitFor();
  step('studio nuovo: sezione "I numeri dello studio" vuota');

  const hours = [9, 10, 11];
  const svcName = await page.evaluate(async ({ day, hours }) => {
    const j = (r) => r.json();
    const send = (u, b, m = 'POST') => fetch(`/api/v1${u}`, { method: m, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(j);
    const prof = (await fetch('/api/v1/professionals').then(j))[0];
    const svc = (await fetch('/api/v1/services').then(j))[0];
    await send(`/services/${svc.id}`, { price: '60.00' }, 'PATCH');
    await send(`/professionals/${prof.id}/availability`, { rules: [1, 2, 3, 4, 5, 6, 7].map((d) => ({ weekday: d, start_time: '09:00', end_time: '13:00' })) }, 'PUT');
    const c = await send('/clients', { first_name: 'Marco', last_name: 'Riva' });
    const made = [];
    for (const h of hours) {
      const start = new Date(`${day}T${String(h).padStart(2, '0')}:00:00`); // ora di Roma (fuso del browser)
      made.push(await send('/appointments', { client_id: c.id, professional_id: prof.id, service_id: svc.id, start_at: start.toISOString(), force: true }));
    }
    await send(`/appointments/${made[0].id}/status`, { version: made[0].version, status: 'cancelled_by_staff' });
    return svc.name;
  }, { day: tomorrow, hours });
  step(`tre appuntamenti domani (${tomorrow}), uno disdetto dallo studio`);

  await page.reload();
  await page.getByLabel('Periodo').selectOption(period);
  const tile = (label) => page.locator('dl > div').filter({ has: page.locator('dt', { hasText: label }) });
  await tile('Appuntamenti').getByText('3', { exact: true }).waitFor();
  await tile('Disdette').getByText('33%', { exact: true }).waitFor();
  await tile('Clienti nuovi').getByText('1', { exact: true }).waitFor();
  await tile('Incassato').getByText(/120\s€ previsti/).waitFor();
  await page.getByRole('cell', { name: svcName, exact: true }).waitFor();
  step('riquadri: 3 appuntamenti, disdette 33%, 1 cliente nuovo, 120 € previsti; tabella prestazioni');

  const bar = page.getByRole('listitem', { name: new RegExp(`: 3 appuntamenti$`) });
  await bar.hover();
  await page.getByText('3 appuntamenti · 0 svolti · 1 disdetti · 0 assenti').waitFor();
  step('andamento: passando sopra la barra di domani si leggono i dettagli');
  await page.screenshot({ path: `${S}/s7-1-dashboard.png`, fullPage: true });

  await page.getByLabel('Periodo').selectOption('last_month');
  await page.getByText('Nessun appuntamento nel periodo').waitFor();
  await tile('Appuntamenti').getByText('0', { exact: true }).waitFor();
  step('mese scorso: nessun appuntamento');

  const phone = await (await browser.newContext({ ...devices['iPhone 13'], timezoneId: 'Europe/Rome' })).newPage();
  phone.on('pageerror', (e) => errors.push(e.message));
  await phone.goto(`${BASE}/accedi`);
  await phone.getByLabel('Email', { exact: true }).fill(owner.email);
  await phone.getByLabel('Password', { exact: true }).fill(owner.password);
  await phone.getByRole('button', { name: 'Accedi' }).click();
  await phone.waitForURL(`${BASE}/app`);
  await phone.getByLabel('Periodo').selectOption(period);
  await phone.locator('dl > div').filter({ has: phone.locator('dt', { hasText: 'Appuntamenti' }) }).getByText('3', { exact: true }).waitFor();
  const overflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 0) throw new Error(`scorrimento orizzontale di ${overflow}px sul telefono`);
  await phone.screenshot({ path: `${S}/s7-2-dashboard-telefono.png`, fullPage: true });
  step('telefono: numeri leggibili, nessuno scorrimento orizzontale');

  if (errors.length) throw new Error('errori JavaScript: ' + errors.join(' | '));
  console.log('\nFlusso dashboard completato senza errori.');
  await browser.close();
})().catch(async (e) => { console.error('✗', e.message); try { await global.__page.screenshot({ path: `${S}/s7-errore.png`, fullPage: true }); } catch {} process.exit(1); });
