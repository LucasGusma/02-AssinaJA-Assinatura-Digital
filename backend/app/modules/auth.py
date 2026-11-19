from fastapi import APIRouter, Depends, Request, Response
from pydantic import ValidationError

from backend.app.core.errors import AppError
from backend.app.modules.dependencies import COOKIE, call, current_session
from backend.app.modules.schemas import Login, LoginResult, Session

router = APIRouter(prefix='/auth', tags=['Autenticação'])


@router.post('/login', response_model=Session)
def login(data: Login, request: Request, response: Response):
    request.app.state.login_limiter.check(request.client.host if request.client else 'unknown')
    settings = request.app.state.settings
    try:
        result = LoginResult.model_validate(call(request, 'auth.login', {
            'username': data.username, 'password': data.password.get_secret_value(),
            'ttl_seconds': settings.session_ttl_seconds,
        }, authenticated=False))
    except ValidationError:
        raise AppError('INVALID_PACKAGE_RESPONSE', 'Resposta da integração incompatível com o contrato.', 502) from None
    response.set_cookie(COOKIE, result.token, max_age=min(settings.session_ttl_seconds, result.expires_in),
                        httponly=True, secure=settings.session_cookie_secure, samesite='strict', path='/api')
    return Session(user=result.user)


@router.get('/session', response_model=Session)
def session(value: Session = Depends(current_session)):
    return value


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response):
    if request.cookies.get(COOKIE):
        try:
            call(request, 'auth.logout')
        except AppError as error:
            if error.status != 401:
                raise
    response.delete_cookie(COOKIE, path='/api', secure=request.app.state.settings.session_cookie_secure,
                           httponly=True, samesite='strict')
