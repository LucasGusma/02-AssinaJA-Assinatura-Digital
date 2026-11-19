import { useEffect, useRef, useState } from 'react';
import { api, dateTime, errorMessage, isAbort } from '../../shared/api';
import { ErrorNotice, Modal, Pagination } from '../../shared/components';
import type { AuditEvent, AuditPage } from '../../shared/types';

const emptyFilters = { search: '', action: '', document: '' };
const actionName = (action: string) => ({ TRANSFERENCIA: 'Transferência', PERMISSAO: 'Permissão' }[action] ?? action);
export function Audit() {
  const [data, setData] = useState<AuditPage>({ events: [], next_cursor: null });
  const [filters, setFilters] = useState(emptyFilters);
  const [query, setQuery] = useState(emptyFilters);
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const [page, setPage] = useState(0);
  const [cursors, setCursors] = useState<(number | null)[]>([null]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  async function load(target: number, before: number | null, nextQuery = query) {
    controller.current?.abort(); const active = new AbortController(); controller.current = active;
    setBusy(true); setError('');
    const params = new URLSearchParams();
    if (before) params.set('before', String(before));
    if (nextQuery.search.trim()) params.set('search', nextQuery.search.trim());
    if (nextQuery.action) params.set('action', nextQuery.action);
    if (nextQuery.document) params.set('document_id', nextQuery.document);
    try {
      const result = await api<AuditPage>(`audit?${params}`, { signal: active.signal });
      if (!active.signal.aborted) { setData(result); setQuery(nextQuery); setPage(target); setCursors(current => [...current.slice(0, target), before]); }
    } catch (error) { if (!isAbort(error)) setError(errorMessage(error)); }
    finally { if (!active.signal.aborted) setBusy(false); }
  }
  useEffect(() => { void load(0, null); return () => controller.current?.abort(); }, []);
  const transfers = data.events.filter(event => event.action === 'TRANSFERENCIA').length;
  const permissions = data.events.filter(event => event.action === 'PERMISSAO').length;
  return <>
    <section className="stats" aria-label="Resumo da página de auditoria">
      <article><span>Movimentações nesta página</span><strong>{data.events.length}</strong><small>Até 50 registros por página</small></article>
      <article><span>Transferências nesta página</span><strong>{transfers}</strong><small>Trocas de responsável registradas</small></article>
      <article><span>Permissões nesta página</span><strong>{permissions}</strong><small>Concessões e retiradas de acesso</small></article>
    </section>
    <section className="panel"><div className="panel-heading"><h2>Histórico de movimentações</h2><p>Registros do AssinaJA desde a ativação da auditoria. A busca considera quem realizou a ação, o responsável anterior e o destinatário.</p></div>
      <form className="audit-filters" onSubmit={event => { event.preventDefault(); void load(0, null, filters); }}>
        <div><label htmlFor="audit-search">Pessoa: nome ou usuário</label><input id="audit-search" type="search" placeholder="Digite um nome ou F0" maxLength={128} value={filters.search} disabled={busy} onChange={event => setFilters({ ...filters, search: event.target.value })} /></div>
        <div><label htmlFor="audit-action">Tipo de movimentação</label><select id="audit-action" value={filters.action} disabled={busy} onChange={event => setFilters({ ...filters, action: event.target.value })}><option value="">Todas as ações</option><option value="TRANSFERENCIA">Transferência</option><option value="PERMISSAO">Permissão</option></select></div>
        <div><label htmlFor="audit-document">Código do documento</label><input id="audit-document" type="number" min="1" step="1" value={filters.document} disabled={busy} onChange={event => setFilters({ ...filters, document: event.target.value })} /></div>
        <button className="primary" disabled={busy}>{busy ? 'Pesquisando…' : 'Pesquisar movimentações'}</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => { setFilters(emptyFilters); void load(0, null, emptyFilters); }}>Limpar</button>
      </form>
      <div className="panel-body"><p className="muted">Mais recentes primeiro · Pesquisa em todo o histórico · Nomes e códigos preservados no momento do registro.</p><ErrorNotice message={error} />{error && <button className="secondary" onClick={() => void load(page, cursors[page])}>Tentar novamente</button>}</div>
      <div className="table-scroll document-table" aria-busy={busy}><table><thead><tr><th>Evento / data e hora</th><th>Ação</th><th>Realizado por</th><th>Responsável anterior</th><th>Destinatário / usuário afetado</th><th>Documento</th><th>Detalhes</th></tr></thead><tbody>{data.events.map(event => <tr key={event.id}>
        <td><b>#{event.id}</b><small>{dateTime(event.created)}</small></td><td><span className="badge">{actionName(event.action)}</span></td><td>{event.actor}</td>
        <td>{event.source_name ?? event.source_user ?? 'Não se aplica'}{event.source_name && <small>{event.source_user}</small>}</td>
        <td>{event.target_name ?? event.target_user ?? 'Não se aplica'}{event.target_name && <small>{event.target_user}</small>}</td>
        <td>{event.document_id ?? 'Não se aplica'}</td><td><button className="row-action" onClick={() => setSelected(event)}>Ver movimentação →</button></td>
      </tr>)}</tbody></table>{!data.events.length && <p className="empty" role="status">{busy ? 'Consultando…' : 'Nenhuma movimentação encontrada.'}</p>}</div>
      <div className="table-footer"><span>{data.events.length} registro(s) nesta página</span><Pagination page={page} busy={busy} previous={page > 0 ? () => void load(page - 1, cursors[page - 1]) : undefined} next={data.next_cursor ? () => void load(page + 1, data.next_cursor) : undefined} /></div>
    </section>
    {selected && <Modal title={`Movimentação #${selected.id}`} onClose={() => setSelected(null)}><dl className="detail-grid">{[
      ['Ação', actionName(selected.action)], ['Data e hora', dateTime(selected.created)], ['Realizado por', selected.actor],
      ['Documento', selected.document_id], ['Responsável anterior', [selected.source_name, selected.source_user].filter(Boolean).join(' · ') || null],
      ['Destinatário / usuário afetado', [selected.target_name, selected.target_user].filter(Boolean).join(' · ') || null], ['Identificador da requisição', selected.request_id],
    ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? 'Não registrado / não se aplica'}</dd></div>)}</dl><h3>Justificativa / alteração registrada</h3><p className="audit-detail">{selected.detail}</p></Modal>}
  </>;
}
