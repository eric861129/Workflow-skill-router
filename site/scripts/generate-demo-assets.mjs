import { copyFile, mkdir, stat, writeFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';
import ffmpegPath from 'ffmpeg-static';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(siteRoot, '..');
const siteAssets = path.join(siteRoot, 'public', 'assets');
const docsAssets = path.join(repoRoot, 'docs', 'assets');
const run = promisify(execFile);
const demoData = path.join(siteRoot, 'src', 'data', 'router-demo-v2.generated.json');

const outputs = {
  sitePoster: path.join(siteAssets, 'workflow-skill-router-demo-poster.png'),
  docsPoster: path.join(docsAssets, 'workflow-skill-router-demo-poster.png'),
  siteWebm: path.join(siteAssets, 'workflow-skill-router-demo.webm'),
  docsWebm: path.join(docsAssets, 'workflow-skill-router-demo.webm'),
  siteMp4: path.join(siteAssets, 'workflow-skill-router-demo.mp4'),
  docsMp4: path.join(docsAssets, 'workflow-skill-router-demo.mp4'),
  siteManifest: path.join(siteAssets, 'workflow-skill-router-demo-manifest.json'),
  docsManifest: path.join(docsAssets, 'workflow-skill-router-demo-manifest.json'),
};

const digest = (data) => createHash('sha256').update(data).digest('hex');

function assetHtml() {
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      html, body { margin: 0; width: 1280px; height: 720px; background: #11120f; }
      .frame {
        position: relative;
        width: 1280px;
        height: 720px;
        box-sizing: border-box;
        padding: 54px 64px;
        color: #f2f0e7;
        font-family: "Courier New", monospace;
        background:
          radial-gradient(circle at 84% 0%, rgba(199, 255, 55, .18), transparent 32%),
          linear-gradient(135deg, #11120f 0%, #191b17 58%, #0d0e0c 100%);
      }
      .kicker { color: #c7ff37; font-size: 24px; font-weight: 760; letter-spacing: .12em; }
      h1 { margin: 18px 0 16px; max-width: 940px; font-size: 78px; line-height: 1.02; letter-spacing: 0; }
      .sub { max-width: 900px; color: #c5d6ea; font-size: 30px; line-height: 1.35; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; margin-top: 36px; }
      .panel {
        min-height: 184px;
        border: 1px solid rgba(199, 221, 255, .22);
        border-radius: 8px;
        background: rgba(5, 13, 26, .72);
        box-shadow: 0 22px 70px rgba(0, 0, 0, .28);
        padding: 26px;
      }
      .panel h2 { margin: 0 0 18px; color: #e8f4ff; font-size: 24px; line-height: 1.1; }
      .before { color: #fecaca; }
      .after { color: #bbf7d0; }
      .line { margin-top: 12px; color: #d9e7f8; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 20px; line-height: 1.45; }
      .pill { display: inline-block; margin: 0 8px 8px 0; padding: 8px 12px; border-radius: 999px; background: rgba(125, 211, 252, .13); color: #bfdbfe; font-size: 18px; }
      .footer { position: absolute; left: 64px; right: 64px; bottom: 34px; display: flex; justify-content: space-between; color: #96a9c3; font-size: 21px; }
    </style>
  </head>
  <body>
    <main class="frame">
      <div class="kicker">V2 ROUTING FLIGHT RECORDER</div>
      <h1>Single. Phased. Managed Goal.</h1>
      <div class="sub">Runtime discovery, explicit SKILL consent, durable state, and evidence—visible before execution.</div>
      <section class="grid">
        <div class="panel">
          <h2 class="before">INPUT / EXPLICIT LOCK</h2>
          <div class="line">“Use api-designer.</div>
          <div class="line">Ask before adding support.”</div>
        </div>
        <div class="panel">
          <h2 class="after">OUTPUT / AUDITABLE ROUTE</h2>
          <span class="pill">primary: api-designer</span>
          <span class="pill">envelope: single</span>
          <span class="pill">support: rejected</span>
          <div class="line">Requested SKILL only · coverage satisfied.</div>
        </div>
      </section>
      <div class="footer"><span>core-derived · skill-only-fallback / hybrid-full</span><span>github.com/eric861129/Workflow-skill-router</span></div>
    </main>
  </body>
</html>`;
}

function recordingPageHtml() {
  return `<!doctype html>
<html>
  <body style="margin:0;background:#07111f">
    <canvas id="demo" width="1280" height="720"></canvas>
    <script>
      const canvas = document.querySelector('#demo');
      const ctx = canvas.getContext('2d');
      const W = canvas.width;
      const H = canvas.height;
      const durationMs = 10000;

      function ease(value) {
        return 1 - Math.pow(1 - value, 3);
      }

      function roundedRect(x, y, width, height, radius) {
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
      }

      function drawPanel(x, y, width, height, title, lines, accent) {
        ctx.fillStyle = 'rgba(5,13,26,.76)';
        ctx.strokeStyle = 'rgba(199,221,255,.22)';
        ctx.lineWidth = 1;
        roundedRect(x, y, width, height, 10);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = accent;
        ctx.font = '700 28px system-ui, sans-serif';
        ctx.fillText(title, x + 28, y + 48);
        ctx.fillStyle = '#d9e7f8';
        ctx.font = '22px Consolas, monospace';
        lines.forEach((line, index) => ctx.fillText(line, x + 28, y + 92 + index * 38));
      }

      function drawPill(text, x, y) {
        ctx.font = '20px system-ui, sans-serif';
        const width = ctx.measureText(text).width + 28;
        ctx.fillStyle = 'rgba(125,211,252,.14)';
        roundedRect(x, y, width, 42, 21);
        ctx.fill();
        ctx.fillStyle = '#bfdbfe';
        ctx.fillText(text, x + 14, y + 28);
        return width;
      }

      function draw(progress) {
        const gradient = ctx.createLinearGradient(0, 0, W, H);
        gradient.addColorStop(0, '#07111f');
        gradient.addColorStop(.52, '#12213a');
        gradient.addColorStop(1, '#0d1b2f');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, W, H);

        ctx.fillStyle = 'rgba(57,189,248,.20)';
        ctx.beginPath();
        ctx.arc(170, 40, 270, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#7dd3fc';
        ctx.font = '760 28px system-ui, sans-serif';
        ctx.fillText('Workflow Skill Router', 64, 82);
        ctx.fillStyle = '#eef6ff';
        ctx.font = '760 70px system-ui, sans-serif';
        ctx.fillText('Fuzzy request in.', 64, 164);
        ctx.fillText('Focused skills out.', 64, 244);

        const stage = Math.min(2, Math.floor(progress * 3));
        const local = ease((progress * 3) % 1);
        const leftX = 64 - (1 - local) * 28;
        const rightX = 660 + (1 - local) * 28;

        drawPanel(leftX, 318, 552, 238, 'Request', [
          '“Add audit tables and keep',
          'the admin query fast.”',
          '',
          stage === 0 ? 'Router is reading intent...' : 'Intent: API + database + QA',
        ], '#fecaca');

        drawPanel(rightX, 318, 552, 238, stage < 2 ? 'Route' : 'Validated route', [
          'Primary: api-designer',
          'Supporting: database-optimizer',
          'Supporting: qa-test-planner',
          stage < 2 ? 'Omit: frontend-design' : 'Validator: PASS',
        ], stage < 2 ? '#bbf7d0' : '#86efac');

        let x = 64;
        x += drawPill('bounded to 3 skills', x, 590) + 10;
        x += drawPill('explicit omissions', x, 590) + 10;
        drawPill(stage < 2 ? 'reviewable plan' : 'public-ready docs', x, 590);
      }

      window.recordDemo = async () => {
        const stream = canvas.captureStream(30);
        const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' });
        const chunks = [];
        recorder.ondataavailable = event => event.data.size && chunks.push(event.data);
        const stopped = new Promise(resolve => recorder.onstop = resolve);
        recorder.start();
        const started = performance.now();
        await new Promise(resolve => {
          function frame(now) {
            const progress = Math.min(1, (now - started) / durationMs);
            draw(progress);
            if (progress < 1) requestAnimationFrame(frame);
            else resolve();
          }
          requestAnimationFrame(frame);
        });
        recorder.stop();
        await stopped;
        const blob = new Blob(chunks, { type: 'video/webm' });
        const buffer = await blob.arrayBuffer();
        return Array.from(new Uint8Array(buffer));
      };

      draw(0);
    </script>
  </body>
</html>`;
}

async function assertFile(filePath, maximumBytes) {
  const details = await stat(filePath);
  if (!details.isFile() || details.size === 0) {
    throw new Error(`${path.relative(repoRoot, filePath)} is missing or empty.`);
  }
  if (maximumBytes && details.size > maximumBytes) {
    throw new Error(`${path.relative(repoRoot, filePath)} is ${details.size} bytes, expected <= ${maximumBytes}.`);
  }
}

async function checkAssets() {
  await assertFile(outputs.sitePoster, 1_500_000);
  await assertFile(outputs.docsPoster, 1_500_000);
  await assertFile(outputs.siteWebm, 12_000_000);
  await assertFile(outputs.docsWebm, 12_000_000);
  await assertFile(outputs.siteMp4, 15_000_000);
  await assertFile(outputs.docsMp4, 15_000_000);
  const manifest = JSON.parse(await readFile(outputs.siteManifest, 'utf8'));
  for (const [key, filePath] of Object.entries({ poster: outputs.sitePoster, webm: outputs.siteWebm, mp4: outputs.siteMp4 })) {
    const actual = digest(await readFile(filePath));
    if (manifest.outputs[key].sha256 !== actual) throw new Error(`${key} digest does not match demo manifest.`);
  }
  if (manifest.source.sha256 !== digest(await readFile(demoData))) throw new Error('Demo data revision is stale.');
  console.log('OK: demo media assets passed');
}

async function generateAssets() {
  await mkdir(siteAssets, { recursive: true });
  await mkdir(docsAssets, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
    await page.setContent(assetHtml());
    await page.screenshot({ path: outputs.sitePoster, clip: { x: 0, y: 0, width: 1280, height: 720 } });
    await copyFile(outputs.sitePoster, outputs.docsPoster);

    await page.setContent(recordingPageHtml());
    const bytes = await page.evaluate(() => window.recordDemo());
    await writeFile(outputs.siteWebm, Buffer.from(bytes));
    await copyFile(outputs.siteWebm, outputs.docsWebm);
    if (!ffmpegPath) throw new Error('ffmpeg-static executable is unavailable.');
    const revision = digest(await readFile(demoData));
    await run(ffmpegPath, ['-y', '-i', outputs.siteWebm, '-metadata', `comment=demo-revision:${revision}`,
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', outputs.siteMp4]);
    await copyFile(outputs.siteMp4, outputs.docsMp4);
    const manifest = {
      schema_version: '1.0', source: { path: 'site/src/data/router-demo-v2.generated.json', sha256: revision },
      outputs: {
        poster: { sha256: digest(await readFile(outputs.sitePoster)), width: 1280, height: 720, codec: 'png' },
        webm: { sha256: digest(await readFile(outputs.siteWebm)), width: 1280, height: 720, codec: 'vp9' },
        mp4: { sha256: digest(await readFile(outputs.siteMp4)), width: 1280, height: 720, codec: 'h264' },
      },
    };
    await writeFile(outputs.siteManifest, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
    await copyFile(outputs.siteManifest, outputs.docsManifest);
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
