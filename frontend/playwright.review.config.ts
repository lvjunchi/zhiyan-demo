import { defineConfig, devices } from '@playwright/test'

// Populated walk-through uses the read-only source backup preview, never demo.db.
export default defineConfig({
  outputDir: 'test-results/review',
  testDir: './e2e-demo', timeout: 60000, fullyParallel: false, reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5200', trace: 'retain-on-failure' },
  projects: [{ name: 'review-msedge', use: { ...devices['Desktop Chrome'], channel: 'msedge' } }],
  webServer: [
    { command: 'python ../scripts/run_preview_backend.py --port 8050', url: 'http://127.0.0.1:8050/api/health', reuseExistingServer: false, timeout: 60000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5200 --strictPort', url: 'http://127.0.0.1:5200', env: { ZHIYAN_API_TARGET: 'http://127.0.0.1:8050' }, reuseExistingServer: false, timeout: 60000 },
  ],
})
