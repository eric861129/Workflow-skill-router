import { createServer } from 'node:http';
import { readFile, stat, mkdir, writeFile } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(__dirname, '..');
const distRoot = path.join(siteRoot, 'dist');
const reportRoot = path.join(siteRoot, 'lighthouse-reports');
const basePath = '/Workflow-skill-router/';

const thresholds = {
  performance: Number(process.env.LH_MIN_PERFORMANCE ?? 0.7),
  accessibility: Number(process.env.LH_MIN_ACCESSIBILITY ?? 0.95),
  'best-practices': Number(process.env.LH_MIN_BEST_PRACTICES ?? 0.9),
  seo: Number(process.env.LH_MIN_SEO ?? 0.9),
};

const routes = [
  { name: 'home-en', path: '/' },
  { name: 'home-zh-tw', path: '/zh-tw/' },
  { name: 'downloads-en', path: '/guides/downloads/' },
  { name: 'template-catalog-en', path: '/examples/template-skill-catalog/' },
  { name: 'template-catalog-zh-tw', path: '/zh-tw/examples/template-skill-catalog/' },
  { name: 'validator-en', path: '/reference/validator/' },
];

const mimeTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml; charset=utf-8'],
  ['.webp', 'image/webp'],
  ['.xml', 'application/xml; charset=utf-8'],
  ['.txt', 'text/plain; charset=utf-8'],
]);

function resolveStaticPath(urlPath) {
  let pathname = decodeURIComponent(urlPath.split('?')[0] || '/');
  if (pathname.startsWith(basePath)) {
    pathname = pathname.slice(basePath.length - 1);
  }

  if (pathname === '/' || pathname.endsWith('/')) {
    pathname = path.posix.join(pathname, 'index.html');
  }

  const normalized = path.normalize(pathname).replace(/^(\.\.[/\\])+/, '');
  const resolved = path.resolve(distRoot, `.${path.sep}${normalized}`);
  if (!resolved.startsWith(distRoot)) {
    return path.join(distRoot, '404.html');
  }
  return resolved;
}

async function fileExists(filePath) {
  try {
    const details = await stat(filePath);
    return details.isFile();
  } catch {
    return false;
  }
}

function startStaticServer() {
  const server = createServer(async (request, response) => {
    const requested = resolveStaticPath(request.url ?? '/');
    const exists = await fileExists(requested);
    const filePath = exists ? requested : path.join(distRoot, '404.html');
    const statusCode = exists ? 200 : 404;
    const extension = path.extname(filePath);

    response.writeHead(statusCode, {
      'content-type': mimeTypes.get(extension) ?? 'application/octet-stream',
      'cache-control': 'no-store',
    });
    createReadStream(filePath).pipe(response);
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (!address || typeof address === 'string') {
        reject(new Error('Unable to bind local Lighthouse server.'));
        return;
      }
      resolve({ server, origin: `http://127.0.0.1:${address.port}` });
    });
  });
}

function scoreOf(category) {
  return Math.round((category.score ?? 0) * 100);
}

function slugify(value) {
  return value.replace(/[^a-z0-9-]+/gi, '-').replace(/^-|-$/g, '').toLowerCase();
}

async function runLighthouse(url, name, chromePort) {
  const runnerResult = await lighthouse(url, {
    port: chromePort,
    logLevel: 'error',
    output: ['json', 'html'],
    onlyCategories: Object.keys(thresholds),
  });

  if (!runnerResult) {
    throw new Error(`Lighthouse did not return a result for ${url}`);
  }

  const [jsonReport, htmlReport] = Array.isArray(runnerResult.report)
    ? runnerResult.report
    : [JSON.stringify(runnerResult.lhr, null, 2), runnerResult.report];

  const reportName = slugify(name);
  await writeFile(path.join(reportRoot, `${reportName}.json`), jsonReport, 'utf-8');
  await writeFile(path.join(reportRoot, `${reportName}.html`), htmlReport, 'utf-8');

  const scores = Object.fromEntries(
    Object.entries(runnerResult.lhr.categories).map(([key, value]) => [key, scoreOf(value)])
  );
  return { name, url, scores };
}

function formatScores(scores) {
  return Object.entries(scores)
    .map(([key, value]) => `${key}=${value}`)
    .join(' ');
}

function findFailures(results) {
  const failures = [];
  for (const result of results) {
    for (const [category, minimum] of Object.entries(thresholds)) {
      const score = result.scores[category] ?? 0;
      if (score < minimum * 100) {
        failures.push(`${result.name}: ${category} ${score} < ${Math.round(minimum * 100)}`);
      }
    }
  }
  return failures;
}

async function main() {
  if (!(await fileExists(path.join(distRoot, 'index.html')))) {
    throw new Error('site/dist/index.html is missing. Run `npm run build` before Lighthouse.');
  }

  await mkdir(reportRoot, { recursive: true });
  await readFile(path.join(distRoot, '404.html'), 'utf-8');

  const { server, origin } = await startStaticServer();
  const chrome = await chromeLauncher.launch({
    chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
  });

  try {
    const results = [];
    for (const route of routes) {
      const url = `${origin}${basePath.replace(/\/$/, '')}${route.path}`;
      const result = await runLighthouse(url, route.name, chrome.port);
      results.push(result);
      console.log(`${result.name}: ${formatScores(result.scores)}`);
    }

    const summary = {
      generatedAt: new Date().toISOString(),
      thresholds: Object.fromEntries(
        Object.entries(thresholds).map(([key, value]) => [key, Math.round(value * 100)])
      ),
      results,
    };
    await writeFile(path.join(reportRoot, 'summary.json'), JSON.stringify(summary, null, 2), 'utf-8');

    const failures = findFailures(results);
    if (failures.length > 0) {
      console.error('\nLighthouse thresholds failed:');
      for (const failure of failures) {
        console.error(`- ${failure}`);
      }
      console.error(`\nReports written to ${path.relative(siteRoot, reportRoot)}`);
      process.exitCode = 1;
      return;
    }

    console.log(`\nOK: Lighthouse audit passed. Reports written to ${path.relative(siteRoot, reportRoot)}`);
  } finally {
    try {
      await chrome.kill();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.warn(`WARN: Lighthouse audit passed, but Chrome cleanup failed: ${message}`);
    }
    await new Promise((resolve) => server.close(resolve));
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
