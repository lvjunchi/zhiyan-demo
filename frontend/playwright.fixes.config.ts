import { defineConfig, devices } from '@playwright/test'
import { testPorts } from './playwright.ports'

const { apiPort, uiPort, apiURL, uiURL } = testPorts(8046, 5196)

export default defineConfig({
  testDir: './e2e-fixes', outputDir: 'test-results/fixes', timeout: 45_000,
  fullyParallel: false, workers: 1, reporter: [['list']],
  use: { baseURL: uiURL, trace: 'retain-on-failure' },
  projects: [{ name: 'fixes-msedge', use: { ...devices['Desktop Chrome'], channel: 'msedge' } }],
  webServer: [
    { command: `python ../backend/tests/run_regression_e2e.py --port ${apiPort}`, url: `${apiURL}/api/health`, reuseExistingServer: false, timeout: 60_000 },
    { command: `npm run dev -- --host 127.0.0.1 --port ${uiPort} --strictPort`, url: uiURL, env: { ZHIYAN_API_TARGET: apiURL }, reuseExistingServer: false, timeout: 60_000 },
  ],
})
