// Full-page screenshot with real device emulation: node scripts/screenshot.mjs <url> <out.png> <desktop|mobile>
import puppeteer from 'puppeteer-core';

const [url, out, mode = 'desktop'] = process.argv.slice(2);
const viewport = mode === 'mobile'
  ? {width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true}
  : {width: 1280, height: 900, deviceScaleFactor: 1};
const executablePath = process.env.BROWSER_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

const browser = await puppeteer.launch({executablePath, headless: true});
try {
  const page = await browser.newPage();
  await page.setViewport(viewport);
  await page.goto(url, {waitUntil: 'networkidle0'});
  await page.waitForFunction(() => !document.body.textContent.includes('Cargando') && !document.body.textContent.includes('Loading'));
  await page.screenshot({path: out, fullPage: true});
} finally {
  await browser.close();
}
