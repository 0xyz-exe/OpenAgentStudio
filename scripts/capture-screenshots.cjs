const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function main() {
  const screenshotsDir = path.join(__dirname, '..', 'docs', 'screenshots');
  fs.mkdirSync(screenshotsDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    colorScheme: 'dark'
  });

  const page = await context.newPage();

  // 1. Capture 04_workspace.png first (Auth screen with pre-filled credentials)
  console.log('Capturing 04_workspace.png (Workspace Sign In / Settings)...');
  await page.goto('http://127.0.0.1:8000/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#auth-email');
  await page.fill('#auth-email', 'owner@openagent.local');
  await page.fill('#auth-password', 'Password123!');
  await page.waitForTimeout(600);
  const out4 = path.join(screenshotsDir, '04_workspace.png');
  await page.screenshot({ path: out4 });
  console.log(`Saved: ${out4} (${fs.statSync(out4).size} bytes)`);

  // Sign in to access the studio
  console.log('Signing in...');
  await page.click('#auth-submit');
  await page.waitForSelector('#studio-shell:not([hidden])', { timeout: 10000 });
  await page.waitForTimeout(1000);

  // 2. Capture 01_studio_builder.png (Studio Canvas & Workflow Builder)
  console.log('Capturing 01_studio_builder.png...');
  // Select Number Transformer Demo
  const options = await page.$$eval('#saved-workflows option', opts => opts.map(o => ({ value: o.value, text: o.text })));
  const demoOpt = options.find(o => o.text.includes('Number Transformer'));
  if (demoOpt && demoOpt.value) {
    await page.selectOption('#saved-workflows', demoOpt.value);
    await page.waitForTimeout(600);
  } else {
    await page.fill('#input-number', '7');
    await page.fill('#factor-number', '3');
    await page.fill('#workflow-name', 'Number Transformer Demo');
  }
  await page.waitForTimeout(1000);
  const out1 = path.join(screenshotsDir, '01_studio_builder.png');
  await page.screenshot({ path: out1 });
  console.log(`Saved: ${out1} (${fs.statSync(out1).size} bytes)`);

  // 3. Capture 02_execution_runs.png (Click Run Workflow to show execution results & traces)
  console.log('Executing workflow and capturing 02_execution_runs.png...');
  await page.click('#run-button');
  await page.waitForSelector('.node-result', { timeout: 10000 });
  await page.waitForTimeout(1000);
  const out2 = path.join(screenshotsDir, '02_execution_runs.png');
  await page.screenshot({ path: out2 });
  console.log(`Saved: ${out2} (${fs.statSync(out2).size} bytes)`);

  // 4. Capture 03_agent_config.png (Switch to Agents page & select Document Analysis Agent)
  console.log('Navigating to Agents page and capturing 03_agent_config.png...');
  await page.click('#agents-nav');
  await page.waitForSelector('.agent-item', { timeout: 10000 });
  // Find and click the Document Analysis Agent
  await page.locator('.agent-item:has-text("Document Analysis Agent")').click();
  await page.waitForSelector('.agent-version-row', { timeout: 10000 });
  await page.waitForTimeout(1000);
  const out3 = path.join(screenshotsDir, '03_agent_config.png');
  await page.screenshot({ path: out3 });
  console.log(`Saved: ${out3} (${fs.statSync(out3).size} bytes)`);

  await browser.close();
  console.log('All 4 OpenAgentStudio screenshots captured successfully.');
}

main().catch(err => {
  console.error('Capture failed:', err);
  process.exit(1);
});
