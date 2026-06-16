import { expect, test } from '@playwright/test';

const pages = [
  { name: 'home', path: './' },
  { name: 'downloads', path: 'guides/downloads/' },
  { name: 'gallery', path: 'examples/routing-gallery/' },
];

const viewports = [
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
];

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
      await expect(page).toHaveScreenshot(`${pageCase.name}-${viewport.name}.png`, {
        fullPage: false,
      });
    });
  }
}
