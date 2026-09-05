import { chromium } from '@playwright/test';
import { pathToFileURL } from 'node:url';

const out = process.env.SHOT_DIR;
const file = pathToFileURL(process.env.TARGET).href;
const tag = process.env.TAG || 'lm';

const b = await chromium.launch();
for (const theme of ['dark', 'light']) {
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  await p.goto(file);
  if (theme === 'light') await p.click('#themeToggle');
  await p.waitForTimeout(400);
  const toc = await p.locator('#toc a').count();
  const copy = await p.locator('.copy-btn').count();
  const boxes = await p.locator('.section-check input').count();
  console.log(`${theme}: tocLinks=${toc} copyBtns=${copy} checkboxes=${boxes} consoleErrors=${errs.length} ${errs.slice(0, 3).join(' | ')}`);
  await p.screenshot({ path: `${out}/${tag}-${theme}.png` });
  const h2s = await p.locator('h2').count();
  if (h2s > 4) {
    await p.locator('h2').nth(4).scrollIntoViewIfNeeded();
    await p.waitForTimeout(250);
    await p.screenshot({ path: `${out}/${tag}-${theme}-mid.png` });
  }
  await p.close();
}
const m = await b.newPage({ viewport: { width: 375, height: 800 } });
await m.goto(file);
await m.waitForTimeout(300);
const scrollW = await m.evaluate(() => document.documentElement.scrollWidth);
console.log('mobile 375px scrollWidth:', scrollW, scrollW <= 380 ? '(no horizontal overflow)' : '(OVERFLOW)');
await m.screenshot({ path: `${out}/${tag}-mobile.png` });
await b.close();
