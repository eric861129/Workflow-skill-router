import { expect, test } from '@playwright/test';
import { access, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const siteRoot = fileURLToPath(new URL('..', import.meta.url));

const pages = [
  { path: './', text: 'Workflow Skill Router' },
  { path: 'guides/quickstart/', text: 'V2 Quickstart' },
  { path: 'guides/downloads/', text: 'Choose your V2 install mode' },
  { path: 'guides/install-plugin/', text: 'Install the Plugin + MCP runtime' },
  { path: 'concepts/runtime-capability-discovery/', text: 'Runtime Capability Discovery' },
  { path: 'reference/mcp-tools/', text: 'MCP Tools' },
  { path: 'zh-tw/guides/quickstart/', text: 'V2 快速開始' },
  { path: 'zh-tw/guides/install-plugin/', text: '安裝 Plugin + MCP Runtime' },
  { path: 'zh-tw/concepts/runtime-capability-discovery/', text: 'Runtime Capability Discovery' },
  { path: 'zh-tw/reference/mcp-tools/', text: 'MCP Tools' },
];

test('homepage presents the V2 product and install choices first', async ({ page }) => {
  await page.goto('./');
  const hero = page.locator('.wsr-hero');
  await expect(hero.getByRole('heading', { name: /runtime-aware skill routing for real codex work/i })).toBeVisible();
  await expect(hero.getByRole('link', { name: /install plugin \+ mcp/i })).toBeVisible();
  await expect(hero.getByRole('link', { name: /use skill only/i })).toBeVisible();
  await expect(page.getByText('Download Blank Router')).toHaveCount(0);
});

test('mobile navigation exposes the full brand and named theme control', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('./');
  await expect(page.getByRole('link', { name: 'Workflow Skill Router', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /toggle color theme/i })).toBeVisible();
});

test('homepage keyboard focus and heading hierarchy stay accessible', async ({ page }) => {
  await page.goto('./');

  const primaryAction = page.locator('.wsr-hero').getByRole('link', { name: /install plugin \+ mcp/i });
  await primaryAction.focus();
  await expect(primaryAction).toBeFocused();
  const focusStyle = await primaryAction.evaluate((element) => {
    const style = getComputedStyle(element);
    return { outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
  });
  expect(focusStyle.outlineStyle).not.toBe('none');
  expect(focusStyle.outlineWidth).not.toBe('0px');

  const headingLevels = await page.locator('main h1, main h2, main h3, main h4, main h5, main h6').evaluateAll(
    (headings) => headings.map((heading) => Number(heading.tagName.slice(1))),
  );
  expect(headingLevels.filter((level) => level === 1)).toHaveLength(1);
  expect(headingLevels[0]).toBe(1);
  await expect(page.locator('h1#_top')).toHaveCount(1);
  for (let index = 1; index < headingLevels.length; index += 1) {
    expect(headingLevels[index] - headingLevels[index - 1]).toBeLessThanOrEqual(1);
  }
});

test('flight recorder exposes named copy and keyboard disclosure controls', async ({ page }) => {
  await page.goto('./');
  const disclosure = page.getByTestId('demo-mcp-step').first().locator('summary');
  await disclosure.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('demo-mcp-step').first()).toHaveAttribute('open', '');
  await expect(page.getByRole('button', { name: 'Copy JSON' }).first()).toBeVisible();
});

test('production output excludes legacy media fallbacks', async () => {
  const legacyAssets = [
    'workflow_skill_rout-GIF.gif',
    'workflow-skill-router-60s-demo.gif',
    'workflow-skill-router-demo-poster.png',
  ];

  for (const asset of legacyAssets) {
    await expect(access(path.join(siteRoot, 'dist', 'assets', asset))).rejects.toThrow();
  }
});

test('Lighthouse gate audits V2 routes at 90/100/100/100', async () => {
  const source = await readFile(path.join(siteRoot, 'scripts', 'lighthouse-audit.mjs'), 'utf8');
  expect(source).toContain("accessibility: Number(process.env.LH_MIN_ACCESSIBILITY ?? 1)");
  expect(source).toContain("'best-practices': Number(process.env.LH_MIN_BEST_PRACTICES ?? 1)");
  expect(source).toContain('seo: Number(process.env.LH_MIN_SEO ?? 1)');

  for (const route of [
    '/guides/v2-routing/',
    '/reference/mcp-tools/',
    '/guides/install-plugin/',
    '/guides/install-skill/',
  ]) {
    expect(source).toContain(`path: '${route}'`);
  }
  expect(source).not.toContain('template-catalog');
});

for (const pageCase of pages) {
  test(`loads ${pageCase.path}`, async ({ page }) => {
    const response = await page.goto(pageCase.path);
    expect(response?.ok()).toBeTruthy();
    await expect(page.locator('body')).toContainText(pageCase.text);

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
}

test('explicit skill rejection keeps support inactive', async ({ page }) => {
  await page.goto('zh-tw/');
  await page.getByTestId('demo-preset-small-explicit-reject-support').click();
  await page.getByTestId('demo-consent-reject').click();
  await expect(page.getByTestId('demo-status')).toContainText('僅使用指定 SKILL');
  await expect(page.getByTestId('demo-audit-proposal')).toContainText('router-recommended');
  await expect(page.getByTestId('demo-active-support')).toHaveCount(0);
  await expect(page.getByTestId('demo-activation-event')).toHaveCount(0);
  await expect(page.getByTestId('demo-explicit-coverage')).toContainText('satisfied');
});

test('auto routing never renders support consent controls', async ({ page }) => {
  await page.goto('./');
  await expect(page.getByTestId('demo-consent-approve')).toBeHidden();
  await expect(page.getByTestId('demo-consent-reject')).toBeHidden();
});

test('personal profile demo exposes intended current-phase routing without consent', async ({ page }) => {
  await page.goto('./');
  await page.getByTestId('demo-preset-personal-skill-tree').click();
  await expect(page.locator('[data-demo-envelope]')).toHaveText('phased');
  await expect(page.locator('[data-demo-route]')).toContainText('skill:api-designer');
  await expect(page.locator('[data-demo-route]')).toContainText('skill:api-guidelines-skill');
  await expect(page.locator('[data-demo-route]')).toContainText('personal-profile');
  await expect(
    page.getByTestId('demo-audit-event').filter({ hasText: 'ROUTING_PROFILE_APPLIED' }),
  ).toHaveCount(1);
  await expect(page.getByTestId('demo-consent-approve')).toBeHidden();
  await page.getByTestId('demo-mcp-step').first().locator('summary').click();
  await expect(page.getByTestId('demo-mcp-step').first()).toContainText('intended-unverified');
});

test('managed Goal renders three independently routed work items', async ({ page }) => {
  await page.goto('./');
  await page.getByTestId('demo-preset-goal-work-graph').click();
  await expect(page.getByTestId('goal-work-item')).toHaveCount(3);
  await expect(page.getByTestId('work-item-envelope')).toHaveText(['single', 'phased', 'single']);
  await expect(page.getByTestId('demo-mcp-tool')).toHaveText(['plan_work', 'get_next_work', 'get_router_status']);
  await expect(page.getByTestId('demo-capability-unavailable')).toContainText('capability-unavailable');
  await expect(page.getByTestId('demo-runtime-profile')).toContainText('bundled-local-r0');
});

test('verified host fixture exposes the complete scheduler flow and fixture boundary', async ({ page }) => {
  await page.goto('./');
  await page.getByTestId('demo-preset-verified-host-flow').click();
  await expect(page.getByTestId('demo-mcp-tool')).toHaveText(['plan_work', 'get_next_work', 'get_router_status']);
  await expect(page.getByTestId('demo-mcp-result')).toHaveText(['OK', 'OK', 'OK']);
  await expect(page.getByTestId('demo-runtime-profile')).toContainText('verified-host-fixture');
  await expect(page.getByTestId('demo-evidence-class')).toContainText('fixture-trace');
  await expect(page.getByText('Requires verified host capabilities', { exact: true })).toBeVisible();
});

test('real evaluation reports its evidence and review gate without reference-driver claims', async ({ page }) => {
  await page.goto('./');
  await page.getByTestId('demo-preset-real-model-evaluation').click();
  await expect(page.getByTestId('demo-evaluation-status')).toContainText(/manual-required|review-required/);
  await expect(page.getByTestId('demo-evaluation-gate')).toContainText('review-required');
  await expect(page.getByTestId('demo-evaluation-class')).toContainText('behavior');
  await expect(page.locator('[data-router-demo]')).not.toContainText(/reference driver.*real model/i);
  await page.getByTestId('demo-mcp-step').first().locator('summary').click();
  await expect(page.getByTestId('demo-copy-json').first()).toBeVisible();
});

test('flight recorder is collapsed and keyboard navigable on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('./');
  await expect(page.getByTestId('demo-mcp-step').first()).not.toHaveAttribute('open', '');
  await page.getByTestId('demo-preset-small-auto').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId('demo-preset-small-explicit-reject-support')).toHaveAttribute('aria-selected', 'true');
  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(hasHorizontalOverflow).toBe(false);
});
