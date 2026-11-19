"""Transfer adapter; Oracle owns authorization, locking, DML and audit."""
import oracledb

from backend.app.core.errors import AppError
from backend.app.modules.schemas import Members, TransferResult

PACKAGE = 'SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.'


def eligibility(connection, ids):
    if not ids:
        return {}
    binds = {f'id{i}': value for i, value in enumerate(ids)}
    placeholders = ','.join(':' + name for name in binds)
    with connection.cursor() as cursor:
        cursor.execute('SELECT CD_DOCUMENTO_CLINICO, ' + PACKAGE + 'BLOQUEIO(CD_DOCUMENTO_CLINICO) '
                       'FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO WHERE CD_DOCUMENTO_CLINICO IN (' + placeholders + ')', binds)
        return dict(cursor.fetchall())


def recipients(connection, username, payload):
    with connection.cursor() as cursor, connection.cursor() as result:
        cursor.callproc(PACKAGE + 'DESTINATARIOS', [username, payload['document_id'], payload.get('search', ''), result])
        return Members(users=[{'username': r[0], 'name': r[1], 'profile': r[2]} for r in result.fetchall()]).model_dump()


def transfer(connection, username, payload, request_id, *, commit=True):
    if not payload.get('expected_owner'):
        raise AppError('INVALID_INPUT', 'Atualize a consulta antes de transferir.', 422)
    with connection.cursor() as cursor:
        event = cursor.var(oracledb.DB_TYPE_NUMBER)
        cursor.callproc(PACKAGE + 'TRANSFERIR', [username, payload['document_id'], payload['expected_owner'],
                        payload['recipient'], payload['reason'], str(payload['idempotency_key']), request_id, event])
        identifier = event.getvalue()
        if identifier is None or identifier <= 0:
            raise AppError('INVALID_PACKAGE_RESPONSE', 'O Oracle não confirmou a transferência.', 502)
        result = TransferResult(transfer_id=str(int(identifier)), message='Transferência confirmada pelo Oracle.')
        if commit:
            connection.commit()
        return result.model_dump()


def batch(connection, username, payload, request_id):
    items = payload['documents']
    ids = [item['document_id'] for item in items]
    if len(ids) != len(set(ids)):
        raise AppError('INVALID_INPUT', 'Documento repetido na seleção.', 422)
    try:
        providers = set()
        with connection.cursor() as cursor:
            for identifier in sorted(ids):
                cursor.execute('SELECT CD_PRESTADOR FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO '
                               'WHERE CD_DOCUMENTO_CLINICO=:id FOR UPDATE WAIT 5', id=identifier)
                row = cursor.fetchone()
                if not row or row[0] is None:
                    raise AppError('TRANSFER_CONFLICT', 'Documento ou prestador indisponível.', 409)
                providers.add(row[0])
        if len(providers) != 1:
            raise AppError('INVALID_INPUT', 'Selecione documentos do mesmo prestador.', 422)
        results = [transfer(connection, username, {**item, 'recipient': payload['recipient'],
                   'reason': payload['reason']}, request_id, commit=False) for item in items]
        connection.commit()
        return {'transfers': results, 'message': 'Todos os documentos foram transferidos.'}
    except Exception:
        connection.rollback()
        raise
