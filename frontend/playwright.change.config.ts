import { defineConfig, devices } from '@playwright/test'
import { testPorts } from './playwright.ports'

const { apiPort, uiPort, apiURL, uiURL } = testPorts(8047, 5197)

export default defineConfig({
  testDir: './e2e-change', outputDir: 'test-results/change', timeout: 45000, fullyParallel: false, reporter: [['list']],
  use: { baseURL: uiURL, trace: 'retain-on-failure' },
  projects: [{ name: 'change-msedge', use: { ...devices['Desktop Chrome'], channel: 'msedge' } }],
  webServer: [
    { command: `python ../scripts/run_preview_backend.py --port ${apiPort}`, url: `${apiURL}/api/health`, reuseExistingServer: false, timeout: 60000 },
    { command: `npm run dev -- --host 127.0.0.1 --port ${uiPort} --strictPort`, url: uiURL, env: { ZHIYAN_API_TARGET: apiURL }, reuseExistingServer: false, timeout: 60000 },
  ],
})
