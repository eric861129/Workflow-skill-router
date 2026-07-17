import { expect, test } from '@playwright/test';

const pages = [
  { name: 'home', path: './' },
  { name: 'downloads', path: 'guides/downloads/' },
  { name: 'showcase', path: 'showcase/' },
  { name: 'quickstart', path: 'guides/quickstart/' },
  { name: 'mcp-tools', path: 'reference/mcp-tools/' },
];

const viewports = [
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
];

const screenshotOverrides: Record<string, { maxDiffPixelRatio: number }> = {
  'home-mobile.png': { maxDiffPixelRatio: 0.12 },
};

for (const pageCase of pages) {
  for (const viewport of viewports) {
    test(`${pageCase.name} ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(pageCase.path);
      await page.addStyleTag({
        content: `
          *,
          *::before,
          *::after {
            animation-duration: 0s !important;
            transition-duration: 0s !important;
          }

          img[src$=".gif"] {
            visibility: hidden !important;
          }
        `,
      });
      const screenshotName = `${pageCase.name}-${viewport.name}.png`;
      await expect(page).toHaveScreenshot(screenshotName, {
        fullPage: false,
        ...screenshotOverrides[screenshotName],
      });
    });
  }
}
