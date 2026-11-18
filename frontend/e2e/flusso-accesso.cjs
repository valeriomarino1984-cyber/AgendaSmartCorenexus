// Flusso completo Sprint 1 nel browser: registrazione → conferma email → impostazioni → invito →
// uscita → accettazione invito → permessi del collaboratore → password errata.
//
// Uso (vedi README, sezione "Test end-to-end"):
//   backend su :8000 con EMAIL_BACKEND=file, EMAIL_FILE_DIR=<cartella>/mail, SIGNUP_OPEN=true
//   frontend con `pnpm dev` su :3000
//   node frontend/e2e/flusso-accesso.cjs <cartella>
// Salva gli screenshot nella stessa cartella. Richiede Playwright con Chromium.
const { chromium, devices } = require('playwright');
const fs = require('fs'); const path = require('path');
const S = process.argv[2]; const MAIL = path.join(S, 'mail'); const BASE = 'http://localhost:3000';
const stamp = Date.now().toString(36);
const owner = { email: `anna.${stamp}@example.com`, password: 'Tramonto-sul-lago-7' };
const collab = { email: `luca.${stamp}@example.com`, password: 'Collaboratore-ok-5' };

function lastLink(pathPart, to) {
  const files = fs.readdirSync(MAIL).sort().reverse();
  for (const f of files) {
    const raw = fs.readFileSync(path.join(MAIL, f), 'utf8').replace(/=\r?\n/g, '').replace(/=3D/g, '=');
    if (to && !raw.includes(`To: ${to}`)) continue;
    const m = raw.match(new RegExp(`${pathPart.replace('/', '\\/')}\\?token=([A-Za-z0-9_-]+)`));
    if (m) return `${BASE}${pathPart}?token=${m[1]}`;
  }
  throw new Error('email non trovata per ' + pathPart);
}
const step = (n) => console.log('✓', n);

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(`${BASE}/registrati`);
  await page.getByLabel('Nome dello studio', { exact: true }).fill('Studio Nutrizione Verdi');
  await page.getByLabel('Attività', { exact: true }).selectOption('nutrizionista');
  await page.getByLabel('Nome e cognome', { exact: true }).fill('Anna Bianchi');
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Password', { exact: true }).fill(owner.password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Crea il tuo studio' }).click();
  await page.getByText('Controlla la tua email').waitFor();
  await page.screenshot({ path: `${S}/e2e-1-registrato.png` });
  step('registrazione: "Controlla la tua email"');

  await page.goto(lastLink('/verifica-email', owner.email));
  await page.waitForURL(`${BASE}/app`);
  await page.getByText('Ciao, Anna').waitFor();
  await page.screenshot({ path: `${S}/e2e-2-dashboard.png` });
  step('conferma email → dashboard "Ciao, Anna"');

  await page.getByRole('link', { name: 'Impostazioni' }).first().click();
  await page.getByLabel('Telefono', { exact: true }).fill('+39 02 1234567');
  await page.getByRole('button', { name: 'Salva' }).click();
  await page.getByText('Impostazioni salvate').waitFor();
  step('impostazioni salvate');

  await page.getByRole('link', { name: 'Collaboratori' }).first().click();
  await page.getByText('Invita un collaboratore').click();
  await page.getByLabel('Nome e cognome', { exact: true }).fill('Luca Neri');
  await page.getByLabel('Email', { exact: true }).fill(collab.email);
  await page.getByRole('button', { name: 'Invia invito' }).click();
  await page.getByText('Invito inviato.').waitFor();
  await page.getByText('Invito in attesa').waitFor();
  await page.screenshot({ path: `${S}/e2e-3-collaboratori.png` });
  step('invito inviato, "Invito in attesa" in elenco');

  await page.getByRole('button', { name: 'Esci' }).first().click();
  await page.waitForURL(/\/accedi\?uscito=1/);
  await page.getByText("Sei uscito dall'area riservata.").waitFor();
  await page.goto(`${BASE}/app`);
  await page.waitForURL(/\/accedi\?next=/);
  step('uscita; /app senza sessione → accesso');

  await page.goto(lastLink('/invito', collab.email));
  await page.getByText('Studio Nutrizione Verdi').waitFor();
  await page.getByLabel('Nuova password', { exact: true }).fill(collab.password);
  await page.getByLabel('Ripeti la password', { exact: true }).fill(collab.password);
  await page.getByRole('button', { name: "Accetta l'invito" }).click();
  await page.waitForURL(`${BASE}/app`);
  await page.getByText('Ciao, Luca').waitFor();
  const hasTeam = await page.getByRole('link', { name: 'Collaboratori' }).count();
  if (hasTeam !== 0) throw new Error('il professionista vede Collaboratori');
  await page.goto(`${BASE}/app/impostazioni`);
  await page.getByText('Solo il titolare può modificare').waitFor();
  step('invito accettato: professionista senza menu Collaboratori e impostazioni in sola lettura');

  await page.getByRole('button', { name: 'Esci' }).first().click();
  await page.waitForURL(/\/accedi/);
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Password', { exact: true }).fill('Password-sbagliata-1');
  await page.getByRole('button', { name: 'Accedi' }).click();
  await page.getByText('Email o password non corretti.').waitFor();
  await page.getByLabel('Password', { exact: true }).fill(owner.password);
  await page.getByRole('button', { name: 'Accedi' }).click();
  await page.waitForURL(`${BASE}/app`);
  step('password errata → messaggio; password giusta → dashboard');

  // Schermate: accesso su telefono (chiaro e scuro), area studio in scuro.
  const phone = await browser.newContext({ ...devices['iPhone 13'], colorScheme: 'dark' });
  const p2 = await phone.newPage(); await p2.goto(`${BASE}/accedi`); await p2.waitForTimeout(800);
  await p2.screenshot({ path: `${S}/e2e-4-accedi-telefono-scuro.png` });
  const dark = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark', storageState: await ctx.storageState() });
  const p3 = await dark.newPage(); await p3.goto(`${BASE}/app/collaboratori`); await p3.getByText('Luca Neri').waitFor();
  await p3.screenshot({ path: `${S}/e2e-5-collaboratori-scuro.png` });

  console.log(errors.length ? 'ERRORI JS: ' + errors.join(' | ') : 'nessun errore JavaScript nel browser');
  await browser.close();
})().catch((e) => { console.error('✗ FALLITO:', e.message); process.exit(1); });
