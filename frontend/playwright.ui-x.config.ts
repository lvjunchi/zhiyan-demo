import { defineConfig } from '@playwright/test'
import cockpit from './playwright.cockpit.config'
import review from './playwright.review.config'
import workspace from './playwright.r2.config'

// Keep this review's temporary databases, servers and artifacts separate from
// other agents running the standard regression profiles at the same time.
const suite = process.env.ZHIYAN_UIX_SUITE ?? 'cockpit'
if (!['cockpit', 'review', 'workspace'].includes(suite)) throw new Error('Unknown UI-X browser suite')
const selected = suite === 'review' ? review : suite === 'workspace' ? workspace : cockpit
const backendPort = suite === 'review' ? 8062 : suite === 'workspace' ? 8063 : 8061
const frontendPort = suite === 'review' ? 5212 : suite === 'workspace' ? 5213 : 5211

export default defineConfig(selected, {
  outputDir: `test-results/ui-x-${suite}`,
  use: { ...selected.use, baseURL: `http://127.0.0.1:${frontendPort}` },
  webServer: [
    { command: `python ../scripts/run_preview_backend.py --port ${backendPort}`, url: `http://127.0.0.1:${backendPort}/api/health`, reuseExistingServer: false, timeout: 60_000 },
    { command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`, url: `http://127.0.0.1:${frontendPort}`, env: { ZHIYAN_API_TARGET: `http://127.0.0.1:${backendPort}` }, reuseExistingServer: false, timeout: 60_000 },
  ],
})
