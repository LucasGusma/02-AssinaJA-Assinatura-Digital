from fastapi import APIRouter, Depends, Query, Request

from backend.app.modules.dependencies import call, current_session, master_session
from backend.app.modules.schemas import Members, PermissionChange, Sectors

router = APIRouter(tags=['Diretório e permissões'])


@router.get('/sectors', response_model=Sectors, dependencies=[Depends(current_session)])
def sectors(request: Request):
    return call(request, 'directory.sectors')


@router.get('/users', response_model=Members, dependencies=[Depends(current_session)])
def users(request: Request, sector: int = Query(ge=0)):
    return call(request, 'directory.users', {'sector_id': sector})


@router.get('/documents/{document_id}/recipients', response_model=Members, dependencies=[Depends(current_session)])
def recipients(document_id: int, request: Request, search: str = Query(default='', max_length=128)):
    from backend.app.modules.documents import validate_id
    validate_id(document_id)
    return call(request, 'directory.recipients', {'document_id': document_id, 'search': search, 'limit': 50})


@router.put('/permissions', dependencies=[Depends(master_session)])
def permission(data: PermissionChange, request: Request):
    call(request, 'permissions.update', data.model_dump())
    return {'message': 'Permissão atualizada.'}
