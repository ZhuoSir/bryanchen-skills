const puppeteer = require('/Users/bryanchen/.nvm/versions/node/v22.16.0/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer');
(async () => {
  const browser = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox', '--disable-gpu'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1100, height: 500, deviceScaleFactor: 2 });
  await page.goto('file:///Users/bryanchen/Documents/work/my_workspace/bryanchen-skills/.tmp_diagram_core.html');
  await new Promise(r => setTimeout(r, 500));
  const svg = await page.$('svg');
  await svg.screenshot({ path: '/Users/bryanchen/Documents/work/my_workspace/bryanchen-skills/.tmp_diagram_core.png' });
  await browser.close();
  console.log('done');
})().catch(e => { console.error(e.message); process.exit(1); });
