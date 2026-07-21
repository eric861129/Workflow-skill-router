import { mkdir, stat, writeFile, readFile, unlink } from 'node:fs/promises';
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
const run = promisify(execFile);
const demoData = path.join(siteRoot, 'src', 'data', 'router-demo-v2.generated.json');

const outputs = {
  posterSource: path.join(siteRoot, 'dist', 'workflow-skill-router-demo-poster-source.png'),
  sitePoster: path.join(siteAssets, 'workflow-skill-router-demo-poster.webp'),
  siteWebm: path.join(siteAssets, 'workflow-skill-router-demo.webm'),
  siteMp4: path.join(siteAssets, 'workflow-skill-router-demo.mp4'),
  siteManifest: path.join(siteAssets, 'workflow-skill-router-demo-manifest.json'),
};

const digest = (data) => createHash('sha256').update(data).digest('hex');

function resultForTool(preset, toolName, occurrence = 0) {
  const indexes = preset.mcp_calls
    .map((call, index) => call.tool === toolName ? index : -1)
    .filter(index => index >= 0);
  const index = indexes[occurrence];
  if (index === undefined) throw new Error(`Missing required public demo tool result: ${toolName}.`);
  return preset.mcp_results[index];
}

async function selectPublicBoundaryData() {
  const document = JSON.parse(await readFile(demoData, 'utf8'));
  const byId = new Map(document.presets.map(preset => [preset.id, preset]));
  const local = byId.get('router-local-work-loop');
  const nativeGoal = byId.get('goal-work-graph');
  if (!local || !nativeGoal) throw new Error('Required public boundary presets are unavailable.');

  const localNext = resultForTool(local, 'get_next_work').result;
  const localRecord = resultForTool(local, 'record_work_event').result;
  const localGate = resultForTool(local, 'evaluate_gate').result;
  const nativeNext = resultForTool(nativeGoal, 'get_next_work').error;
  const presentation = {
    source_preset_ids: ['router-local-work-loop', 'goal-work-graph'],
    router_local: {
      authority_mode: localNext.authority_mode,
      host_goal_mutated: localNext.host_goal_mutated,
      evidence_class: localRecord.evidence_class,
      host_transition_authorized: localRecord.host_transition_authorized,
      gate_scope: localGate.gate_scope,
    },
    native_goal: {
      code: nativeNext.code,
      availability: nativeNext.availability,
      required_capabilities: nativeNext.required_capabilities,
    },
  };
  const valid = presentation.router_local.authority_mode === 'router-local'
    && presentation.router_local.host_goal_mutated === false
    && presentation.router_local.evidence_class === 'user-or-agent-reported-local'
    && presentation.router_local.host_transition_authorized === false
    && presentation.router_local.gate_scope === 'router-local'
    && presentation.native_goal.code === 'capability-unavailable'
    && presentation.native_goal.availability === 'conditional-local'
    && Array.isArray(presentation.native_goal.required_capabilities)
    && presentation.native_goal.required_capabilities.length === 1
    && presentation.native_goal.required_capabilities[0] === 'verified-host-scheduler';
  if (!valid) throw new Error('Public boundary presets do not satisfy the safe visual contract.');
  return presentation;
}

function assetHtml(boundary) {
  const local = boundary.router_local;
  const nativeGoal = boundary.native_goal;
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
        padding: 40px 64px;
        color: #f2f0e7;
        font-family: "Courier New", monospace;
        background:
          radial-gradient(circle at 84% 0%, rgba(199, 255, 55, .18), transparent 32%),
          linear-gradient(135deg, #11120f 0%, #191b17 58%, #0d0e0c 100%);
      }
      .kicker { color: #c7ff37; font-size: 24px; font-weight: 760; letter-spacing: .12em; }
      h1 { margin: 12px 0 10px; max-width: 1120px; font-size: 60px; line-height: 1.02; letter-spacing: 0; }
      .sub { max-width: 1000px; color: #c5d6ea; font-size: 25px; line-height: 1.25; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; margin-top: 22px; }
      .panel {
        min-height: 154px;
        border: 1px solid rgba(199, 221, 255, .22);
        border-radius: 8px;
        background: rgba(5, 13, 26, .72);
        box-shadow: 0 22px 70px rgba(0, 0, 0, .28);
        padding: 20px 24px;
      }
      .panel h2 { margin: 0 0 14px; color: #e8f4ff; font-size: 21px; line-height: 1.1; }
      .before { color: #fecaca; }
      .after { color: #bbf7d0; }
      .line { margin-top: 9px; color: #d9e7f8; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 18px; line-height: 1.35; }
      .pill { display: inline-block; margin: 0 8px 8px 0; padding: 8px 12px; border-radius: 999px; background: rgba(125, 211, 252, .13); color: #bfdbfe; font-size: 18px; }
      .footer { position: absolute; left: 64px; right: 64px; bottom: 20px; display: flex; justify-content: space-between; color: #96a9c3; font-size: 17px; }
    </style>
  </head>
  <body>
    <main class="frame">
      <div class="kicker">V2 ROUTING FLIGHT RECORDER</div>
      <h1>Router-local advisory.<br />Native Goal fails closed.</h1>
      <div class="sub">Runtime-derived boundaries without fabricated Host authority.</div>
      <section class="grid">
        <div class="panel">
          <h2 class="after">ROUTER-OWNED WORK GRAPH</h2>
          <div class="line">authority_mode: ${local.authority_mode}</div>
          <div class="line">host_goal_mutated: ${local.host_goal_mutated}</div>
          <div class="line">gate_scope: ${local.gate_scope}</div>
        </div>
        <div class="panel">
          <h2 class="before">Native Goal requires verified Host</h2>
          <div class="line">code: ${nativeGoal.code}</div>
          <div class="line">availability: ${nativeGoal.availability}</div>
          <div class="line">requires: ${nativeGoal.required_capabilities[0]}</div>
        </div>
      </section>
      <div class="footer"><span>${local.evidence_class} · no Host transition</span><span>github.com/eric861129/Workflow-skill-router</span></div>
    </main>
  </body>
</html>`;
}

function recordingPageHtml(boundary) {
  const safeBoundaryJson = JSON.stringify(boundary).replaceAll('<', '\\u003c');
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
      const boundary = ${safeBoundaryJson};

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
        const nativeStage = progress >= .5;
        ctx.fillText(nativeStage ? 'Native Goal requires' : 'Router-local advisory', 64, 164);
        ctx.fillText(nativeStage ? 'verified Host.' : 'without Host mutation.', 64, 244);

        const motion = ease((progress * 2) % 1);
        const leftX = 64 - (1 - motion) * 28;
        const rightX = 660 + (1 - motion) * 28;

        if (!nativeStage) {
          drawPanel(leftX, 318, 552, 238, 'Router-owned work graph', [
            'authority_mode: ' + boundary.router_local.authority_mode,
            'evidence: ' + boundary.router_local.evidence_class,
            'gate_scope: ' + boundary.router_local.gate_scope,
          ], '#86efac');
          drawPanel(rightX, 318, 552, 238, 'Advisory boundary', [
            'host_goal_mutated: ' + boundary.router_local.host_goal_mutated,
            'host_transition_authorized: ' + boundary.router_local.host_transition_authorized,
            'No activation or production claim',
          ], '#bbf7d0');
        } else {
          drawPanel(leftX, 318, 552, 238, 'Native Goal', [
            'code: ' + boundary.native_goal.code,
            'availability: ' + boundary.native_goal.availability,
            'Local runtime: fail closed',
          ], '#fecaca');
          drawPanel(rightX, 318, 552, 238, 'Verified Host required', [
            'requires: ' + boundary.native_goal.required_capabilities[0],
            'No local Host mutation',
            'No fabricated scheduler result',
          ], '#fcd34d');
        }

        let x = 64;
        x += drawPill(nativeStage ? boundary.native_goal.code : boundary.router_local.authority_mode, x, 590) + 10;
        x += drawPill(nativeStage ? boundary.native_goal.required_capabilities[0] : boundary.router_local.gate_scope, x, 590) + 10;
        drawPill(nativeStage ? 'verified Host path' : 'advisory evidence only', x, 590);
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
  try {
    await stat(outputs.posterSource);
    throw new Error(`${path.relative(repoRoot, outputs.posterSource)} is a stale temporary source file.`);
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  await assertFile(outputs.sitePoster, 250_000);
  await assertFile(outputs.siteWebm, 12_000_000);
  await assertFile(outputs.siteMp4, 15_000_000);
  const manifest = JSON.parse(await readFile(outputs.siteManifest, 'utf8'));
  const presentation = await selectPublicBoundaryData();
  for (const [key, filePath] of Object.entries({ poster: outputs.sitePoster, webm: outputs.siteWebm, mp4: outputs.siteMp4 })) {
    const actual = digest(await readFile(filePath));
    if (manifest.outputs[key].sha256 !== actual) throw new Error(`${key} digest does not match demo manifest.`);
  }
  if (manifest.source.sha256 !== digest(await readFile(demoData))) throw new Error('Demo data revision is stale.');
  if (JSON.stringify(manifest.presentation) !== JSON.stringify(presentation)) {
    throw new Error('Demo visual boundary presentation is stale.');
  }
  console.log('OK: demo media assets passed');
}

async function generateAssets() {
  await mkdir(siteAssets, { recursive: true });
  await mkdir(path.dirname(outputs.posterSource), { recursive: true });
  const presentation = await selectPublicBoundaryData();

  const browser = await chromium.launch({ headless: true });
  try {
    if (!ffmpegPath) throw new Error('ffmpeg-static executable is unavailable.');
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
    await page.setContent(assetHtml(presentation));
    await page.screenshot({
      path: outputs.posterSource,
      clip: { x: 0, y: 0, width: 1280, height: 720 },
    });
    await run(ffmpegPath, [
      '-y',
      '-i', outputs.posterSource,
      '-frames:v', '1',
      '-c:v', 'libwebp',
      '-quality', '82',
      outputs.sitePoster,
    ]);

    await page.setContent(recordingPageHtml(presentation));
    const bytes = await page.evaluate(() => window.recordDemo());
    await writeFile(outputs.siteWebm, Buffer.from(bytes));
    const revision = digest(await readFile(demoData));
    await run(ffmpegPath, ['-y', '-i', outputs.siteWebm, '-metadata', `comment=demo-revision:${revision}`,
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', outputs.siteMp4]);
    const manifest = {
      schema_version: '1.0', source: { path: 'site/src/data/router-demo-v2.generated.json', sha256: revision },
      presentation,
      outputs: {
        poster: { sha256: digest(await readFile(outputs.sitePoster)), width: 1280, height: 720, codec: 'webp' },
        webm: { sha256: digest(await readFile(outputs.siteWebm)), width: 1280, height: 720, codec: 'vp9' },
        mp4: { sha256: digest(await readFile(outputs.siteMp4)), width: 1280, height: 720, codec: 'h264' },
      },
    };
    await writeFile(outputs.siteManifest, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
  } finally {
    await browser.close();
    try {
      await unlink(outputs.posterSource);
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
  }

  await checkAssets();
}

if (process.argv.includes('--check')) {
  await checkAssets();
} else {
  await generateAssets();
}
