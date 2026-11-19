import { useState, type FormEvent } from 'react';
import { api, errorMessage } from '../../shared/api';
import { Brand, ErrorNotice } from '../../shared/components';
import type { IntegrationStatus, Session, User } from '../../shared/types';

export function Login({ status, onLogin, onRetry }: { status: IntegrationStatus | null; onLogin: (user: User) => void; onRetry: () => void }) {
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError('');
    try {
      const result = await api<Session>('auth/login', { method: 'POST', body: JSON.stringify({ username: String(data.get('username')).trim(), password: data.get('password') }) });
      form.reset(); onLogin(result.user);
    } catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  const enabled = status?.integration === 'configured';
  return <div className="login-page"><header className="login-header"><div className="hospital-logo"><img src="/logo-baleia.png" alt="Hospital de Referência Modelo" /></div><div className="header-app-brand" role="img" aria-label="AssinaJA"><span className="header-app-mark"><img src="/logo-assinaja.png" alt="" /></span><span className="header-app-name" aria-hidden="true">ssina<span>JA</span></span></div><div className="technology-brand"><span className="eyebrow">TECNOLOGIA A SERVIÇO DO CUIDADO</span><img src="/logo-baleia-ia.png" alt="BaleIA" /></div></header>
    <main className="login-layout"><section className="intro"><span className="eyebrow">HOSPITAL DA BALEIA · 100% SUS</span><h1>Mais organização.<br />Mais tempo<br /><em>para cuidar.</em></h1><p>Acompanhe pendências e encaminhe documentos com rastreabilidade.</p><p className="intro-note">✓ Cada documento, com o responsável certo.</p></section>
      <section className="login-card"><Brand /><p className="eyebrow">GESTÃO DE PENDÊNCIAS</p><h2>Bem-vindo de volta</h2><p>Acesse com seu usuário institucional.</p>
        {!enabled && <div className="notice" role="status"><strong>{status ? 'Integração em preparação' : 'Conexão indisponível'}</strong><p>{status?.message ?? 'Não foi possível consultar a API.'}</p><button type="button" className="secondary" onClick={onRetry}>Verificar novamente</button></div>}
        <form onSubmit={submit}><label htmlFor="username">Usuário</label><input id="username" name="username" autoComplete="username" maxLength={128} required disabled={!enabled || busy} placeholder="Seu usuário MV" />
          <label htmlFor="password">Senha</label><div className="password-field"><input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" maxLength={256} required disabled={!enabled || busy} /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}>{showPassword ? 'Ocultar' : 'Mostrar'}</button></div>
          <ErrorNotice message={error} /><button className="primary login-submit" disabled={!enabled || busy}>{busy ? 'Entrando…' : 'Entrar no AssinaJA →'}</button></form>
        <p className="muted fine-print">A assinatura dos documentos permanece no MV.</p>
      </section></main></div>;
}