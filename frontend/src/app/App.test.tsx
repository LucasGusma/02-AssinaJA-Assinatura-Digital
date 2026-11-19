import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { api } from '../shared/api';
import { Documents } from '../features/documents/Documents';
import { Permissions } from '../features/permissions/Permissions';
import { DocumentDetail } from '../features/documents/DocumentDetail';
import type { ClinicalDocument } from '../shared/types';

const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const document: ClinicalDocument = { id: 20, title: 'Documento de teste', patient_name: 'Paciente fictício', status: 'FECHADO', can_transfer: false };

describe('AssinaJA', () => {
  it('sends previous owner and preserves the transfer key when retrying a failed request', async () => {
    const sent: Record<string, string>[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        sent.push(JSON.parse(options.body as string));
        return sent.length === 1 ? response({ error: { message: 'Falha temporária' } }, 503)
          : response({ transfer_id: '123', message: 'Confirmada' });
      }
      return response({ users: [{ username: 'F012345', name: 'Destinatário teste' }] });
    }));
    const completed = vi.fn(); const user = userEvent.setup();
    render(<DocumentDetail document={{ ...document, can_transfer: true, mv_user: 'F000001' }} canTransfer onClose={() => {}} onTransferred={completed} />);
    await user.click(screen.getByRole('button', { name: 'Transferir' }));
    await screen.findByRole('option', { name: 'Destinatário teste · F012345' });
    await user.selectOptions(screen.getByLabelText('Destinatário'), 'F012345');
    await user.type(screen.getByLabelText('Justificativa'), 'Troca de responsável no plantão');
    await user.click(screen.getByRole('button', { name: 'Confirmar transferência' }));
    await screen.findByText('Falha temporária');
    expect(completed).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Confirmar transferência' }));
    await waitFor(() => expect(completed).toHaveBeenCalledOnce());
    expect(sent[0].expected_owner).toBe('F000001');
    expect(sent[0].recipient).toBe('F012345');
    expect(sent[1].idempotency_key).toBe(sent[0].idempotency_key);
  });
  it('lets ordinary users inspect permissions without modifying them', async () => {
    const fetcher = vi.fn(async (url: string) => url.endsWith('/sectors')
      ? response({ sectors: [{ id: 0, name: 'Sem setor' }] })
      : response({ users: [{ username: 'F012345', name: 'Pessoa teste', can_forward: true }] }));
    vi.stubGlobal('fetch', fetcher);
    const user = userEvent.setup(); render(<Permissions />);
    await user.click(await screen.findByRole('button', { name: 'Sem setor' }));
    const checkbox = await screen.findByRole('checkbox');
    expect(checkbox).toBeDisabled(); expect(checkbox).toBeChecked();
    await user.type(screen.getByLabelText('Buscar por nome ou F0'), 'f012345');
    expect(screen.getByText('Pessoa teste')).toBeInTheDocument();
    await user.click(checkbox);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it('opens global documents first and isolates the personal tab query', async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith('/status')) return response({ integration: 'configured', transfers_enabled: false, message: 'Pronto', capabilities: { sector_filter: false, audit: false } });
      if (url.endsWith('/auth/session')) return response({ user: { username: 'TEST', name: 'Usuário teste', is_master: false, all_sectors: true, can_transfer: false } });
      return response({ documents: [{ ...document, title: url.includes('scope=mine') ? 'Documento pessoal' : 'Documento geral' }], next_cursor: null });
    });
    vi.stubGlobal('fetch', fetcher); const user = userEvent.setup(); render(<App />);
    await screen.findByText('Documento geral');
    expect(fetcher.mock.calls.some(([url]) => url.includes('scope=all'))).toBe(true);
    await user.click(screen.getByRole('button', { name: /Meus documentos/ }));
    await screen.findByText('Documento pessoal');
    expect(screen.queryByText('Documento geral')).not.toBeInTheDocument();
    expect(fetcher.mock.calls.at(-1)?.[0]).toContain('scope=mine');
    await user.click(screen.getByRole('button', { name: /Visão geral/ }));
    await screen.findByText('Documento geral');
    expect(fetcher.mock.calls.at(-1)?.[0]).toContain('scope=all');
  });
  it('keeps directory and audit navigation available in the REF CURSOR integration', async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith('/status')) return response({ integration: 'configured', transfers_enabled: false, message: 'Pronto', capabilities: { sector_filter: false, audit: false } });
      if (url.endsWith('/auth/session')) return response({ user: { username: 'TEST', name: 'Usuário teste', is_master: false, all_sectors: false, can_transfer: false } });
      return response({ documents: [document], next_cursor: null });
    });
    vi.stubGlobal('fetch', fetcher); render(<App />);
    await screen.findByText('Paciente fictício');
    expect(screen.queryByLabelText('Buscar setor')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Auditoria/ })).toBeInTheDocument();
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/sectors'))).toBe(false);
  });
  it('shows the pending integration without offering fake authentication', async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ integration: 'pending', transfers_enabled: false, message: 'Aguardando a package Oracle.' }));
    vi.stubGlobal('fetch', fetcher);
    render(<App />);
    expect(await screen.findByText('Integração em preparação')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Entrar no AssinaJA/ })).toBeDisabled();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('advances, returns, keeps the current page on failure and resets filters', async () => {
    let fail = false;
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith('/sectors')) return response({ sectors: [] });
      if (url.endsWith('/documents/types')) return response({ types: [{ id: 7, name: 'Tipo teste' }] });
      if (url.includes('/documents/summary')) return response({ total: 1234, start: '2026-07-15', end: '2026-10-15' });
      if (fail) return response({ error: { code: 'UNAVAILABLE', message: 'Falha simulada' } }, 503);
      const next = url.includes('before=20');
      return response({ documents: [{ ...document, id: next ? 10 : 20 }], next_cursor: next ? null : 20 });
    });
    vi.stubGlobal('fetch', fetcher);
    const user = userEvent.setup(); render(<Documents canTransfer={false} />);
    await screen.findByText('Documento de teste');
    expect(await screen.findByText('1234')).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Tipo de documento'), '7');
    await user.click(screen.getByRole('button', { name: 'Consultar documentos' }));
    await waitFor(() => expect(fetcher.mock.calls.some(call => call[0].includes('document_type=7'))).toBe(true));
    expect(screen.getByRole('button', { name: /Anterior/ })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Próxima/ }));
    await screen.findByText('Página 2');
    expect(screen.getByRole('button', { name: /Próxima/ })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Anterior/ }));
    await screen.findByText('Página 1');
    fail = true; await user.click(screen.getByRole('button', { name: /Próxima/ }));
    await screen.findByText('Falha simulada');
    expect(screen.getByText('Página 1')).toBeInTheDocument();
    fail = false; await user.click(screen.getByRole('button', { name: /Próxima/ }));
    await screen.findByText('Página 2');
    await user.click(screen.getByRole('button', { name: 'Consultar documentos' }));
    await screen.findByText('Página 1');
    expect(fetcher.mock.calls.at(-1)?.[0]).not.toContain('before=');
  });

  it('filters users ignoring accents and does not apply a failed permission update', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
      if (options?.method === 'PUT') return response({ error: { message: 'Alteração recusada' } }, 403);
      if (url.endsWith('/sectors')) return response({ sectors: [{ id: 1, name: 'Clínica' }] });
      return response({ users: [{ username: 'F1', name: 'Álvaro', can_forward: false }, { username: 'F2', name: 'Beatriz', can_forward: false }] });
    }));
    const user = userEvent.setup(); render(<Permissions canManage />);
    await user.click(await screen.findByRole('button', { name: 'Clínica' }));
    await screen.findByText('Álvaro');
    await user.type(screen.getByLabelText('Buscar por nome ou F0'), 'alvaro');
    expect(screen.queryByText('Beatriz')).not.toBeInTheDocument();
    const checkbox = screen.getByRole('checkbox', { name: 'Permitir transferência para Álvaro' });
    await user.click(checkbox);
    await screen.findByText('Alteração recusada');
    expect(checkbox).not.toBeChecked();
  });

  it('renders clinical document details without the content tab', async () => {
    render(<DocumentDetail document={document} canTransfer={false} onClose={() => {}} onTransferred={() => {}} />);
    expect(screen.getByText('Paciente fictício')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Documento' })).not.toBeInTheDocument();
  });

  it('clears the workspace when the session expires', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.endsWith('/status')) return response({ integration: 'configured', transfers_enabled: false, message: 'Pronto' });
      if (url.endsWith('/auth/session')) return response({ user: { username: 'F1', name: 'Usuário teste', is_master: false, all_sectors: true, can_transfer: false } });
      if (url.endsWith('/sectors')) return response({ sectors: [] });
      if (url.endsWith('/documents/types')) return response({ types: [{ id: 7, name: 'Tipo teste' }] });
      if (url.includes('/documents/summary')) return response({ total: 1234, start: '2026-07-15', end: '2026-10-15' });
      return response({ documents: [document], next_cursor: null });
    }));
    render(<App />); await screen.findByText('Paciente fictício');
    window.dispatchEvent(new Event('session-expired'));
    await waitFor(() => expect(screen.queryByText('Paciente fictício')).not.toBeInTheDocument());
    expect(await screen.findByRole('button', { name: /Entrar no AssinaJA/ })).toBeInTheDocument();
  });

  it('sends JSON and the CSRF protection header without storing session tokens', async () => {
    const storeToken = vi.fn(); vi.stubGlobal('localStorage', { setItem: storeToken });
    const fetcher = vi.fn().mockResolvedValue(response({ user: {} })); vi.stubGlobal('fetch', fetcher);
    await api('auth/login', { method: 'POST', body: JSON.stringify({ username: 'test', password: 'test' }) });
    const options = fetcher.mock.calls[0][1];
    expect(options.headers.get('X-CSRF-Protection')).toBe('1');
    expect(options.credentials).toBe('same-origin');
    expect(storeToken).not.toHaveBeenCalled();
  });
});
