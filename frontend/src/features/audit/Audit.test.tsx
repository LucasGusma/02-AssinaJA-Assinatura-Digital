import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { Audit } from './Audit';

it('searches the full history, preserves filters when paging and exposes event details', async () => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify({
    events: [{ id: url.includes('before=') ? 9 : 10, created: '2026-10-15T12:00:00Z',
      actor: 'Operador (F001)', action: 'TRANSFERENCIA', detail: 'Justificativa completa',
      source_user: 'F002', source_name: 'Origem', target_user: 'F003', target_name: 'Destino',
      document_id: 123, request_id: 'rastreio-teste' }], next_cursor: url.includes('before=') ? null : 10,
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  vi.stubGlobal('fetch', fetcher);
  const user = userEvent.setup(); render(<Audit />);
  await screen.findByText('Operador (F001)');
  await user.type(screen.getByLabelText('Pessoa: nome ou usuário'), 'F003');
  await user.selectOptions(screen.getByLabelText('Tipo de movimentação'), 'TRANSFERENCIA');
  await user.click(screen.getByRole('button', { name: 'Pesquisar movimentações' }));
  await waitFor(() => expect(fetcher.mock.calls.at(-1)?.[0]).toContain('search=F003'));
  await user.click(screen.getByRole('button', { name: /Próxima/ }));
  await screen.findByText('Página 2');
  expect(fetcher.mock.calls.at(-1)?.[0]).toContain('action=TRANSFERENCIA');
  expect(fetcher.mock.calls.at(-1)?.[0]).toContain('before=10');
  await user.click(screen.getByRole('button', { name: /Ver movimentação/ }));
  expect(screen.getByText('Justificativa completa')).toBeInTheDocument();
  expect(screen.getByText('rastreio-teste')).toBeInTheDocument();
});
