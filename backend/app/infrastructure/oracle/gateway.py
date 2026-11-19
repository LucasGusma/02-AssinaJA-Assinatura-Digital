"""Transport contract only. Business rules are implemented by the Oracle package."""
import json
from typing import Protocol

import oracledb

from backend.app.core.errors import AppError, ERRORS, integration_pending
from backend.app.infrastructure.oracle.pool import OraclePool
from backend.app.modules.schemas import AuditPage, Content, Documents, LoginResult, Members, Sectors, Session, TransferResult

MAX_JSON = 2 * 1024 * 1024
MAX_PDF = 20 * 1024 * 1024
RESPONSE_MODELS = {
    'auth.login': LoginResult, 'auth.session': Session,
    'directory.sectors': Sectors, 'directory.users': Members, 'directory.recipients': Members,
    'documents.list': Documents, 'documents.content': Content,
    'transfers.create': TransferResult, 'audit.list': AuditPage,
}


class Gateway(Protocol):
    configured: bool

    def call(self, operation: str, payload: dict, session: str | None, request_id: str) -> dict: ...
    def file(self, document_id: int, session: str, request_id: str) -> bytes: ...


class PendingGateway:
    configured = False

    def call(self, operation, payload, session, request_id):
        raise integration_pending()

    def file(self, document_id, session, request_id):
        raise integration_pending()


class OracleGateway:
    configured = True

    def __init__(self, pool: OraclePool):
        self.pool = pool

    def call(self, operation, payload, session, request_id):
        request = json.dumps({'version': 1, 'operation': operation, 'session': session,
                              'request_id': request_id, 'payload': payload}, ensure_ascii=False)
        try:
            with self.pool.connection(request_id) as connection:
                with connection.cursor() as cursor:
                    source = cursor.var(oracledb.DB_TYPE_CLOB)
                    source.setvalue(0, request)
                    target = cursor.var(oracledb.DB_TYPE_CLOB)
                    cursor.callproc(self.pool.settings.oracle_package_routine, [source, target])
                    output = target.getvalue()
                    if output is None or (output.size() if hasattr(output, 'size') else len(output)) > MAX_JSON:
                        raise ValueError('Invalid package response size')
                    result = json.loads(output.read() if hasattr(output, 'read') else output)
                    if not isinstance(result, dict):
                        raise ValueError('Invalid response')
                    if result.get('ok') is not True:
                        code = result.get('error', {}).get('code', 'UNAVAILABLE')
                        status, message = ERRORS.get(code, ERRORS['UNAVAILABLE'])
                        # Preserve authentication failure counters, never clinical
                        # changes. This exception is part of the package contract.
                        if operation == 'auth.login' and code in ('INVALID_CREDENTIALS', 'RATE_LIMITED'):
                            connection.commit()
                        raise AppError(code if code in ERRORS else 'UNAVAILABLE', message, status)
                    if not isinstance(result.get('data'), dict):
                        raise ValueError('Invalid response data')
                    model = RESPONSE_MODELS.get(operation)
                    if model:
                        model.model_validate(result['data'])
                    # Packages must not commit business changes or retain user state.
                    connection.commit()
                    return result['data']
        except oracledb.Error:
            raise AppError('UNAVAILABLE', 'Serviço Oracle temporariamente indisponível.', 503) from None
        except (ValueError, TypeError, AttributeError):
            raise AppError('INVALID_PACKAGE_RESPONSE', 'Resposta da integração incompatível com o contrato.', 502) from None

    def file(self, document_id, session, request_id):
        if not self.pool.settings.oracle_file_routine:
            raise AppError('FILE_INTEGRATION_PENDING', 'Leitura de PDF ainda não configurada.', 503)
        try:
            with self.pool.connection(request_id) as connection:
                with connection.cursor() as cursor:
                    output = cursor.var(oracledb.DB_TYPE_BLOB)
                    status = cursor.var(str, size=40)
                    cursor.callproc(self.pool.settings.oracle_file_routine, [session, document_id, request_id, output, status])
                    code = status.getvalue()
                    if code != 'OK':
                        http_status, message = ERRORS.get(code, ERRORS['UNAVAILABLE'])
                        raise AppError(code if code in ERRORS else 'UNAVAILABLE', message, http_status)
                    blob = output.getvalue()
                    if blob is None or blob.size() > MAX_PDF:
                        raise AppError('INVALID_FILE', 'Documento indisponível ou maior que 20 MB.', 422)
                    content = blob.read()
                    if not content.startswith(b'%PDF-'):
                        raise AppError('INVALID_FILE', 'O arquivo recebido não é um PDF.', 422)
                    connection.commit()
                    return content
        except oracledb.Error:
            raise AppError('UNAVAILABLE', 'Serviço Oracle temporariamente indisponível.', 503) from None
