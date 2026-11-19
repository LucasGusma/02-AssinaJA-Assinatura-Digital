import { chromium } from '@playwright/test';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8765/');
  const login = page.getByRole('button', { name: /Entrar no AssinaJA/ });
  await login.waitFor();
  if (!(await login.isEnabled())) throw new Error('Login still disabled');
  if (await page.getByText('Integração em preparação').count()) throw new Error('Pending message still present');
  await page.screenshot({ path: 'frontend/test-results/login-connected.png', fullPage: true });
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('Live application: login enabled, no pending notice, no JavaScript errors.');
} finally {
  await browser.close();
}
