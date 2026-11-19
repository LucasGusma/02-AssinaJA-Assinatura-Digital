import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { Documents } from './Documents';

it('selects only the same provider and submits all documents to one recipient', async () => {
  const docs = [1, 2, 3].map(id => ({ id, title: `Documento ${id}`, provider_id: id === 3 ? 8 : 7,
    provider_name: 'Prestador teste', mv_user: 'ORIGEM', status: 'FECHADO', can_transfer: true }));
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => new Response(JSON.stringify(
    options?.method === 'POST' ? { transfers: [], message: 'OK' } : url.includes('/recipients')
      ? { users: [{ username: 'DESTINO', name: 'Pessoa destino' }] } : { documents: docs, next_cursor: null }
  ), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  vi.stubGlobal('fetch', fetcher);
  const user = userEvent.setup();
  render(<Documents canTransfer transfersEnabled sectorFilter={false} />);
  await user.click(await screen.findByLabelText('Selecionar documento 1'));
  expect(screen.getByLabelText('Selecionar documento 3')).toBeDisabled();
  await user.click(screen.getByLabelText('Selecionar documento 2'));
  await user.click(screen.getByRole('button', { name: 'Transferir selecionados (2)' }));
  await screen.findByRole('option', { name: 'Pessoa destino · DESTINO' });
  expect(screen.getAllByText('Documento 1').length).toBeGreaterThan(1);
  expect(screen.getAllByText('Documento 2').length).toBeGreaterThan(1);
  await user.selectOptions(screen.getByLabelText('Destinatário'), 'DESTINO');
  await user.type(screen.getByLabelText('Justificativa'), 'Mudança de responsável');
  await user.click(screen.getByRole('button', { name: 'Confirmar transferência' }));
  await waitFor(() => expect(fetcher.mock.calls.some(call => call[1]?.method === 'POST')).toBe(true));
  const call = fetcher.mock.calls.find(call => call[1]?.method === 'POST')!;
  expect(call[0]).toContain('/documents/transfers/batch');
  const body = JSON.parse(call[1]!.body as string);
  expect(body.recipient).toBe('DESTINO');
  expect(body.documents.map((item: { document_id: number }) => item.document_id)).toEqual([1, 2]);
});
