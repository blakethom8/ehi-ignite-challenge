const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const PATIENT_ID = 'eec393be-2569-46db-a974-33d7c853d690'; // Shelly431 Corwin846 - highly complex
const BASE_URL = 'http://localhost:5173';
const OUT_DIR = '/Users/blake/Repo/ehi-ignite-challenge/report/assets/screenshots';

async function shot(page, name, description) {
  await page.waitForTimeout(2000); // let content settle
  await page.screenshot({
    path: path.join(OUT_DIR, name),
    clip: { x: 0, y: 0, width: 1440, height: 900 }
  });
  console.log(`Captured: ${name} — ${description}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await ctx.newPage();

  // Shot 1: Source Intake
  console.log('--- Shot 1: Source Intake ---');
  await page.goto(`${BASE_URL}/aggregate/sources`, { waitUntil: 'networkidle', timeout: 20000 });
  await shot(page, '01-source-intake.png', 'Source Intake page');

  // Shot 2: Harmonized Record
  console.log('--- Shot 2: Harmonized Record ---');
  await page.goto(`${BASE_URL}/aggregate/harmonize?patient=${PATIENT_ID}`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(3000);
  await shot(page, '02-harmonized-record.png', 'HarmonizeView with patient record');

  // Shot 3: Safety Panel
  console.log('--- Shot 3: Safety Panel ---');
  await page.goto(`${BASE_URL}/explorer/safety?patient=${PATIENT_ID}`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(3000);
  await shot(page, '03-safety-panel.png', 'Safety flags panel');

  // Shot 4: Provider Assistant
  console.log('--- Shot 4: Provider Assistant ---');
  await page.goto(`${BASE_URL}/explorer/assistant?patient=${PATIENT_ID}`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(2000);
  await shot(page, '04-assistant-evidence.png', 'Provider Assistant');

  // Shot 5: Care Journey
  console.log('--- Shot 5: Care Journey ---');
  await page.goto(`${BASE_URL}/explorer/care-journey?patient=${PATIENT_ID}`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(5000);
  await shot(page, '05-care-journey.png', 'Care Journey timeline');

  // Shot 6: Analysis / Methodology
  console.log('--- Shot 6: Analysis Methodology ---');
  await page.goto(`${BASE_URL}/analysis/methodology`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(2000);
  await shot(page, '06-data-lab.png', 'Analysis methodology');

  // Shot 7: Overview / record overview
  console.log('--- Shot 7: Patient Overview ---');
  await page.goto(`${BASE_URL}/explorer?patient=${PATIENT_ID}`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(3000);
  await shot(page, '07-patient-overview.png', 'Patient overview/explorer');

  await browser.close();
  console.log('All done.');
})().catch(err => {
  console.error('ERROR:', err.message);
  process.exit(1);
});
