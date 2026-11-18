// Flusso Sprint 2 nel browser: registrazione da fisioterapista → prestazioni del profilo →
// nuova prestazione online → professionista senza account → sede → clienti (doppione, ricerca,
// consensi, archivio) → vista telefono.
//
// Uso: come flusso-accesso.cjs (backend su :8000 con EMAIL_BACKEND=file, frontend su :3000)
//   node frontend/e2e/flusso-anagrafiche.cjs <cartella>
const { chromium, devices } = require('playwright');
const fs = require('fs'); const path = require('path');
const S = process.argv[2]; const MAIL = path.join(S, 'mail'); const BASE = 'http://localhost:3000';
const stamp = Date.now().toString(36);
const owner = { email: `paola.${stamp}@example.com`, password: 'Tramonto-sul-lago-7' };

function lastLink(pathPart, to) {
  for (const f of fs.readdirSync(MAIL).sort().reverse()) {
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
  await page.getByLabel('Nome dello studio', { exact: true }).fill('Fisioterapia Conti');
  await page.getByLabel('Attività', { exact: true }).selectOption('fisioterapista');
  await page.getByLabel('Nome e cognome', { exact: true }).fill('Paola Conti');
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Password', { exact: true }).fill(owner.password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Crea il tuo studio' }).click();
  await page.getByText('Controlla la tua email').waitFor();
  await page.goto(lastLink('/verifica-email', owner.email));
  await page.waitForURL(`${BASE}/app`);
  step('studio da fisioterapista registrato');

  // Prestazioni: il profilo ha già creato le tre prestazioni approvate.
  await page.getByRole('link', { name: 'Prestazioni' }).first().click();
  for (const n of ['Valutazione fisioterapica', 'Seduta di fisioterapia', 'Terapia manuale'])
    await page.getByText(n, { exact: true }).first().waitFor();
  await page.getByText('Tutte già presenti').waitFor();
  step('prestazioni del profilo presenti (3)');

  await page.getByText('Nuova prestazione').click();
  const add = page.locator('details[open]:visible').last();
  await add.getByLabel('Nome', { exact: true }).fill('Teleconsulto');
  await add.getByLabel('Durata (minuti)', { exact: true }).fill('20');
  await add.getByLabel('Prezzo (€)', { exact: true }).fill('35,50');
  await add.getByRole('radio', { name: 'Online' }).click();
  await add.getByText('link della videochiamata').waitFor();
  await add.getByRole('button', { name: 'Aggiungi prestazione' }).click();
  await page.getByText('Teleconsulto', { exact: true }).waitFor();
  await page.getByText('20 min · 35,50 €').waitFor();
  await page.screenshot({ path: `${S}/s2-1-prestazioni.png` });
  step('prestazione online aggiunta: "20 min · 35,50 €"');

  // Professionisti: la titolare ha la sua scheda; se ne aggiunge una senza account.
  await page.getByRole('link', { name: 'Professionisti' }).first().click();
  await page.getByText('Paola Conti (tu)').waitFor();
  await page.getByText('Aggiungi professionista').click();
  const addProf = page.locator('details[open]:visible').last();
  await addProf.getByLabel('Nome visualizzato', { exact: true }).fill('Marco Ferri');
  await addProf.getByLabel('Specializzazione', { exact: true }).fill('Osteopata');
  await addProf.getByRole('radio', { name: '#34c759' }).click();
  await addProf.getByRole('button', { name: 'Aggiungi' }).click();
  await page.getByText('Marco Ferri', { exact: true }).waitFor();
  await page.screenshot({ path: `${S}/s2-2-professionisti.png` });
  step('professionista senza account aggiunto');

  // Sede principale nelle impostazioni.
  await page.getByRole('link', { name: 'Impostazioni' }).first().click();
  await page.getByLabel('Indirizzo della sede', { exact: true }).fill('Via Garibaldi 12, Bergamo');
  await page.getByRole('button', { name: 'Salva sede' }).click();
  await page.getByText('Sede salvata').waitFor();
  step('sede principale salvata');

  // Clienti.
  await page.getByRole('link', { name: 'Clienti' }).first().click();
  await page.getByText('Nessun cliente').waitFor();
  async function addClient(first, last, phone, opts = {}) {
    // Il modulo resta aperto dopo un inserimento (per aggiungerne altri di seguito).
    const f = page.locator('details:visible', { has: page.getByText('Nuovo cliente') });
    if ((await f.getAttribute('open')) === null) await page.getByText('Nuovo cliente').click();
    await f.getByLabel('Nome', { exact: true }).fill(first);
    await f.getByLabel('Cognome', { exact: true }).fill(last);
    await f.getByLabel('Cellulare', { exact: true }).fill(phone);
    if (opts.email) await f.getByLabel('Email', { exact: true }).fill(opts.email);
    if (opts.ref) await f.getByLabel('Professionista di riferimento', { exact: true }).selectOption({ label: opts.ref });
    if (opts.consent) await f.getByLabel('Promemoria via email').check();
    await f.getByRole('button', { name: 'Aggiungi cliente' }).click();
    return f;
  }
  await addClient('Giulia', 'Bassi', '333 111 2222', { email: 'giulia@example.com', ref: 'Marco Ferri', consent: true });
  await page.getByText('Bassi Giulia').waitFor();
  await page.getByText('+39 333 111 2222 · giulia@example.com').waitFor();
  step('cliente aggiunto, telefono normalizzato e mostrato come +39 333 111 2222');

  const dup = await addClient('Giulia M.', 'Bassi', '+39 333 1112222');
  await dup.getByText('Esiste già un cliente').waitFor();
  await page.screenshot({ path: `${S}/s2-3-doppione.png` });
  await dup.getByRole('button', { name: 'Crea comunque' }).click();
  await page.getByText('Bassi Giulia M.').waitFor();
  step('avviso doppione e "Crea comunque"');

  await addClient('Luca', 'Moretti', '340 555 6666');
  await page.getByText('Moretti Luca').waitFor();
  await page.getByRole('searchbox', { name: 'Cerca clienti' }).fill('moretti');
  await page.getByText('1 cliente', { exact: true }).waitFor();
  await page.getByRole('searchbox', { name: 'Cerca clienti' }).fill('');
  await page.getByText('3 clienti', { exact: true }).waitFor();
  step('ricerca per cognome');

  await page.getByText('Bassi Giulia', { exact: true }).click();
  const row = page.locator('details[open]:visible').first();
  await row.getByLabel('Promemoria via WhatsApp').check();
  await row.getByRole('button', { name: 'Salva' }).click();
  await row.getByText('Cliente salvato').waitFor();
  await row.getByRole('button', { name: 'Storico consensi' }).click();
  await row.getByText(/WhatsApp: consenso dato/).waitFor();
  await row.getByText(/Email: consenso dato/).waitFor();
  await page.screenshot({ path: `${S}/s2-4-cliente.png` });
  step('consenso WhatsApp aggiunto e storico consensi visibile');

  await row.getByRole('button', { name: 'Archivia' }).click();
  await page.getByText('2 clienti', { exact: true }).waitFor();
  await page.getByRole('radio', { name: 'Archiviati' }).click();
  await page.getByText('Bassi Giulia', { exact: true }).waitFor();
  step('cliente archiviato e visibile in Archiviati');

  // Telefono: Prestazioni e Professionisti raggiungibili dalle impostazioni.
  const phone = await browser.newContext({ ...devices['iPhone 13'] });
  await phone.addCookies(await ctx.cookies());
  const p2 = await phone.newPage();
  p2.on('pageerror', (e) => errors.push(e.message));
  await p2.goto(`${BASE}/app/impostazioni`);
  await p2.getByRole('link', { name: 'Prestazioni' }).click();
  await p2.waitForURL(`${BASE}/app/prestazioni`);
  await p2.getByText('Teleconsulto', { exact: true }).waitFor();
  await p2.goto(`${BASE}/app/clienti`);
  await p2.getByText('Moretti Luca').waitFor();
  await p2.screenshot({ path: `${S}/s2-5-telefono-clienti.png` });
  step('telefono: impostazioni → prestazioni, elenco clienti');

  if (errors.length) throw new Error('errori JavaScript: ' + errors.join(' | '));
  step('nessun errore JavaScript');
  await browser.close();
})().catch((e) => { console.error('✗', e.message); process.exit(1); });
