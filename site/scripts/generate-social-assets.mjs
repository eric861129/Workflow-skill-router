import { mkdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(siteRoot, '..');
const siteOg = path.join(siteRoot, 'public', 'og');

const outputs = {
  siteOg: path.join(siteOg, 'workflow-skill-router.png'),
};

function socialHtml() {
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      html, body { margin: 0; width: 1200px; height: 630px; background: #07111f; }
      .card {
        width: 1200px;
        height: 630px;
        box-sizing: border-box;
        padding: 54px 62px;
        color: #eef6ff;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background:
          radial-gradient(circle at 12% 0%, rgba(14, 165, 233, .28), transparent 31%),
          linear-gradient(135deg, #07111f 0%, #13233e 54%, #0d1b2f 100%);
      }
      .topline { color: #7dd3fc; font-size: 25px; font-weight: 760; letter-spacing: 0; }
      h1 { margin: 16px 0 14px; max-width: 980px; font-size: 76px; line-height: 1; letter-spacing: 0; }
      .sub { max-width: 870px; color: #c5d6ea; font-size: 28px; line-height: 1.3; }
      .flow { display: grid; grid-template-columns: 1fr 92px 1fr; gap: 20px; align-items: center; margin-top: 38px; }
      .box {
        height: 188px;
        box-sizing: border-box;
        border: 1px solid rgba(199, 221, 255, .22);
        border-radius: 8px;
        background: rgba(5, 13, 26, .76);
        padding: 24px;
      }
      .box h2 { margin: 0 0 16px; font-size: 24px; }
      .bad { color: #fecaca; }
      .good { color: #bbf7d0; }
      .mono { color: #d9e7f8; font: 21px/1.45 Consolas, ui-monospace, monospace; }
      .arrow { color: #7dd3fc; text-align: center; font-size: 66px; font-weight: 760; }
      .footer { margin-top: 28px; display: flex; justify-content: space-between; align-items: center; color: #9eb2cc; font-size: 21px; }
      .badge { color: #dbeafe; border: 1px solid rgba(125, 211, 252, .36); border-radius: 999px; padding: 9px 14px; background: rgba(125, 211, 252, .11); }
    </style>
  </head>
  <body>
    <main class="card">
      <div class="topline">Codex Plugin / MCP + SKILL fallback</div>
      <h1>Workflow Skill Router V2</h1>
      <div class="sub">Deterministic routing, scoped consent, durable state, and inspectable evidence for real developer workflows.</div>
      <section class="flow">
        <div class="box">
          <h2 class="bad">Before</h2>
          <div class="mono">skill sprawl<br />generic consent<br />no runtime proof</div>
        </div>
        <div class="arrow">→</div>
        <div class="box">
          <h2 class="good">After</h2>
          <div class="mono">Single · Phased · Managed Goal<br />scoped consent<br />inspectable evidence</div>
        </div>
      </section>
      <div class="footer">
        <span class="badge">Runtime Capability Discovery</span>
        <span>github.com/eric861129/Workflow-skill-router</span>
      </div>
    </main>
  </body>
</html>`;
}

async function assertFile(filePath) {
  const details = await stat(filePath);
  if (!details.isFile() || details.size === 0) {
    throw new Error(`${path.relative(repoRoot, filePath)} is missing or empty.`);
  }
  if (details.size > 1_500_000) {
    throw new Error(`${path.relative(repoRoot, filePath)} is ${details.size} bytes, expected <= 1500000.`);
  }
}

async function checkAssets() {
  await assertFile(outputs.siteOg);
  console.log('OK: social preview assets passed');
}

async function generateAssets() {
  await mkdir(siteOg, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
    await page.setContent(socialHtml());
    await page.screenshot({ path: outputs.siteOg, clip: { x: 0, y: 0, width: 1200, height: 630 } });
  } finally {
    await browser.close();
  }

  await checkAssets();
}

if (process.argv.includes('--check')) {
  await checkAssets();
} else {
  await generateAssets();
}
