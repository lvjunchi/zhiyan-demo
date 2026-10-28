import { defineConfig, devices } from '@playwright/test'

// Keep API setup and assertions on the isolated test server.
process.env.ZHIYAN_E2E_API_BASE = 'http://127.0.0.1:8037'
export default defineConfig({
  outputDir: 'test-results/single-project',
 testDir: './e2e', fullyParallel: false, timeout: 30000, reporter: [['list']],
 use: { baseURL: 'http://127.0.0.1:5191', trace: 'retain-on-failure' },
 projects: [{ name: 'single-project-regression', use: { ...devices['Desktop Chrome'], channel: 'msedge' } }],
 webServer: [
  { command: "python -c \"import tempfile,uvicorn; from pathlib import Path; from app.main import create_app; from app.db import connect,run_migrations; from app import services,design_services; temporary=tempfile.TemporaryDirectory(prefix='zhiyan-single-e2e-'); database=Path(temporary.name)/'test.db'; connection=connect(database); run_migrations(connection); services.seed_catalog(connection); design_services.seed_history(connection); connection.close(); uvicorn.run(create_app(database),host='127.0.0.1',port=8037,log_level='warning')\"", env: { PYTHONPATH: '../backend' }, url: 'http://127.0.0.1:8037/api/health', reuseExistingServer: false, timeout: 60000 },
  { command: 'npm run dev -- --host 127.0.0.1 --port 5191 --strictPort', env: { ZHIYAN_API_TARGET: 'http://127.0.0.1:8037' }, url: 'http://127.0.0.1:5191', reuseExistingServer: false, timeout: 60000 }
 ]
})
