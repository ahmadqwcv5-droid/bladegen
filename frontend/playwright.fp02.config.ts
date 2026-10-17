import { defineConfig, devices } from '@playwright/test'

const evidenceRunId = process.env.FP02_EVIDENCE_RUN_ID ?? 'unlabelled-local-run'
const evidenceRoot = process.env.FP02_EVIDENCE_ROOT ?? `../qualification/fp02/evidence/browser/${evidenceRunId}`
const externalServer = process.env.L1A_EXTERNAL_SERVER === '1'
const uiPort = process.env.L1A_UI_PORT ?? '5174'

export default defineConfig({
  testDir: './e2e',
  timeout: 3_600_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: `${evidenceRoot}/html-report` }],
        ['json', { outputFile: `${evidenceRoot}/consolidated_results.json` }],
  ],
  use: {
    baseURL: `http://127.0.0.1:${uiPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: externalServer ? [] : [
    {
      command: 'BLADEGEN_API_PORT=8011 BLADEGEN_BUILD_TIMEOUT=900 ../scripts/start_backend.sh',
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
