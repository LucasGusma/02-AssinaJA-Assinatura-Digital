import { useEffect, useState } from 'react';
import { Login } from '../features/auth/Login';
import { Documents } from '../features/documents/Documents';
import { Permissions } from '../features/permissions/Permissions';
import { Audit } from '../features/audit/Audit';
import { api, errorMessage, isAbort } from '../shared/api';
import { Brand, ErrorNotice, Loading } from '../shared/components';
import type { IntegrationStatus, Session, User } from '../shared/types';

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener('session-expired', expired);
    return () => window.removeEventListener('session-expired', expired);
  }, []);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setStatus(null);
    async function initialize() {
      try {
        const value = await api<IntegrationStatus>('status', { signal: controller.signal }); setStatus(value);
        if (value.integration === 'configured') {
          const session = await api<Session>('auth/session', { signal: controller.signal }); setUser(session.user);
        }
      } catch (error) { if (!isAbort(error)) setUser(null); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void initialize(); return () => controller.abort();
  }, [attempt]);
  return <>{loading ? <main className="startup"><Brand /><Loading /></main> : user && status ? <Workspace key={user.username} user={user} status={status} onUserChange={setUser} onLogout={() => setUser(null)} /> : <Login status={status} onLogin={setUser} onRetry={() => setAttempt(attempt + 1)} />}
    <footer>AssinaJA · Uso interno<span>Desenvolvedores: <b>Lucas Gusmão</b> e <b>Gabriel Soares</b></span></footer></>;
}

function Workspace({ user, status, onLogout, onUserChange }: { user: User; status: IntegrationStatus; onLogout: () => void; onUserChange: (user: User) => void }) {
  const [view, setView] = useState('documents');
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigation = [{ id: 'documents', title: 'Visão geral', icon: '▦' }, { id: 'my-documents', title: 'Meus documentos', icon: '▤' }, { id: 'access', title: 'Usuários ativos', icon: '♙' }, { id: 'audit', title: 'Auditoria', icon: '◷' }, { id: 'integration', title: 'Integração MV', icon: '⇄' }];
  return <div className="workspace"><aside className="sidebar"><Brand /><p className="eyebrow">GESTÃO DE PENDÊNCIAS</p><nav aria-label="Navegação principal">{navigation.map(item => <button key={item.id} className={view === item.id ? 'active' : ''} aria-current={view === item.id ? 'page' : undefined} onClick={() => setView(item.id)}><span>{item.icon}</span>{item.title}</button>)}</nav><div className="sidebar-bottom"><div className="hospital-logo"><img src="/logo-baleia.png" alt="Hospital de Referência Modelo" /></div><p>Juntos pelo cuidado.</p><span className="badge">● Integração Oracle</span></div></aside>
    <div className="main-shell"><header className="topbar"><span>Hospital de Referência Modelo / <b>AssinaJA</b></span><div className="account"><span>{user.name}{user.is_master ? ' · Master' : ''}</span><button className="subtle" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { await api('auth/logout', { method: 'POST', body: '{}' }); onLogout(); } catch (error) { setError(errorMessage(error)); } finally { setBusy(false); } }}>Sair ↗</button></div></header>
      <main className="content"><div className="notice">{view === 'my-documents' ? 'Pendências de assinatura vinculadas ao seu usuário MV.' : 'Visão geral de pendências de assinatura disponível aos usuários autenticados.'} A assinatura permanece no MV.</div><ErrorNotice message={error} /><div className="page-heading"><div><span className="eyebrow">HOSPITAL DA BALEIA</span><h1>{navigation.find(item => item.id === view)?.title}</h1><p className="muted">Cada pendência acompanhada. Cada ação registrada.</p></div><button className="secondary" onClick={() => setRevision(revision + 1)}>↻ Atualizar</button></div>
        <div key={`${view}-${revision}`}>{(view === 'documents' || view === 'my-documents') && <Documents transfersEnabled={status.transfers_enabled} scope={view === 'my-documents' ? 'mine' : 'all'} canTransfer={status.transfers_enabled && user.can_transfer} sectorFilter={status.capabilities?.sector_filter !== false} />}{view === 'access' && <Permissions canManage={user.is_master} onPermissionChanged={() => { void api<Session>('auth/session').then(session => onUserChange(session.user)).catch(error => setError(errorMessage(error))); }} />}{view === 'audit' && <Audit />}{view === 'integration' && <section className="panel panel-body"><h2>Integração com o MV</h2><p>{status.message}</p><p>{status.capabilities?.sector_filter === false ? "Consulta geral e pessoal de documentos fechados que exigem assinatura. Usuários ativos, permissões e auditoria integrados ao Oracle. Transferência integrada para documentos elegíveis. Confira eventuais restrições nos detalhes." : "Consultas, permissões e auditoria são processadas no Oracle."}</p><p className="notice">{status.transfers_enabled ? 'Transferências habilitadas conforme as permissões de cada usuário.' : 'Transferências aguardam homologação. Nenhuma transferência será apresentada como concluída antes da confirmação do Oracle.'}</p></section>}</div>
      </main></div></div>;
}
