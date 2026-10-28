import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-r2', outputDir: 'test-results/r2', timeout: 45_000,
  fullyParallel: false, workers: 1, reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5198', trace: 'retain-on-failure' },
  projects: [{ name: 'r2-msedge', use: { ...devices['Desktop Chrome'], channel: 'msedge' } }],
  webServer: [
    { command: 'python ../scripts/run_preview_backend.py --port 8048', url: 'http://127.0.0.1:8048/api/health', reuseExistingServer: false, timeout: 60_000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5198 --strictPort', url: 'http://127.0.0.1:5198', env: { ZHIYAN_API_TARGET: 'http://127.0.0.1:8048' }, reuseExistingServer: false, timeout: 60_000 },
  ],
})
