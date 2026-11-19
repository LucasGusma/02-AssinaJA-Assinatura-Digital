import { useEffect, useState } from 'react';
import { api, dateTime, errorMessage, isAbort } from '../../shared/api';
import { ErrorNotice, Modal } from '../../shared/components';
import type { ClinicalDocument, Member } from '../../shared/types';

export function DocumentDetail({ document, canTransfer, onClose, onTransferred }: { document: ClinicalDocument; canTransfer: boolean; onClose: () => void; onTransferred: () => void }) {
  const [tab, setTab] = useState<'details' | 'transfer'>('details');
  const showTransfer = canTransfer && document.can_transfer;
  return <Modal title={document.title} onClose={onClose}>
    {showTransfer && <div className="tabs" aria-label="Seções do documento">
      <button className={tab === 'details' ? 'selected' : ''} onClick={() => setTab('details')}>Detalhes</button>
      <button className={tab === 'transfer' ? 'selected' : ''} onClick={() => setTab('transfer')}>Transferir</button>
    </div>}
    {tab === 'details' && <><span className="badge">{document.status}</span><dl className="detail-grid">{[
      ['Documento', document.id], ['Paciente', document.patient_name], ['Atendimento', document.attendance_id],
      ['Prestador', document.provider_name], ['Usuário MV', document.mv_user], ['Setor', document.sector_name], ['Criado em', dateTime(document.created)],
      ['Alta do atendimento', document.discharge_at || 'Alta não registrada'],
    ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? 'Não informado'}</dd></div>)}</dl><p className="notice">A assinatura é realizada exclusivamente no MV.</p>{document.transfer_block_reason && <p className="notice">{document.transfer_block_reason}</p>}</>}
    {tab === 'transfer' && showTransfer && <TransferForm documents={[document]} onTransferred={onTransferred} />}
  </Modal>;
}

export function TransferForm({ documents, onTransferred, onBusyChange }: { documents: ClinicalDocument[]; onTransferred: () => void; onBusyChange?: (busy: boolean) => void }) {
  const documentId = documents[0].id;
  const [search, setSearch] = useState('');
  const [members, setMembers] = useState<Member[]>([]);
  const [recipient, setRecipient] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [keys] = useState(() => documents.map(() => crypto.randomUUID()));
  const [submitted, setSubmitted] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setRecipient(''); setMembers([]);
    const timer = setTimeout(() => {
      api<{ users: Member[] }>(`documents/${documentId}/recipients?search=${encodeURIComponent(search)}`, { signal: controller.signal })
        .then(result => { setMembers(result.users); setError(''); }).catch(error => { if (!isAbort(error)) setError(errorMessage(error)); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [documentId, search]);
  return <form onSubmit={async event => {
    event.preventDefault(); if (busy) return; setBusy(true); onBusyChange?.(true); setSubmitted(true); setError('');
    try { const items = documents.map((doc, index) => ({ document_id: doc.id, expected_owner: doc.mv_user, idempotency_key: keys[index] })); await api(documents.length === 1 ? `documents/${documentId}/transfers` : 'documents/transfers/batch', { method: 'POST', body: JSON.stringify(documents.length === 1 ? { recipient, reason, expected_owner: items[0].expected_owner, idempotency_key: items[0].idempotency_key } : { recipient, reason, documents: items }) }); onTransferred(); }
    catch (error) { setError(errorMessage(error)); } finally { setBusy(false); onBusyChange?.(false); }
  }}><p className="notice">Todos os documentos serão enviados ao mesmo destinatário. Se algum falhar, o lote será revertido. A assinatura permanece no MV.</p><ul>{documents.map(doc => <li key={doc.id}><strong>{doc.title}</strong> · {doc.id} · {doc.patient_name ?? "Paciente não informado"} · {doc.provider_name}</li>)}</ul>
    <label htmlFor="recipient-search">Buscar destinatário</label><input id="recipient-search" value={search} disabled={busy || submitted} maxLength={128} onChange={event => { setSearch(event.target.value); }} />
    <label htmlFor="recipient">Destinatário</label><select id="recipient" value={recipient} required disabled={busy || loading || submitted} onChange={event => { setRecipient(event.target.value); }}><option value="">{loading ? 'Buscando…' : 'Selecione um usuário'}</option>{members.map(member => <option key={member.username} value={member.username}>{member.name} · {member.username}</option>)}</select>
    <label htmlFor="reason">Justificativa</label><textarea id="reason" value={reason} required minLength={10} maxLength={1000} disabled={busy || submitted} onChange={event => { setReason(event.target.value); }} />
    <ErrorNotice message={error} /><button className="primary" disabled={busy || loading || !recipient}>{busy ? 'Transferindo…' : 'Confirmar transferência'}</button>
  </form>;
}
