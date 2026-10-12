// Functional validation of a deployed build (default: staging) with puppeteer-core + Edge.
// Usage: node scripts/validate_staging.mjs [url] [outDir] [load|flow] [es|en]
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

const URL = process.argv[2] || 'https://outdoor-staging.privantix.io/index.html';
const OUT = process.argv[3] || 'validation-output';
const mode = process.argv[4] || 'load';
const lang = process.argv[5] || 'es';
fs.mkdirSync(OUT, { recursive: true });
const executablePath = process.env.BROWSER_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const browser = await puppeteer.launch({ executablePath, headless: true, args: ['--no-first-run'], protocolTimeout: 900000 });
const report = { url: URL, mode, lang, at: new Date().toISOString(), checks: [] };
const check = (name, ok, detail = '') => { report.checks.push({ name, ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`); };
const notLoading = () => !/Cargando|Loading/.test(document.body.innerText);

const snapshot = page => page.evaluate(() => ({
  h1: document.querySelector('h1')?.innerText,
  lang: document.documentElement.lang,
  missions: [...document.querySelectorAll('article')].map(a => ({ title: a.querySelector('h3')?.innerText, text: a.innerText })),
  journal: [...document.querySelectorAll('li')].map(l => l.innerText),
  points: Number((document.body.innerText.match(/(Puntos ganados|Points earned):\s*(\d+)/) || [])[2] || 0),
  more: [...document.querySelectorAll('button')].map(b => b.innerText).find(t => /anteriores|earlier/i.test(t)) || null,
  alert: document.querySelector('[role=alert]')?.innerText || '',
  overflowX: document.documentElement.scrollWidth > window.innerWidth,
}));

function watch(page) {
  const log = { errors: [], bad: [], requests: [] };
  page.on('pageerror', e => log.errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') log.errors.push(m.text()); });
  page.on('requestfailed', r => log.bad.push(`${r.url()} ${r.failure()?.errorText}`));
  page.on('response', r => {
    log.requests.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    if (r.status() >= 400 && !/\/missions\/jobs$/.test(r.url())) log.bad.push(`${r.status()} ${r.url()}`);
  });
  return log;
}

if (mode === 'load') {
  const viewports = [[{ width: 1366, height: 900 }, 'desktop'], [{ width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 }, 'mobile']];
  for (const [viewport, label] of viewports) {
    const page = await browser.newPage();
    await page.setViewport(viewport);
    const log = watch(page);
    const t0 = Date.now();
    const res = await page.goto(URL, { waitUntil: 'networkidle0', timeout: 60000 });
    await page.waitForFunction(notLoading, { timeout: 60000 }).catch(() => {});
    const s = await snapshot(page);
    await page.screenshot({ path: `${OUT}/${label}.png`, fullPage: true });
    check(`${label}: page served`, [200, 304].includes(res.status()), `status=${res.status()} load=${Date.now() - t0}ms`);
    check(`${label}: renders heading`, !!s.h1, s.h1);
    check(`${label}: no JS errors`, log.errors.length === 0, JSON.stringify(log.errors));
    check(`${label}: no failed or 4xx/5xx requests`, log.bad.length === 0, JSON.stringify(log.bad));
    check(`${label}: no horizontal overflow`, !s.overflowX);
    check(`${label}: data loaded from API without error`, !s.alert, `${s.missions.length} missions, ${s.journal.length} journal entries`);
    report[label] = { requests: log.requests };
    await page.close();
  }
}

if (mode === 'flow') {
  const page = await browser.newPage();
  await page.setViewport({ width: 1366, height: 900 });
  const log = watch(page);
  let result = null;
  page.on('response', async r => {
    if (r.request().method() === 'GET' && /\/missions\/jobs\/[0-9a-f]+$/.test(r.url())) {
      try { const b = await r.json(); if (b.status !== 'running') result = b; } catch {}
    }
  });
  await page.goto(URL + (URL.includes('?') ? '&' : '?') + 'lang=' + lang, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.waitForFunction(notLoading, { timeout: 60000 });
  const before = await snapshot(page);
  check(`[${lang}] UI language`, lang === 'es' ? /Menos pantalla/.test(before.h1) : /Less screen/.test(before.h1), before.h1);
  check(`[${lang}] html lang attribute`, before.lang === lang, `lang=${before.lang}`);

  const interests = lang === 'es' ? 'árboles, sonidos' : 'trees, sounds';
  await page.$eval('input', (el, v) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })); }, interests);
  await page.select('select', '10');
  const t0 = Date.now();
  await page.evaluate(() => [...document.querySelectorAll('button')].find(b => /Proponer|Suggest/.test(b.innerText)).click());
  await page.waitForFunction(() => { const b = [...document.querySelectorAll('button')].find(b => /Proponer|Suggest|Creando|Creating/.test(b.innerText)); return b && !b.disabled; }, { timeout: 660000, polling: 1000 });
  const secs = Math.round((Date.now() - t0) / 1000);
  await new Promise(r => setTimeout(r, 500));
  const after = await snapshot(page);
  const generated = result?.result?.missions || [];
  check(`[${lang}] generation job finished`, result?.status === 'done', `status=${result?.status} in ${secs}s; alert="${after.alert}"`);
  check(`[${lang}] AI engine is Gemma (not demo fallback)`, result?.result?.source === 'gemma', `source=${result?.result?.source} fallback=${result?.result?.fallback_reason}`);
  check(`[${lang}] three new missions shown first`, generated.length === 3 && generated.every((m, i) => after.missions[i]?.title === m.title), after.missions.slice(0, 3).map(m => m.title).join(' | '));
  check(`[${lang}] at most 3 pending missions visible`, after.missions.length <= 3, `${after.missions.length} visible; toggle=${after.more}`);
  check(`[${lang}] missions carry 10 min / 40 pts`, generated.length === 3 && generated.every(m => m.minutes === 10 && m.points === 40));
  check(`[${lang}] mission text is in the UI language`, generated.length === 3 && generated.every(m => lang === 'es' ? /[áéíóúñ¿¡]|\b(el|la|los|las|un|una|y|en)\b/i.test(m.description) : /\b(the|a|and|of|to)\b/i.test(m.description)), generated.map(m => m.title).join(' | '));
  await page.screenshot({ path: `${OUT}/flow-${lang}-generated.png`, fullPage: true });
  if (!generated.length) { await finish(); }

  const target = generated[0];
  const reflection = lang === 'es' ? 'Prueba QA de staging: no es una salida real.' : 'Staging QA test: not a real outing.';
  await page.evaluate((title, text) => {
    const art = [...document.querySelectorAll('article')].find(a => a.querySelector('h3')?.innerText === title);
    const ta = art.querySelector('textarea');
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(ta, text);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    art.querySelector('button').click();
  }, target.title, reflection);
  await page.waitForFunction(title => ![...document.querySelectorAll('article h3')].some(h => h.innerText === title), { timeout: 30000 }, target.title).catch(() => {});
  await new Promise(r => setTimeout(r, 1000));
  const done = await snapshot(page);
  check(`[${lang}] completed mission leaves the pending list`, !done.missions.some(m => m.title === target.title));
  check(`[${lang}] journal shows the entry with its reflection`, done.journal[0]?.includes(target.title) && done.journal[0]?.includes(reflection), JSON.stringify(done.journal[0]));
  check(`[${lang}] points increase by exactly 40`, done.points - after.points === 40, `${after.points} -> ${done.points}`);

  const api = await page.evaluate(() => window.TAMAGOSHI_API);
  const dup = await page.evaluate(async (api, id) => (await fetch(`${api}/missions/${id}/complete`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"reflection":"dup"}' })).status, api, target.id);
  check(`[${lang}] second completion rejected with 409`, dup === 409, `status=${dup}`);

  await page.reload({ waitUntil: 'networkidle0' });
  await page.waitForFunction(notLoading, { timeout: 60000 });
  const reloaded = await snapshot(page);
  check(`[${lang}] after reload: journal entry persists`, reloaded.journal.some(j => j.includes(target.title) && j.includes(reflection)));
  check(`[${lang}] after reload: points persist`, reloaded.points === done.points, `points=${reloaded.points}`);
  check(`[${lang}] after reload: other new missions still pending`, generated.slice(1).every(m => reloaded.missions.some(x => x.title === m.title)));
  const expected = s => /409/.test(s);
  const unexpected = [...log.errors, ...log.bad].filter(s => !expected(s));
  check(`[${lang}] no JS errors or failed requests during flow (besides the deliberate 409)`, unexpected.length === 0, JSON.stringify(unexpected));
  await page.screenshot({ path: `${OUT}/flow-${lang}-after-reload.png`, fullPage: true });
  report.flow = { secs, generated, journalTop: reloaded.journal.slice(0, 2) };
}

await finish();

async function finish() {
  fs.writeFileSync(`${OUT}/report-${mode}-${lang}.json`, JSON.stringify(report, null, 2));
  await browser.close();
  const failed = report.checks.filter(c => !c.ok).length;
  console.log(`\n${report.checks.length - failed}/${report.checks.length} passed`);
  process.exit(failed ? 1 : 0);
}
