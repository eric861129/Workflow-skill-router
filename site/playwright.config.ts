import { defineConfig, devices } from '@playwright/test';

const baseURL = 'http://127.0.0.1:4321/Workflow-skill-router/';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  snapshotPathTemplate: '{testDir}/__screenshots__/{arg}{ext}',
  timeout: 30_000,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      // CI runners can render fonts and anti-aliased edges slightly differently.
      // Keep enough tolerance for that noise while still catching major layout shifts.
      maxDiffPixelRatio: 0.08,
      threshold: 0.35,
    },
  },
  use: {
    baseURL,
    trace: 'on-first-retry',
    reducedMotion: 'reduce',
  },
  webServer: {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4321',
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'chromium-smoke',
      testMatch: /smoke\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 900 },
      },
    },
    {
      name: 'chromium-visual',
      testMatch: /visual\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});
