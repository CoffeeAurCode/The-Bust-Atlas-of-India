import { chromium } from '@playwright/test';
import { pathToFileURL } from 'node:url';

const file = pathToFileURL(process.env.TARGET).href;
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 375, height: 800 } });
await p.goto(file);
await p.waitForTimeout(300);
const info = await p.evaluate(() => {
  const de = document.documentElement;
  const res = {
    docScrollW: de.scrollWidth, docClientW: de.clientWidth,
    bodyScrollW: document.body.scrollWidth,
    wide: [],
  };
  // elements whose own layout width exceeds the viewport AND which are not
  // inside a horizontally scrollable ancestor
  const scrollable = el => {
    let n = el.parentElement;
    while (n) {
      const st = getComputedStyle(n);
      if (st.overflowX === 'auto' || st.overflowX === 'scroll' || st.overflowX === 'hidden') return true;
      n = n.parentElement;
    }
    return false;
  };
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > de.clientWidth + 1 && !scrollable(el)) {
      res.wide.push({
        tag: el.tagName.toLowerCase(),
        cls: (el.className && el.className.toString().slice(0, 45)) || '',
        w: Math.round(r.width),
        left: Math.round(r.left),
        text: (el.textContent || '').trim().slice(0, 45),
      });
    }
  });
  res.wide = res.wide.slice(0, 12);
  return res;
});
console.log(JSON.stringify(info, null, 1));
await b.close();
