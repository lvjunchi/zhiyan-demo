const { chromium } = require('../frontend/node_modules/playwright');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.route(/^https?:/, route => route.abort());
  await page.goto(pathToFileURL(path.resolve('参考文档/index.html')).href);
  await page.screenshot({ path: 'docs/test-evidence/2026-10-19/UI-F/reference-1440.png', fullPage: true });
  await browser.close();
})();
