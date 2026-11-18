// Area clienti nel browser: lo studio prenota una visita online per un cliente con email →
// il cliente chiede il link, entra senza password, vede l'appuntamento con la videochiamata,
// disdice; le due aree restano separate (il cliente non entra nell'area dello studio).
//
// Uso: come flusso-accesso.cjs (backend su :8000 con EMAIL_BACKEND=file, frontend su :3000)
//   node frontend/e2e/flusso-area-clienti.cjs <cartella>
const { chromium, devices } = require('playwright');
const fs = require('fs'); const path = require('path');
const S = process.argv[2]; const MAIL = path.join(S, 'mail'); const BASE = 'http://localhost:3000';
const stamp = Date.now().toString(36);
const owner = { email: `chiara.${stamp}@example.com`, password: 'Tramonto-sul-lago-7' };
const cliente = `marta.${stamp}@example.com`;

function lastLink(pathPart, to) {
  for (const f of fs.readdirSync(MAIL).sort().reverse()) {
    const raw = fs.readFileSync(path.join(MAIL, f), 'utf8').replace(/=\r?\n/g, '').replace(/=3D/g, '=');
    if (to && !raw.includes(`To: ${to}`)) continue;
    const m = raw.match(new RegExp(`${pathPart.replace(/\//g, '\\/')}\\?token=([A-Za-z0-9_-]+)`));
    if (m) return `${BASE}${pathPart}?token=${m[1]}`;
  }
  throw new Error('email non trovata per ' + pathPart);
}
const step = (n) => console.log('✓', n);

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const staff = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Europe/Rome' });
  const page = await staff.newPage();
  global.__page = page;
  page.on('pageerror', (e) => errors.push(e.message));

  // Studio con una visita online prenotata per Marta (via API dallo stesso browser, già autenticato).
  await page.goto(`${BASE}/registrati`);
  await page.getByLabel('Nome dello studio', { exact: true }).fill('Psicologia Bruni');
  await page.getByLabel('Attività', { exact: true }).selectOption('psicologo');
  await page.getByLabel('Nome e cognome', { exact: true }).fill('Chiara Bruni');
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Password', { exact: true }).fill(owner.password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Crea il tuo studio' }).click();
  await page.getByText('Controlla la tua email').waitFor();
  await page.goto(lastLink('/verifica-email', owner.email));
  await page.waitForURL(`${BASE}/app`);
  const booked = await page.evaluate(async (email) => {
    const j = (r) => r.json();
    const post = (u, b) => fetch(`/api/v1${u}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(j);
    const profs = await fetch('/api/v1/professionals').then(j);
    const services = await fetch('/api/v1/services').then(j);
    const online = services.find((s) => s.mode === 'online');
    const client = await post('/clients', { first_name: 'Marta', last_name: 'Gallo', email, email_consent: true });
    const start = new Date(Date.now() + 5 * 86400000); start.setUTCHours(9, 0, 0, 0);
    return post('/appointments', { client_id: client.id, professional_id: profs[0].id, service_id: online.id, start_at: start.toISOString(), force: true });
  }, cliente);
  if (!booked.video_url) throw new Error('prenotazione non riuscita: ' + JSON.stringify(booked));
  step('lo studio ha prenotato un colloquio online per Marta');

  // Il cliente, in un altro browser, chiede il link.
  const cctx = await browser.newContext({ ...devices['iPhone 13'], timezoneId: 'Europe/Rome' });
  const c = await cctx.newPage();
  c.on('pageerror', (e) => errors.push(e.message));
  await c.goto(`${BASE}/accedi`);
  await c.getByRole('link', { name: 'Clienti' }).click();
  await c.waitForURL(`${BASE}/area-clienti`);
  await c.getByText('Login clienti').waitFor();
  await c.locator('input[type=email]:visible').fill(cliente);
  await c.getByRole('button', { name: 'Inviami il link' }).click();
  await c.getByText('Controlla la tua email').waitFor();
  await c.screenshot({ path: `${S}/cl-1-link.png` });
  step('dal Login professionisti si passa al Login clienti; link richiesto');

  await c.goto(lastLink('/area-clienti/entra', cliente));
  await c.waitForURL(`${BASE}/area-clienti`);
  await c.getByRole('heading', { name: 'I tuoi appuntamenti' }).waitFor();
  await c.getByText('Colloquio online · Chiara Bruni').waitFor();
  await c.getByText('Psicologia Bruni').waitFor();
  const href = await c.getByRole('link', { name: 'Entra nella videochiamata' }).getAttribute('href');
  if (href !== booked.video_url) throw new Error('link video diverso');
  await c.screenshot({ path: `${S}/cl-2-appuntamenti.png` });
  step('il cliente entra con il link e vede il colloquio con "Entra nella videochiamata"');

  // Il cliente non entra nell'area dello studio.
  await c.goto(`${BASE}/app`);
  await c.waitForURL(/\/accedi\?next=/);
  step('con la sessione cliente /app rimanda al Login professionisti');

  await c.goto(`${BASE}/area-clienti`);
  await c.getByRole('button', { name: "Disdici l'appuntamento" }).click();
  await c.getByRole('button', { name: 'Sì, disdici' }).click();
  await c.getByText('Disdetto dal cliente').waitFor();
  await c.screenshot({ path: `${S}/cl-3-disdetto.png` });
  const status = await page.evaluate((id) => fetch(`/api/v1/appointments/${id}`).then((r) => r.json()).then((a) => a.status), booked.id);
  if (status !== 'cancelled_by_client') throw new Error('stato in agenda: ' + status);
  step('disdetta dal cliente, l\'agenda dello studio la vede');

  // Lo staff non entra nell'area clienti con la propria sessione.
  await page.goto(`${BASE}/area-clienti`);
  await page.getByText('Login clienti').waitFor();
  step('con la sessione dello studio l\'area clienti chiede il login clienti');

  // Timer di disconnessione: orologio simulato per non aspettare 5 minuti veri.
  await c.clock.install();
  await c.goto(`${BASE}/area-clienti`);
  const timer = c.getByRole('timer');
  await timer.waitFor();
  const t0 = await timer.innerText();
  if (!/^(5:00|4:5\d)$/.test(t0.trim())) throw new Error('timer iniziale inatteso: ' + t0);
  await c.clock.fastForward('04:35');
  await c.getByText('Vuoi restare connesso?').waitFor();
  await c.screenshot({ path: `${S}/cl-4-avviso.png` });
  await c.getByRole('button', { name: 'Resta connesso' }).click();
  await c.getByText('Vuoi restare connesso?').waitFor({ state: 'detached' });
  const t1 = (await timer.innerText()).trim();
  if (!/^(5:00|4:5\d)$/.test(t1)) throw new Error('dopo "Resta connesso" il timer non è ripartito: ' + t1);
  step(`timer in alto a destra (${t0.trim()}), avviso 30 secondi prima, "Resta connesso" lo fa ripartire`);
  await c.clock.fastForward('05:05');
  await c.getByText('Sei uscito per inattività').waitFor();
  const still = await c.evaluate(() => fetch('/api/v1/client-portal/me').then((r) => r.status));
  if (still !== 401) throw new Error('sessione ancora aperta sul server: ' + still);
  await c.screenshot({ path: `${S}/cl-5-scaduta.png` });
  step('senza risposta si esce da soli dopo 5 minuti, anche sul server');

  // Home: contatti, footer con versione, Novità.
  await page.goto(`${BASE}/`);
  await page.getByText('Scrivici direttamente su WhatsApp').waitFor();
  await page.getByRole('link', { name: /Agenda \d+\.\d+/ }).click();
  await page.waitForURL(`${BASE}/novita`);
  await page.getByRole('heading', { name: "Cosa c'è di nuovo in Agenda." }).waitFor();
  step('home con contatti e WhatsApp; footer con versione → Novità');

  if (errors.length) throw new Error('errori JavaScript: ' + errors.join(' | '));
  step('nessun errore JavaScript');
  await browser.close();
})().catch(async (e) => {
  console.error('✗', e.message);
  await global.__page?.screenshot({ path: `${S}/errore.png` }).catch(() => null);
  process.exit(1);
});
