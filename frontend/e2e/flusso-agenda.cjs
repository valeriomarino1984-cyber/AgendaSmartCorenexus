// Flusso Sprint 3 nel browser: orari settimanali → prenotazione dalla griglia con orari liberi →
// visita online con link → trascinamento in un altro giorno → fuori orario con conferma →
// sovrapposizione rifiutata → vista mese → disdetta → vista telefono.
//
// Uso: come flusso-accesso.cjs (backend su :8000 con EMAIL_BACKEND=file, frontend su :3000)
//   node frontend/e2e/flusso-agenda.cjs <cartella>
const { chromium, devices } = require('playwright');
const fs = require('fs'); const path = require('path');
const S = process.argv[2]; const MAIL = path.join(S, 'mail'); const BASE = 'http://localhost:3000';
const stamp = Date.now().toString(36);
const owner = { email: `elena.${stamp}@example.com`, password: 'Tramonto-sul-lago-7' };
const HOUR_PX = 56; const FIRST_HOUR = 7;

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
const sheet = (page) => page.getByRole('dialog');

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, timezoneId: 'Europe/Rome' });
  const page = await ctx.newPage();
  global.__page = page;
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(`${BASE}/registrati`);
  await page.getByLabel('Nome dello studio', { exact: true }).fill('Nutrizione Rinaldi');
  await page.getByLabel('Attività', { exact: true }).selectOption('nutrizionista');
  await page.getByLabel('Nome e cognome', { exact: true }).fill('Elena Rinaldi');
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Password', { exact: true }).fill(owner.password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Crea il tuo studio' }).click();
  await page.getByText('Controlla la tua email').waitFor();
  await page.goto(lastLink('/verifica-email', owner.email));
  await page.waitForURL(`${BASE}/app`);
  await page.getByText('Nessun appuntamento oggi').waitFor();
  await page.getByText('Imposta i tuoi orari').waitFor();
  step('studio registrato; dashboard con "Agenda di oggi" e passo "Imposta i tuoi orari"');

  // Orario settimanale: lun 9-13, copiato fino al venerdì.
  await page.getByRole('link', { name: 'Disponibilità', exact: true }).first().click();
  await page.getByRole('button', { name: 'Aggiungi fascia a Lunedì' }).click();
  await page.getByLabel('Lunedì: inizio fascia 1').fill('09:00');
  await page.getByLabel('Lunedì: fine fascia 1').fill('13:00');
  await page.getByRole('button', { name: 'Copia il lunedì fino al venerdì' }).click();
  await page.getByRole('button', { name: 'Salva orario' }).click();
  await page.getByText('Orario salvato').waitFor();
  await page.screenshot({ path: `${S}/s3-1-disponibilita.png` });
  step('orario lun-ven 9-13 salvato');

  // Agenda, settimana prossima.
  await page.getByRole('link', { name: 'Agenda', exact: true }).first().click();
  await page.getByRole('button', { name: 'Successivo' }).click();
  const cols = page.locator('[data-day]');
  await cols.first().waitFor();
  const monday = await cols.nth(0).getAttribute('data-day');
  const tuesday = await cols.nth(1).getAttribute('data-day');
  const box = await cols.nth(0).boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + (10 - FIRST_HOUR) * HOUR_PX + 4);
  await sheet(page).waitFor();
  await sheet(page).getByLabel('Giorno', { exact: true }).waitFor();
  if ((await sheet(page).getByLabel('Giorno', { exact: true }).inputValue()) !== monday) throw new Error('giorno non precompilato');
  if ((await sheet(page).getByLabel('Ora', { exact: true }).inputValue()) !== '10:00') throw new Error('ora non precompilata');
  step(`clic sulla griglia → nuovo appuntamento precompilato ${monday} 10:00`);

  await sheet(page).getByRole('button', { name: '+ Nuovo cliente' }).click();
  await sheet(page).getByLabel('Nome', { exact: true }).fill('Giulia');
  await sheet(page).getByLabel('Cognome', { exact: true }).fill('Ferri');
  await sheet(page).getByLabel('Cellulare', { exact: true }).fill('333 123 4567');
  await sheet(page).getByRole('button', { name: 'Crea e scegli' }).click();
  await sheet(page).getByText('Giulia Ferri').waitFor();
  await sheet(page).getByLabel('Prestazione', { exact: true }).selectOption({ label: 'Controllo online · 30 min · Online' });
  await sheet(page).getByText('Il link della videochiamata viene creato al salvataggio.').waitFor();
  await sheet(page).getByRole('button', { name: '09:30', exact: true }).waitFor();
  await sheet(page).getByRole('button', { name: '10:00', exact: true }).click();
  await page.screenshot({ path: `${S}/s3-2-nuovo.png` });
  await sheet(page).getByRole('button', { name: 'Prenota' }).click();
  await sheet(page).waitFor({ state: 'detached' });
  const block = page.getByRole('button', { name: /^10:00 Giulia Ferri/ });
  await block.waitFor();
  step('cliente creato dal pannello, orari liberi proposti, prenotazione online alle 10:00');

  await block.click();
  await sheet(page).getByText('Visita online').waitFor();
  const link = await sheet(page).getByRole('link', { name: 'Apri videochiamata' }).getAttribute('href');
  if (!/^https:\/\/meet\.jit\.si\/CN-[A-Za-z0-9]{22}$/.test(link)) throw new Error('link video inatteso: ' + link);
  await page.screenshot({ path: `${S}/s3-3-dettaglio.png` });
  await sheet(page).getByRole('button', { name: 'Chiudi' }).first().click();
  step('dettaglio: link Jitsi univoco ' + link.slice(0, 30) + '…');

  // Trascina al martedì alle 11:00.
  const b = await block.boundingBox();
  const colW = box.width;
  await page.mouse.move(b.x + b.width / 2, b.y + 6);
  await page.mouse.down();
  for (let i = 1; i <= 8; i++) await page.mouse.move(b.x + b.width / 2 + (colW * i) / 8, b.y + 6 + (HOUR_PX * i) / 8);
  await page.mouse.up();
  await page.getByText(/Spostato a mar .* alle 11:00/).waitFor();
  await page.getByRole('button', { name: /^11:00 Giulia Ferri/ }).waitFor();
  const movedDay = await page.getByRole('button', { name: /^11:00 Giulia Ferri/ }).evaluate((el) => el.parentElement.parentElement.children.length);
  step(`trascinato al martedì ${tuesday} alle 11:00`);

  // Fuori orario: lunedì 15:00 → avviso e "Prenota comunque".
  await page.getByRole('button', { name: 'Nuovo appuntamento' }).click();
  await sheet(page).getByPlaceholder('Cerca per nome o telefono').fill('ferri');
  await sheet(page).getByRole('button', { name: /Ferri Giulia/ }).click();
  await sheet(page).getByLabel('Giorno', { exact: true }).fill(monday);
  await sheet(page).getByLabel('Ora', { exact: true }).fill('15:00');
  await sheet(page).getByRole('button', { name: 'Prenota' }).click();
  await sheet(page).getByText(/fuori dall'orario di lavoro/).waitFor();
  await sheet(page).getByRole('button', { name: 'Prenota comunque' }).click();
  await sheet(page).waitFor({ state: 'detached' });
  await page.getByRole('button', { name: /^15:00 Giulia Ferri/ }).waitFor();
  step('fuori orario: avviso e "Prenota comunque"');

  // Sovrapposizione: martedì 11:00 è occupato.
  await page.getByRole('button', { name: 'Nuovo appuntamento' }).click();
  await sheet(page).getByPlaceholder('Cerca per nome o telefono').fill('ferri');
  await sheet(page).getByRole('button', { name: /Ferri Giulia/ }).click();
  await sheet(page).getByLabel('Giorno', { exact: true }).fill(tuesday);
  await sheet(page).getByLabel('Ora', { exact: true }).fill('11:15');
  await sheet(page).getByRole('button', { name: 'Prenota' }).click();
  await sheet(page).getByText(/Orario già occupato/).waitFor();
  await page.screenshot({ path: `${S}/s3-4-occupato.png` });
  await sheet(page).getByRole('button', { name: 'Chiudi' }).first().click();
  step('sovrapposizione rifiutata: "Orario già occupato"');

  await page.screenshot({ path: `${S}/s3-5-settimana.png` });
  await page.getByRole('radio', { name: 'Mese' }).click();
  await page.getByRole('button', { name: /Giulia Ferri/ }).first().waitFor();
  await page.screenshot({ path: `${S}/s3-6-mese.png` });
  await page.getByRole('radio', { name: 'Settimana' }).click();
  step('vista mese');

  // Disdetta.
  await page.getByRole('button', { name: /^15:00 Giulia Ferri/ }).click();
  await sheet(page).getByRole('button', { name: 'Disdici' }).click();
  await sheet(page).getByLabel('Motivo (facoltativo)').fill('Impegno di lavoro');
  await sheet(page).getByRole('button', { name: 'Conferma disdetta' }).click();
  await sheet(page).getByText('Disdetto dal cliente').first().waitFor();
  await sheet(page).getByText(/Motivo: Impegno di lavoro/).waitFor();
  await sheet(page).getByRole('button', { name: 'Chiudi' }).first().click();
  await page.getByRole('button', { name: /^15:00 Giulia Ferri/ }).waitFor({ state: 'detached' });
  step('disdetta: l\'appuntamento esce dall\'agenda');

  const phone = await browser.newContext({ ...devices['iPhone 13'], timezoneId: 'Europe/Rome' });
  await phone.addCookies(await ctx.cookies());
  const p2 = await phone.newPage();
  p2.on('pageerror', (e) => errors.push(e.message));
  await p2.goto(`${BASE}/app/agenda`);
  await p2.getByRole('radio', { name: 'Giorno' }).click();
  await p2.getByRole('button', { name: 'Successivo' }).click();
  await p2.getByRole('button', { name: 'Successivo' }).waitFor();
  await p2.screenshot({ path: `${S}/s3-7-telefono.png` });
  step('telefono: agenda in vista giorno');

  if (errors.length) throw new Error('errori JavaScript: ' + errors.join(' | '));
  step('nessun errore JavaScript');
  await browser.close();
})().catch(async (e) => {
  console.error('✗', e.message);
  await global.__page?.screenshot({ path: `${S}/errore.png` }).catch(() => null);
  process.exit(1);
});
