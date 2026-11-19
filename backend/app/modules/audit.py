from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from backend.app.modules.dependencies import call, current_session
from backend.app.modules.schemas import AuditPage

router = APIRouter(prefix='/audit', tags=['Auditoria'], dependencies=[Depends(current_session)])


@router.get('', response_model=AuditPage)
def audit(request: Request, before: int | None = Query(default=None, gt=0),
          search: str = Query(default='', max_length=128),
          action: Literal['', 'TRANSFERENCIA', 'PERMISSAO'] = '',
          document_id: int | None = Query(default=None, gt=0)):
    return call(request, 'audit.list', {'before': before, 'limit': 50, 'search': search.strip(), 'action': action, 'document_id': document_id})
