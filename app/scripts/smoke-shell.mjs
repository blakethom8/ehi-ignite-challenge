import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import process from "node:process";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright";

const HOST = "127.0.0.1";
const PORT = 4173;
const BASE_URL = `http://${HOST}:${PORT}`;

async function waitForServer(url, timeoutMs = 30_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Server not ready yet.
    }
    await delay(250);
  }
  throw new Error(`Timed out waiting for preview server at ${url}`);
}

function startPreviewServer() {
  const child = spawn(
    "npm",
    ["run", "preview", "--", "--host", HOST, "--port", String(PORT)],
    {
      cwd: process.cwd(),
      stdio: "pipe",
      env: { ...process.env, VITE_USE_MOCK_DATA: "true" },
    },
  );

  child.stdout.on("data", (chunk) => {
    process.stdout.write(chunk);
  });
  child.stderr.on("data", (chunk) => {
    process.stderr.write(chunk);
  });
  return child;
}

async function pressAlt(page, key) {
  await page.keyboard.down("Alt");
  await page.keyboard.press(key);
  await page.keyboard.up("Alt");
}

async function main() {
  const preview = startPreviewServer();
  let browser;

  const stopPreview = () => {
    if (!preview.killed) {
      preview.kill("SIGTERM");
    }
  };

  process.on("SIGINT", stopPreview);
  process.on("SIGTERM", stopPreview);

  try {
    await waitForServer(BASE_URL);
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();

    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
    await page.getByText("Choose demo patient").waitFor();
    await page.evaluate(() => {
      window.localStorage.setItem(
        "atlas:access",
        JSON.stringify({ mode: "demo", activePatientId: "demo-high-risk" }),
      );
    });

    await page.goto(`${BASE_URL}/caspian`, { waitUntil: "domcontentloaded" });
    await page.getByText("WORKBENCH").waitFor();
    await page.getByText("FILES").waitFor();

    await pressAlt(page, "f");
    await expectHidden(page, "FILES");
    await page.reload({ waitUntil: "domcontentloaded" });
    await expectHidden(page, "FILES");

    await page.goto(`${BASE_URL}/workspaces/second-opinion/sessions/o1`, { waitUntil: "domcontentloaded" });
    await page.getByText("FILES").waitFor();
    await page.getByText("redaction-preview.md").last().click();
    await page.getByText("+++ redaction-preview.md").waitFor();

    await page.goto(`${BASE_URL}/caspian`, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => {
      window.localStorage.setItem(
        "atlas:panes:caspian",
        JSON.stringify({
          sessions: true,
          chat: true,
          workbench: true,
          files: true,
          inspector: true,
        }),
      );
    });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByText("FILES").waitFor();
    await page.getByText("anticoagulation-note.txt").last().click();
    await page.getByText("Anticoagulation note").waitFor();

    await page.goto(`${BASE_URL}/ground-truth-review/demo-run`, { waitUntil: "domcontentloaded" });
    await page.waitForURL("**/learn/ground-truth-review/demo-run");
    assert.equal(new URL(page.url()).pathname, "/learn/ground-truth-review/demo-run");

    await page.goto(`${BASE_URL}/explorer`, { waitUntil: "domcontentloaded" });
    await page.waitForURL("**/fhir-charts");
    assert.equal(new URL(page.url()).pathname, "/fhir-charts");

    console.log("Atlas shell smoke passed.");
  } finally {
    if (browser) {
      await browser.close();
    }
    stopPreview();
  }
}

async function expectHidden(page, text) {
  await delay(150);
  await assert.doesNotReject(async () => {
    const count = await page.getByText(text).count();
    assert.equal(count, 0);
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
