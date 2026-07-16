import { expect, test } from '@playwright/test';

const pages = [
  { path: './', text: 'Workflow Skill Router' },
  { path: 'guides/quickstart/', text: 'V2 Quickstart' },
  { path: 'guides/install-plugin/', text: 'Install the Plugin + MCP runtime' },
  { path: 'concepts/runtime-capability-discovery/', text: 'Runtime Capability Discovery' },
  { path: 'reference/mcp-tools/', text: 'MCP Tools' },
  { path: 'examples/routing-gallery/', text: 'Routing Gallery' },
  { path: 'zh-tw/guides/quickstart/', text: 'V2 快速開始' },
  { path: 'zh-tw/guides/install-plugin/', text: '安裝 Plugin + MCP Runtime' },
  { path: 'zh-tw/concepts/runtime-capability-discovery/', text: 'Runtime Capability Discovery' },
  { path: 'zh-tw/reference/mcp-tools/', text: 'MCP Tools' },
  { path: 'zh-tw/examples/routing-gallery/', text: '路由案例 Gallery' },
];

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

test('routing gallery filters by domain and tag', async ({ page }) => {
  await page.goto('examples/routing-gallery/');

  await page.locator('[data-gallery-domain]').selectOption('frontend');
  await expect(page.locator('[data-gallery-card]:not([hidden])')).toHaveCount(2);
  const frontendDomains = await page.locator('[data-gallery-card]:not([hidden])').evaluateAll((cards) =>
    cards.map((card) => (card as HTMLElement).dataset.domain),
  );
  expect(frontendDomains).toEqual(['frontend', 'frontend']);

  await page.locator('[data-gallery-domain]').selectOption('');
  await page.getByRole('button', { name: 'anti-over-routing' }).click();
  await expect(page.locator('[data-gallery-card]:not([hidden])')).toHaveCount(2);
  await expect(page.locator('[data-gallery-card]:not([hidden])').first()).toContainText('Copy-edit boundary');

  await page.getByRole('button', { name: 'All tags' }).click();
  await expect(page.locator('[data-gallery-empty]')).toBeHidden();
});

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
