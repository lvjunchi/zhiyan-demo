import { defineConfig, devices } from '@playwright/test'
import { testPorts } from './playwright.ports'

const { apiPort, uiPort, apiURL, uiURL } = testPorts(8049, 5199)

export default defineConfig({
  outputDir: 'test-results/cockpit',
  testDir: './e2e-cockpit',
  timeout: 45_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: uiURL, trace: 'retain-on-failure' },
  projects: [{ name: 'cockpit-msedge', use: { ...devices['Desktop Chrome'], channel: 'msedge' } }],
  webServer: [
    { command: `python ../scripts/run_preview_backend.py --port ${apiPort}`, url: `${apiURL}/api/health`, reuseExistingServer: false, timeout: 60_000 },
    { command: `npm run dev -- --host 127.0.0.1 --port ${uiPort} --strictPort`, url: uiURL, env: { ZHIYAN_API_TARGET: apiURL }, reuseExistingServer: false, timeout: 60_000 },
  ],
})
