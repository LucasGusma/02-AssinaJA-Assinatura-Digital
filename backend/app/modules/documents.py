from datetime import date
from calendar import monthrange
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from backend.app.core.errors import AppError
from backend.app.modules.dependencies import call, current_session, token
from backend.app.modules.schemas import BatchTransfer, Content, Documents, Session, Transfer, TransferResult

router = APIRouter(prefix='/documents', tags=['Documentos'], dependencies=[Depends(current_session)])


@router.get('', response_model=Documents)
def documents(request: Request, start: date, end: date, sector: int | None = Query(default=None, gt=0),
              before: int | None = Query(default=None, gt=0), scope: Literal['all', 'mine'] = 'mine',
              provider: str = Query(default='', max_length=128), document_type: int | None = Query(default=None, gt=0)):
    month_index = end.year * 12 + end.month - 1 - 3
    year, month = divmod(month_index, 12)
    month += 1
    day = monthrange(year, month)[1] if end.day == monthrange(end.year, end.month)[1] else min(end.day, monthrange(year, month)[1])
    if end < start or start < date(year, month, day):
        raise AppError('INVALID_INPUT', 'Selecione um período de até 3 meses.', 422)
    return call(request, 'documents.list', {'start': start.isoformat(), 'end': end.isoformat(),
                                           'sector': sector, 'before': before, 'limit': 50, 'scope': scope,
                                           'provider': provider.strip(), 'document_type': document_type})


@router.get('/{document_id}/content', response_model=Content)
def content(document_id: int, request: Request):
    validate_id(document_id)
    return call(request, 'documents.content', {'document_id': document_id})


@router.get('/{document_id}/file')
def file(document_id: int, request: Request):
    validate_id(document_id)
    content = request.app.state.gateway.file(document_id, token(request), request.state.request_id)
    return Response(content, media_type='application/pdf', headers={
        'Content-Disposition': f'inline; filename="documento-{document_id}.pdf"',
        'Content-Security-Policy': "default-src 'none'; frame-ancestors 'self'",
        'X-Frame-Options': 'SAMEORIGIN',
    })


@router.post('/{document_id}/transfers', response_model=TransferResult)
def transfer(document_id: int, data: Transfer, request: Request, session: Session = Depends(current_session)):
    validate_id(document_id)
    if not request.app.state.settings.transfers_enabled:
        raise AppError('TRANSFERS_DISABLED', 'Transferências aguardam homologação da rotina MV.', 503)
    if not session.user.can_transfer:
        raise AppError('FORBIDDEN', 'Você não tem permissão para transferir documentos.', 403)
    return call(request, 'transfers.create', {'document_id': document_id, **data.model_dump(mode='json')})


def validate_id(value):
    if value <= 0:
        raise AppError('INVALID_INPUT', 'Documento inválido.', 422)


@router.post('/transfers/batch')
def transfer_batch(data: BatchTransfer, request: Request, session: Session = Depends(current_session)):
    if not request.app.state.settings.transfers_enabled:
        raise AppError('TRANSFERS_DISABLED', 'Transferências desabilitadas.', 503)
    if not session.user.can_transfer:
        raise AppError('FORBIDDEN', 'Você não tem permissão para transferir documentos.', 403)
    return call(request, 'transfers.batch', data.model_dump(mode='json'))


@router.get('/types')
def document_types(request: Request):
    return call(request, 'documents.types')


@router.get('/summary')
def document_summary(request: Request, scope: Literal['all', 'mine'] = 'mine'):
    return call(request, 'documents.summary', {'scope': scope})
