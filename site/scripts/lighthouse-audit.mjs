import { createServer } from 'node:http';
import { readFile, stat, mkdir, writeFile } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { createGzip } from 'node:zlib';
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
  performance: Number(process.env.LH_MIN_PERFORMANCE ?? 0.9),
  accessibility: Number(process.env.LH_MIN_ACCESSIBILITY ?? 1),
  'best-practices': Number(process.env.LH_MIN_BEST_PRACTICES ?? 1),
  seo: Number(process.env.LH_MIN_SEO ?? 1),
};

const routes = [
  { name: 'home-en', path: '/' },
  { name: 'home-zh-tw', path: '/zh-tw/' },
  { name: 'showcase-en', path: '/showcase/', maxLcpMs: 2500 },
  { name: 'showcase-zh-tw', path: '/zh-tw/showcase/', maxLcpMs: 2500 },
  { name: 'v2-routing-en', path: '/guides/v2-routing/' },
  { name: 'v2-routing-zh-tw', path: '/zh-tw/guides/v2-routing/' },
  { name: 'mcp-tools-en', path: '/reference/mcp-tools/' },
  { name: 'mcp-tools-zh-tw', path: '/zh-tw/reference/mcp-tools/' },
  { name: 'install-plugin-en', path: '/guides/install-plugin/' },
  { name: 'install-plugin-zh-tw', path: '/zh-tw/guides/install-plugin/' },
  { name: 'install-skill-en', path: '/guides/install-skill/' },
  { name: 'install-skill-zh-tw', path: '/zh-tw/guides/install-skill/' },
];

const mimeTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.mp4', 'video/mp4'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml; charset=utf-8'],
  ['.webp', 'image/webp'],
  ['.webm', 'video/webm'],
  ['.xml', 'application/xml; charset=utf-8'],
  ['.txt', 'text/plain; charset=utf-8'],
]);

const compressibleExtensions = new Set(['.css', '.html', '.js', '.json', '.svg', '.txt', '.xml']);

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
    const acceptsGzip = request.headers['accept-encoding']?.includes('gzip');
    const useGzip = Boolean(acceptsGzip && compressibleExtensions.has(extension));

    response.writeHead(statusCode, {
      'content-type': mimeTypes.get(extension) ?? 'application/octet-stream',
      'cache-control': extension === '.html' ? 'no-store' : 'public, max-age=3600',
      ...(useGzip ? { 'content-encoding': 'gzip', vary: 'Accept-Encoding' } : {}),
    });
    const fileStream = createReadStream(filePath);
    if (useGzip) fileStream.pipe(createGzip()).pipe(response);
    else fileStream.pipe(response);
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

async function runLighthouse(url, route, chromePort) {
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

  const reportName = slugify(route.name);
  await writeFile(path.join(reportRoot, `${reportName}.json`), jsonReport, 'utf-8');
  await writeFile(path.join(reportRoot, `${reportName}.html`), htmlReport, 'utf-8');

  const scores = Object.fromEntries(
    Object.entries(runnerResult.lhr.categories).map(([key, value]) => [key, scoreOf(value)])
  );
  const lcpMs = Math.round(runnerResult.lhr.audits['largest-contentful-paint'].numericValue ?? 0);
  return {
    name: route.name,
    url,
    scores,
    metrics: { lcpMs },
    budgets: { maxLcpMs: route.maxLcpMs ?? null },
  };
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
    if (result.budgets.maxLcpMs && result.metrics.lcpMs >= result.budgets.maxLcpMs) {
      failures.push(`${result.name}: LCP ${result.metrics.lcpMs}ms >= ${result.budgets.maxLcpMs}ms`);
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
      const result = await runLighthouse(url, route, chrome.port);
      results.push(result);
      console.log(`${result.name}: ${formatScores(result.scores)} lcp=${result.metrics.lcpMs}ms`);
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
