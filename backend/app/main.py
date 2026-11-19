import logging
from pathlib import Path
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import AppError
from backend.app.core.middleware import SecurityMiddleware
from backend.app.core.security import LoginLimiter
from backend.app.infrastructure.oracle.gateway import OracleGateway, PendingGateway
from backend.app.infrastructure.oracle.pool import OraclePool
from backend.app.infrastructure.oracle.mv_gateway import MVPackageGateway
from backend.app.modules import audit, auth, directory, documents

logger = logging.getLogger('assinaja')


def create_app(settings: Settings | None = None, gateway=None):
    settings = settings or get_settings()
    uploaded_logo = Path(r"C:\Users\f015114\.gemini\antigravity\brain\4c42f1b7-1a09-4439-913b-076db36a5cf6\.user_uploaded\media_1794427999208_31839dac.png")
    if uploaded_logo.is_file():
        for dest in (settings.frontend_dist / 'logo-baleia-ia.png', settings.frontend_dist.parent / 'public' / 'logo-baleia-ia.png'):
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(uploaded_logo, dest)
            except Exception:
                pass
    pool = OraclePool(settings)

    @asynccontextmanager
    async def lifespan(application):
        if gateway is None and settings.oracle_configured:
            try:
                pool.start()
            except Exception:
                logger.error('Falha ao inicializar Oracle Thick. Confira configuração e conectividade localmente.')
                raise RuntimeError('Oracle Thick indisponível; inicialização cancelada.') from None
        try:
            yield
        finally:
            pool.close()

    app = FastAPI(title='AssinaJA API', version='1.0.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None,
                  openapi_url='/api/openapi.json' if settings.app_environment != 'production' else None)
    app.state.settings = settings
    app.state.gateway = gateway if gateway is not None else (
        MVPackageGateway(pool) if settings.oracle_integration_mode == 'mv_refcursor'
        else OracleGateway(pool) if settings.oracle_package_routine else PendingGateway())
    app.state.login_limiter = LoginLimiter()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SecurityMiddleware, settings=settings)

    def error_response(request, status, code, message):
        return JSONResponse({'error': {'code': code, 'message': message,
                                      'request_id': getattr(request.state, 'request_id', '')}}, status_code=status)

    @app.exception_handler(AppError)
    async def app_error(request, error):
        return error_response(request, error.status, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def request_error(request, error):
        # Pydantic errors may contain the input password. Never serialize them.
        return error_response(request, 422, 'INVALID_INPUT', 'Confira os campos e formatos informados.')

    @app.exception_handler(ResponseValidationError)
    async def response_error(request, error):
        logger.error('Contrato Oracle incompatível request_id=%s', request.state.request_id)
        return error_response(request, 502, 'INVALID_PACKAGE_RESPONSE', 'Resposta da integração incompatível com o contrato.')

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response(request, error.status_code, 'HTTP_ERROR', 'Recurso indisponível.')

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        logger.error('Falha interna request_id=%s type=%s', getattr(request.state, 'request_id', ''), type(error).__name__)
        return error_response(request, 500, 'INTERNAL_ERROR', 'Não foi possível concluir a operação.')

    for router in (auth.router, documents.router, directory.router, audit.router):
        app.include_router(router, prefix='/api/v1')

    @app.get('/api/health/live', tags=['Saúde'])
    def live():
        return {'status': 'ok'}

    @app.get('/api/health/ready', tags=['Saúde'])
    def ready(request: Request):
        app.state.gateway.call('health.ready', {}, None, request.state.request_id)
        return {'status': 'ready'}

    @app.get('/api/v1/status', tags=['Integração'])
    def status():
        configured = app.state.gateway.configured
        limited = settings.oracle_integration_mode == 'mv_refcursor'
        return {'integration': 'configured' if configured else 'pending',
                'transfers_enabled': configured and settings.transfers_enabled,
                'capabilities': {'sector_filter': not limited, 'audit': True},
                'message': 'Integração configurada.' if configured else 'A integração com o MV está em preparação. O acesso será liberado após a configuração.'}

    if (settings.frontend_dist / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=settings.frontend_dist / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path == 'api' or path.startswith('api/'):
            raise HTTPException(404)
        if path == 'logo-baleia-ia.png':
            if uploaded_logo.is_file():
                return FileResponse(uploaded_logo)
        if path in ('logo-baleia.png', 'logo-baleia-ia.png', 'logo-assinaja.png') and (settings.frontend_dist / path).is_file():
            return FileResponse(settings.frontend_dist / path)
        if '.' in path:
            raise HTTPException(404)
        index = settings.frontend_dist / 'index.html'
        if index.is_file():
            return FileResponse(index, headers={'Cache-Control': 'no-cache'})
        return JSONResponse({'message': 'Frontend ainda não compilado. Execute npm run build em frontend/.'}, status_code=503)

    return app


app = create_app()
