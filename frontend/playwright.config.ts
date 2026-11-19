import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:18765', channel: 'msedge', headless: true },
  webServer: {
    command: '..\\.venv\\Scripts\\python.exe ..\\server.py --port 18765',
    url: 'http://127.0.0.1:18765/api/health/live',
    reuseExistingServer: false,
    timeout: 30000,
    env: { ORACLE_PACKAGE_ROUTINE: '', ORACLE_FILE_ROUTINE: '', ORACLE_INTEGRATION_MODE: 'json', APP_ENVIRONMENT: 'test' },
  },
});
