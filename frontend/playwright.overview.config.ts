import { defineConfig, devices } from '@playwright/test'
import { testPorts } from './playwright.ports'
const { apiPort, uiPort, apiURL, uiURL } = testPorts(8075, 5225)

export default defineConfig({
  testDir: './e2e-overview', outputDir: 'test-results/overview', timeout: 45_000,
  fullyParallel: false, workers: 1, reporter: [['list']],
  use: { baseURL: uiURL, trace: 'retain-on-failure' },
  projects: [{ name: 'overview-msedge', use: { ...devices['Desktop Chrome'], channel: 'msedge' } }],
  webServer: [
    { command: `python ../scripts/run_overview_preview.py --port ${apiPort}`, url: `${apiURL}/api/health`, reuseExistingServer: false, timeout: 60_000 },
    { command: `npm run dev -- --host 127.0.0.1 --port ${uiPort} --strictPort`, url: uiURL, env: { ZHIYAN_API_TARGET: apiURL }, reuseExistingServer: false, timeout: 60_000 },
  ],
})
