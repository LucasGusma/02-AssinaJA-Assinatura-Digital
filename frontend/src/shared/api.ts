export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) { super(message); }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.method && options.method !== 'GET') {
    headers.set('Content-Type', 'application/json');
    headers.set('X-CSRF-Protection', '1');
  }
  const response = await fetch(`/api/v1/${path}`, { ...options, headers, credentials: 'same-origin', cache: 'no-store' });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== 'auth/login') window.dispatchEvent(new Event('session-expired'));
    throw new ApiError(response.status, body?.error?.code ?? 'UNAVAILABLE', body?.error?.message ?? 'Não foi possível concluir a operação.', body?.error?.request_id);
  }
  return body as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Não foi possível concluir a operação.';
}
export function isAbort(error: unknown) { return error instanceof Error && error.name === 'AbortError'; }
export const dateTime = (value?: string | null) => value ? new Date(value).toLocaleString('pt-BR') : 'Não informado';
export const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
