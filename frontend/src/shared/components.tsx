import { useEffect, useRef, type ReactNode } from 'react';

export function Brand() { return <span className="app-logo">Assina<span>JA</span><span className="logo-dot">.</span></span>; }
export function ErrorNotice({ message }: { message: string }) { return message ? <p className="error-box" role="alert">{message}</p> : null; }
export function Loading() { return <p className="empty" role="status">Carregando…</p>; }
export function Pagination({ page, previous, next, busy }: { page: number; previous?: () => void; next?: () => void; busy: boolean }) {
  return <div className="pagination"><button className="secondary" disabled={!previous || busy} onClick={previous}>← Anterior</button><span>Página {page + 1}</span><button className="secondary" disabled={!next || busy} onClick={next}>Próxima →</button></div>;
}
export function Modal({ title, children, onClose, busy = false }: { title: string; children: ReactNode; onClose: () => void; busy?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const node = dialog.current; node?.showModal(); return () => node?.close(); }, []);
  return <dialog ref={dialog} onCancel={event => { event.preventDefault(); if (!busy) onClose(); }} aria-labelledby="modal-title"><div className="dialog-top"><span className="eyebrow">DOCUMENTO CLÍNICO · MV</span><button className="subtle" aria-label="Fechar documento" disabled={busy} onClick={onClose}>✕</button></div><h2 id="modal-title">{title}</h2>{children}</dialog>;
}
