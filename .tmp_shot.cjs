const puppeteer = require('/Users/bryanchen/.nvm/versions/node/v22.16.0/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer');
(async () => {
  const browser = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox', '--disable-gpu'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800, deviceScaleFactor: 2 });
  await page.goto('file:///Users/bryanchen/Documents/work/my_workspace/bryanchen-skills/.tmp_diagram.html');
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: '/Users/bryanchen/Documents/work/my_workspace/bryanchen-skills/.tmp_diagram.png' });
  await browser.close();
  console.log('screenshot done');
})().catch(e => { console.error(e.message); process.exit(1); });
