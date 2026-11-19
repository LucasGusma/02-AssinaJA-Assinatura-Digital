"""REF CURSOR adapter. Authorization and directory rules live in Oracle."""
from backend.app.modules.schemas import AuditPage, Members, Sectors

PACKAGE = 'APP_SCHEMA.PKG_ASSINAJA_ACESSO.'


def query(connection, cursor, routine, arguments):
    with connection.cursor() as procedure, connection.cursor() as result:
        result.arraysize = 100
        procedure.callproc(PACKAGE + routine, [*arguments, result])
        return result.fetchall()


def profile(connection, cursor, username):
    row = query(connection, cursor, 'PERFIL', [username])[0]
    return {'username': row[0], 'name': row[1], 'is_master': row[2] == 'S',
            'can_transfer': row[3] == 'S', 'all_sectors': True}


def dispatch(connection, cursor, operation, username, payload, request_id):
    if operation == 'directory.sectors':
        rows = query(connection, cursor, 'SETORES', [username])
        return Sectors(sectors=[{'id': r[0], 'name': r[1]} for r in rows]).model_dump()
    if operation == 'directory.users':
        rows = query(connection, cursor, 'USUARIOS', [username, payload['sector_id']])
        return Members(users=[{'username': r[0], 'name': r[1], 'profile': r[2],
                               'can_forward': r[3] == 'S'} for r in rows]).model_dump()
    if operation == 'permissions.update':
        cursor.callproc(PACKAGE + 'PERMISSAO', [username, payload['username'].upper(),
                        'S' if payload['enabled'] else 'N', request_id])
        connection.commit()
        return {}
    if operation == 'audit.list':
        with connection.cursor() as procedure, connection.cursor() as result:
            procedure.callproc(PACKAGE + 'AUDITORIA', [username, payload.get('before'), result,
                               payload.get('search') or None, payload.get('action') or None, payload.get('document_id')])
            rows = result.fetchmany(51)
        events = [{'id': r[0], 'created': r[1], 'actor': f'{r[3]} ({r[2]})',
                   'action': r[4], 'detail': r[5], 'document_id': r[6],
                   'source_user': r[7], 'source_name': r[8],
                   'target_user': r[9], 'target_name': r[10], 'request_id': r[11] if len(r) > 11 else None} for r in rows[:50]]
        return AuditPage(events=events, next_cursor=events[-1]['id'] if len(rows) > 50 else None).model_dump()
    raise ValueError('Unsupported access operation')
