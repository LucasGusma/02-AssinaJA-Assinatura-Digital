import { useEffect, useRef, useState } from 'react';
import { api, dateTime, errorMessage, isAbort, normalize } from '../../shared/api';
import { ErrorNotice, Modal, Pagination } from '../../shared/components';
import type { ClinicalDocument, DocumentPage, Sector } from '../../shared/types';
import { DocumentDetail, TransferForm } from './DocumentDetail';

function localDate(value: Date) { return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`; }
function initialFilters() { const today = new Date(); const start = new Date(today); start.setDate(1); start.setMonth(start.getMonth() - 3); const last = new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate(); start.setDate(today.getDate() === new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate() ? last : Math.min(today.getDate(), last)); return { start: localDate(start), end: localDate(today), sector: '', provider: '', documentType: '' }; }

export function Documents({ canTransfer, sectorFilter = true, scope = 'all', transfersEnabled = false }: { transfersEnabled?: boolean; canTransfer: boolean; sectorFilter?: boolean; scope?: 'all' | 'mine' }) {
  const [filters, setFilters] = useState(initialFilters);
  const [query, setQuery] = useState(initialFilters);
  const [types, setTypes] = useState<{ id: number; name: string }[]>([]);
  const [summary, setSummary] = useState<{ total: number; start: string; end: string } | null>(null);
  const [summaryError, setSummaryError] = useState('');
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [sectorSearch, setSectorSearch] = useState('');
  const [data, setData] = useState<DocumentPage>({ documents: [], next_cursor: null });
  const [page, setPage] = useState(0);
  const [cursors, setCursors] = useState<(number | null)[]>([null]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [directoryError, setDirectoryError] = useState('');
  const [selected, setSelected] = useState<ClinicalDocument | null>(null);
  const [checked, setChecked] = useState<ClinicalDocument[]>([]);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [notice, setNotice] = useState('');
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  async function fetchPage(target: number, cursor: number | null, nextQuery = query) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError('');
    const active = new AbortController(); controller.current = active;
    try {
      const params = new URLSearchParams({ start: nextQuery.start, end: nextQuery.end, scope });
      if (nextQuery.sector) params.set('sector', nextQuery.sector);
      if (nextQuery.documentType) params.set('document_type', nextQuery.documentType);
      if (nextQuery.provider.trim()) params.set('provider', nextQuery.provider.trim());
      if (cursor !== null) params.set('before', String(cursor));
      setSummaryError('');
      void api<{ total: number; start: string; end: string }>(`documents/summary?scope=${scope}`, { signal: active.signal }).then(setSummary).catch(error => { if (!isAbort(error)) { setSummary(null); setSummaryError(errorMessage(error)); } });
      const result = await api<DocumentPage>(`documents?${params}`, { signal: active.signal });
      if (active.signal.aborted) return;
      setLastUpdated(new Date().toISOString()); setChecked([]); setData(result); setPage(target); setQuery(nextQuery);
      setCursors(current => [...current.slice(0, target), cursor]);
    } catch (error) { if (!isAbort(error)) setError(errorMessage(error)); }
    finally { if (controller.current === active) { inFlight.current = false; if (!active.signal.aborted) setBusy(false); } }
  }
  useEffect(() => {
    const directory = new AbortController();
    api<{ types: { id: number; name: string }[] }>('documents/types', { signal: directory.signal }).then(result => setTypes(result.types ?? [])).catch(error => { if (!isAbort(error)) setDirectoryError(errorMessage(error)); });
    if (sectorFilter) api<{ sectors: Sector[] }>('sectors', { signal: directory.signal }).then(result => setSectors(result.sectors)).catch(error => { if (!isAbort(error)) setDirectoryError(errorMessage(error)); });
    void fetchPage(0, null, initialFilters());
    return () => { directory.abort(); controller.current?.abort(); inFlight.current = false; };
    // Query changes are explicit so failed pagination preserves the current page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const refreshRef = useRef(() => {});
  refreshRef.current = () => {
    // Preserve reading, selection, pagination and filters that are being edited.
    if (document.visibilityState === 'hidden' || inFlight.current || selected || batchOpen || batchBusy || checked.length || page !== 0 || JSON.stringify(filters) !== JSON.stringify(query)) return;
    void fetchPage(0, null, query);
  };
  useEffect(() => {
    const timer = window.setInterval(() => refreshRef.current(), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  return <><section className="stats"><article><span>Total de documentos de 3 meses</span><strong>{summary?.total ?? "—"}</strong><small>Pendentes de assinatura · {scope === "mine" ? "Meu usuário" : "Todos os usuários"}</small><p className="muted fine-print">{summary?.start} a {summary?.end} · Total independente dos filtros abaixo</p><ErrorNotice message={summaryError} /></article><article><span>Transferências</span><strong>{canTransfer ? 'Habilitadas' : transfersEnabled ? 'Sem permissão' : 'Desabilitadas'}</strong><small>{canTransfer ? 'Conforme suas permissões' : transfersEnabled ? 'Solicite liberação ao master ADMIN' : 'Integração de transferência desativada'}</small></article><article><span>Assinatura</span><strong>MV</strong><small>Realizada no sistema de origem</small></article></section>
    <section className="panel"><div className="panel-heading"><h2>{scope === 'mine' ? 'Minhas pendências de assinatura' : 'Pendências de assinatura'}</h2><p>{scope === 'mine' ? 'Documentos do seu usuário, fechados e aguardando assinatura.' : 'Documentos de todos os usuários, fechados e aguardando assinatura.'} Documentos que não exigem assinatura não aparecem.</p></div>
      <form className={`filters provider-filters ${sectorFilter ? "" : "filters-without-sector"}`} onSubmit={event => { event.preventDefault(); setNotice(''); void fetchPage(0, null, filters); }}>
        <div><label htmlFor="start">Data inicial</label><input type="date" id="start" required value={filters.start} disabled={busy} onChange={event => setFilters({ ...filters, start: event.target.value })} /></div>
        <div><label htmlFor="end">Data final</label><input type="date" id="end" required value={filters.end} min={filters.start} disabled={busy} onChange={event => setFilters({ ...filters, end: event.target.value })} /></div>
        <div><label htmlFor="provider-search">Nome do prestador</label><input type="search" id="provider-search" placeholder="Digite o nome ou parte dele" maxLength={128} value={filters.provider} disabled={busy} onChange={event => setFilters({ ...filters, provider: event.target.value })} /></div>
        <div><label htmlFor="document-type">Tipo de documento</label><select id="document-type" value={filters.documentType} disabled={busy} onChange={event => setFilters({ ...filters, documentType: event.target.value })}><option value="">Todos os tipos</option>{types.map(type => <option key={type.id} value={type.id}>{type.name} · {type.id}</option>)}</select></div>{sectorFilter && <div><label htmlFor="sector-search">Buscar setor</label><input id="sector-search" placeholder="Nome do setor" value={sectorSearch} onChange={event => setSectorSearch(event.target.value)} /><label htmlFor="sector" className="sr-only">Setor</label><select id="sector" value={filters.sector} disabled={busy} onChange={event => setFilters({ ...filters, sector: event.target.value })}><option value="">Todos os setores autorizados</option>{sectors.filter(sector => String(sector.id) === filters.sector || normalize(sector.name).includes(normalize(sectorSearch))).map(sector => <option key={sector.id} value={sector.id}>{sector.name}</option>)}</select></div>}
        <button className="primary" disabled={busy}>{busy ? 'Consultando…' : 'Consultar documentos'}</button>
      </form><div className="panel-body"><p className="muted" role="status">Atualização automática: 60 segundos na primeira página, com a aba visível. Pausa durante leitura, seleção ou edição dos filtros. {lastUpdated && `Última consulta: ${dateTime(lastUpdated)}`}</p><p className="muted">Até 3 meses por consulta · 50 documentos por página.</p>{canTransfer && <><p className="muted">Selecione documentos do mesmo prestador nesta página. Ao consultar ou mudar de página, a seleção será limpa.</p><button type="button" className="primary" disabled={busy || !checked.length} onClick={() => setBatchOpen(true)}>Transferir selecionados ({checked.length})</button>{checked.length > 0 && <button type="button" className="subtle" onClick={() => setChecked([])}>Limpar seleção</button>}</>}<ErrorNotice message={directoryError} /><ErrorNotice message={error} />{notice && <p className="notice" role="status">{notice}</p>}</div>
      <div className="table-scroll document-table" aria-busy={busy}><table><thead><tr>{canTransfer && <th>Selecionar</th>}<th>Documento</th><th>Paciente / atendimento</th><th>Prestador</th>{sectorFilter && <th>Setor</th>}<th>Criado em</th><th><span className="sr-only">Ações</span></th></tr></thead><tbody>{data.documents.map(document => <tr key={document.id}>{canTransfer && <td><input type="checkbox" aria-label={`Selecionar documento ${document.id}`} checked={checked.some(item => item.id === document.id)} disabled={busy || !document.can_transfer || !document.provider_id || !document.mv_user || (checked.length > 0 && checked[0].provider_id !== document.provider_id)} onChange={event => setChecked(current => event.target.checked ? [...current, document] : current.filter(item => item.id !== document.id))} /></td>}<td><b>{document.title}</b><small>{document.id} · {document.status}</small></td><td>{document.patient_name ?? 'Não informado'}<small>Atendimento {document.attendance_id ?? '—'}</small></td><td>{document.provider_name ?? 'Não informado'}<small>{document.mv_user}</small></td>{sectorFilter && <td>{document.sector_name ?? 'Não informado'}</td>}<td>{dateTime(document.created)}</td><td><button className="row-action" onClick={() => setSelected(document)}>Ver detalhes →</button></td></tr>)}</tbody></table>
        {!data.documents.length && <p className="empty" role="status">{busy ? 'Consultando documentos…' : 'Nenhum documento carregado para esta seleção.'}</p>}</div>
      <div className="table-footer"><span>{data.documents.length} documento(s) nesta página · Fonte MV</span><Pagination page={page} busy={busy} previous={page > 0 ? () => void fetchPage(page - 1, cursors[page - 1]) : undefined} next={data.next_cursor !== null ? () => void fetchPage(page + 1, data.next_cursor) : undefined} /></div>
    </section>{batchOpen && <Modal title="Transferir documentos selecionados" busy={batchBusy} onClose={() => { setBatchOpen(false); setChecked([]); void fetchPage(0, null); }}><TransferForm onBusyChange={setBatchBusy} documents={checked} onTransferred={() => { setBatchOpen(false); setChecked([]); setNotice('Todos os documentos selecionados foram transferidos.'); void fetchPage(0, null); }} /></Modal>}{selected && <DocumentDetail key={selected.id} document={selected} canTransfer={canTransfer} onClose={() => setSelected(null)} onTransferred={() => { setSelected(null); setNotice('Transferência confirmada pelo Oracle.'); void fetchPage(0, null); }} />}</>;
}
