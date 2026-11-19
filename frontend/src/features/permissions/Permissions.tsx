import { useEffect, useState } from 'react';
import { api, errorMessage, isAbort, normalize } from '../../shared/api';
import { ErrorNotice, Loading } from '../../shared/components';
import type { Member, Sector } from '../../shared/types';

export function Permissions({ canManage = false, onPermissionChanged }: { canManage?: boolean; onPermissionChanged?: () => void }) {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selected, setSelected] = useState<Sector | null>(null);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    api<{ sectors: Sector[] }>('sectors', { signal: controller.signal }).then(result => setSectors(result.sectors)).catch(error => { if (!isAbort(error)) setError(errorMessage(error)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry]);
  return <section className="panel panel-body"><h2>Usuários ativos</h2><p className="muted">Somente ADMIN pode alterar a permissão de transferência. A permissão vale em todos os setores.</p><ErrorNotice message={error} />{error && <button className="secondary" onClick={() => setRetry(retry + 1)}>Tentar novamente</button>}
    <label htmlFor="sector-filter">Buscar setor por nome</label><input id="sector-filter" value={search} onChange={event => setSearch(event.target.value)} />
    <div className="directory-layout"><div className="sector-list">{loading && <Loading />}{sectors.filter(sector => normalize(sector.name).includes(normalize(search))).map(sector => <button className={`secondary ${selected?.id === sector.id ? 'selected' : ''}`} key={sector.id} onClick={() => setSelected(sector)}>{sector.name}</button>)}</div>
      {selected ? <SectorMembers key={selected.id} sector={selected} canManage={canManage} onPermissionChanged={onPermissionChanged} /> : <p className="empty">Selecione um setor.</p>}</div></section>;
}

function SectorMembers({ sector, canManage, onPermissionChanged }: { sector: Sector; canManage: boolean; onPermissionChanged?: () => void }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    api<{ users: Member[] }>(`users?sector=${sector.id}`, { signal: controller.signal }).then(result => setMembers(result.users)).catch(error => { if (!isAbort(error)) setError(errorMessage(error)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [sector.id, retry]);
  const filtered = members.filter(member => normalize(`${member.name} ${member.username}`).includes(normalize(search)));
  async function save(member: Member, enabled: boolean) {
    if (saving || !canManage) return; setSaving(member.username); setError(''); setNotice('');
    try {
      await api('permissions', { method: 'PUT', body: JSON.stringify({ username: member.username, sector_id: sector.id, enabled }) });
      setMembers(current => current.map(value => value.username === member.username ? { ...value, can_forward: enabled } : value));
      setNotice('Permissão atualizada.'); onPermissionChanged?.();
    } catch (error) { setError(errorMessage(error)); } finally { setSaving(null); }
  }
  return <div><h3>{sector.name}</h3><label htmlFor="user-search">Buscar por nome ou F0</label><input id="user-search" value={search} onChange={event => setSearch(event.target.value)} /><ErrorNotice message={error} />{error && !saving && <button className="secondary" onClick={() => setRetry(retry + 1)}>Recarregar usuários</button>}{notice && <p className="notice" role="status">{notice}</p>}
    {loading ? <Loading /> : <><p className="muted" role="status">{filtered.length} usuário(s) encontrado(s)</p><div className="table-scroll"><table><thead><tr><th>Profissional</th><th>Cargo / tipo de prestador</th><th>Pode transferir</th></tr></thead><tbody>{filtered.map(member => <tr key={member.username}><td>{member.name}<small>{member.username}</small></td><td>{member.profile ?? 'Não informado'}</td><td><input type="checkbox" aria-label={`Permitir transferência para ${member.name}`} checked={member.can_forward} disabled={!canManage || saving !== null} onChange={event => void save(member, event.target.checked)} /></td></tr>)}</tbody></table></div></>}
  </div>;
}
