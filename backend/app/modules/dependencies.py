from fastapi import Request
from pydantic import ValidationError

from backend.app.core.errors import AppError
from backend.app.modules.schemas import Session

COOKIE = 'assinaja_session'


def token(request: Request) -> str:
    value = request.cookies.get(COOKIE, '')
    if not value or len(value) > 512:
        raise AppError('SESSION_EXPIRED', 'Entre para continuar.', 401)
    return value


def call(request: Request, operation: str, payload: dict | None = None, authenticated=True):
    return request.app.state.gateway.call(
        operation, payload or {}, token(request) if authenticated else None, request.state.request_id,
    )


def current_session(request: Request) -> Session:
    try:
        return Session.model_validate(call(request, 'auth.session'))
    except ValidationError:
        raise AppError('INVALID_PACKAGE_RESPONSE', 'Resposta da integração incompatível com o contrato.', 502) from None


def master_session(request: Request) -> Session:
    session = current_session(request)
    if not session.user.is_master:
        raise AppError('FORBIDDEN', 'Administração de permissões disponível somente ao master.', 403)
    return session
