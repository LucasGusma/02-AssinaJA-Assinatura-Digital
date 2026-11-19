import { test, expect } from '@playwright/test';

test('built React runs against the real FastAPI pending integration', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.getByText('Integração em preparação')).toBeVisible();
  await expect(page.getByRole('button', { name: /Entrar no AssinaJA/ })).toBeDisabled();
  await expect(page.locator('.hospital-logo img')).toHaveJSProperty('naturalWidth', 2481);
  await expect(page.getByRole('img', { name: 'AssinaJA', exact: true })).toBeVisible();
  await expect(page.getByRole('img', { name: 'BaleIA', exact: true })).toHaveJSProperty('naturalWidth', 193);
  const brand = await page.locator('.header-app-brand').boundingBox();
  expect(Math.abs(brand!.x + brand!.width / 2 - 720)).toBeLessThan(2);
  await page.screenshot({ path: 'test-results/login-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText('Integração em preparação')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/login-mobile.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('document UI and logout work with a simulated package response', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  let authenticated = true;
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url());
    let data: unknown = {};
    if (url.pathname.endsWith('/status')) data = { integration: 'configured', transfers_enabled: false, message: 'Integração de teste.' };
    else if (url.pathname.endsWith('/auth/session')) {
      if (!authenticated) return route.fulfill({ status: 401, json: { error: { message: 'Sessão expirada.' } } });
      data = { user: { username: 'TEST', name: 'Usuário de teste', is_master: true, can_transfer: false, all_sectors: true } };
    } else if (url.pathname.endsWith('/auth/logout')) { authenticated = false; return route.fulfill({ status: 204 }); }
    else if (url.pathname.endsWith('/sectors')) data = { sectors: [{ id: 1, name: 'Clínica de teste' }] };
    else if (url.pathname.endsWith('/documents')) data = { documents: [{ id: 20, title: url.searchParams.get('scope') === 'mine' ? 'Minha evolução de teste' : 'Evolução de teste', patient_name: 'Paciente fictício', attendance_id: 100, provider_name: 'Profissional fictício', sector_name: 'Clínica de teste', created: '2026-10-08T10:00:00-03:00', status: 'FECHADO', can_transfer: false }], next_cursor: null };
    else if (url.pathname.endsWith('/content')) data = { kind: 'editor', fields: [{ label: 'Observação', value: 'Conteúdo fictício para teste visual.', truncated: false }], partial: false };
    else if (url.pathname.endsWith('/users')) data = { users: [{ username: 'F1', name: 'Álvaro Teste', can_forward: false, profile: 'Teste' }] };
    else if (url.pathname.endsWith('/audit')) data = { events: [], next_cursor: null };
    await route.fulfill({ json: data });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.getByText('Paciente fictício')).toBeVisible();
  await page.screenshot({ path: 'test-results/dashboard-desktop.png', fullPage: true });
  await page.getByRole('button', { name: /Meus documentos/ }).click();
  await expect(page.getByRole('heading', { name: 'Meus documentos', exact: true })).toBeVisible();
  await expect(page.getByText('Minha evolução de teste', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/my-documents-desktop.png', fullPage: true });
  await page.getByRole('button', { name: /Visão geral/ }).click();
  await expect(page.getByText('Evolução de teste', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ver detalhes →' }).click();
  await page.getByRole('button', { name: 'Documento', exact: true }).click();
  await expect(page.getByText('Conteúdo fictício para teste visual.')).toBeVisible();
  await page.getByRole('button', { name: 'Fechar documento' }).click();
  await page.getByRole('button', { name: /Usuários ativos/ }).click();
  await page.getByRole('button', { name: 'Clínica de teste' }).click();
  await expect(page.getByText('Álvaro Teste')).toBeVisible();
  await page.getByRole('button', { name: 'Sair ↗' }).click();
  await expect(page.getByRole('button', { name: /Entrar no AssinaJA/ })).toBeVisible();
  await expect(page.getByText('Paciente fictício')).toHaveCount(0);
  expect(errors).toEqual([]);
});
