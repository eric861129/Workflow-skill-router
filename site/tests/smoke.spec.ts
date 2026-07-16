import { expect, test } from '@playwright/test';

const pages = [
  { path: './', text: 'Workflow Skill Router' },
  { path: 'guides/downloads/', text: 'Download packages' },
  { path: 'guides/quickstart/', text: 'Try in 30 seconds' },
  { path: 'examples/routing-gallery/', text: 'Routing Gallery' },
  { path: 'reference/validator/', text: 'Validation Toolchain' },
  { path: 'zh-tw/examples/routing-gallery/', text: '路由案例 Gallery' },
  { path: 'zh-tw/reference/validator/', text: '驗證工具鏈' },
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

test('managed Goal renders three independently routed work items', async ({ page }) => {
  await page.goto('./');
  await page.getByTestId('demo-preset-goal-work-graph').click();
  await expect(page.getByTestId('goal-work-item')).toHaveCount(3);
  await expect(page.getByTestId('work-item-envelope')).toHaveText(['single', 'phased', 'single']);
});
