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
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700&family=Source+Serif+4:wght@400;600&display=swap" rel="stylesheet" />
    <style>
      * { box-sizing: border-box; margin: 0; }
      html, body { width: 1200px; height: 630px; background: #ebe5e3; }
      .board {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        grid-template-rows: 170px 1fr 64px;
        gap: 8px;
        width: 1200px;
        height: 630px;
        padding: 8px;
        color: #2b2622;
        font-family: 'Libre Franklin', 'Segoe UI', sans-serif;
      }
      .name {
        grid-column: 1 / -1;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #2b2622;
        color: #f1eeed;
        font-size: 86px;
        font-weight: 700;
        letter-spacing: -0.035em;
        text-transform: uppercase;
        white-space: nowrap;
      }
      .statement {
        grid-column: 1 / 7;
        display: flex;
        align-items: flex-end;
        padding: 28px;
        background: #f4f0ee;
        font-size: 44px;
        font-weight: 700;
        line-height: 1.08;
        letter-spacing: -0.025em;
      }
      .rows { grid-column: 7 / -1; display: grid; gap: 6px; }
      .row {
        display: grid;
        grid-template-columns: 1.2fr 1.5fr 1fr;
        align-items: center;
        gap: 12px;
        padding: 0 18px;
        background: #e1dad7;
        font-size: 21px;
        font-weight: 600;
      }
      .row b { font-weight: 700; }
      .row span:last-child { justify-self: end; padding: 6px 10px; background: #f4f0ee; font-size: 17px; }
      .row.is-lead { background: #0f7d45; color: #ffffff; }
      .row.is-lead span:last-child { background: #ffffff; color: #0f7d45; }
      .foot { grid-column: 1 / 10; display: flex; align-items: center; padding: 0 20px; background: #cfc6c2; font-family: 'Source Serif 4', Georgia, serif; font-size: 22px; }
      .action { grid-column: 10 / -1; display: flex; align-items: center; padding: 0 20px; background: #0f7d45; color: #ffffff; font-size: 22px; font-weight: 700; }
    </style>
  </head>
  <body>
    <main class="board">
      <div class="name">Workflow Skill Router</div>
      <div class="statement">One lead Skill per phase, for Claude Code and Codex.</div>
      <div class="rows">
        <div class="row is-lead"><b>contract</b><span>api-designer</span><span>leads now</span></div>
        <div class="row"><b>implementation</b><span>csharp-developer</span><span>next</span></div>
        <div class="row"><b>verification</b><span>qa-test-planner</span><span>later</span></div>
      </div>
      <div class="foot">Open source, MIT. Your workflow as config, every route inspectable.</div>
      <div class="action">github.com/eric861129</div>
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
    await page.setContent(socialHtml(), { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
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
