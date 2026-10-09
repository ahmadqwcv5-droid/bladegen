import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 300_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'BLADEGEN_API_PORT=8011 ../scripts/start_backend.sh',
      cwd: '.',
      url: 'http://127.0.0.1:8011/api/health',
      timeout: 30_000,
      reuseExistingServer: false,
    },
    {
      command: 'BLADEGEN_API_TARGET=http://127.0.0.1:8011 npm run dev -- --host 127.0.0.1 --port 5174',
      cwd: '.',
      url: 'http://127.0.0.1:5174',
      timeout: 30_000,
      reuseExistingServer: false,
    },
  ],
})
