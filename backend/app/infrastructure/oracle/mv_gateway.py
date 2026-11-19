"""Adapter for LISTA_PENDENCIAS with scope and pagination in Oracle.

Transfers run through the audited Oracle package. Sessions are process-local:
run exactly one worker until Oracle session procedures are provided.
"""
from datetime import date, datetime, time
from hashlib import sha256
import logging
import secrets
from threading import Lock
from time import monotonic

import oracledb

from backend.app.core.errors import AppError
from backend.app.infrastructure.oracle import access, transfers

logger = logging.getLogger('assinaja')


class Sessions:
    def __init__(self, maximum=4096):
        self.items = {}
        self.lock = Lock()
        self.maximum = maximum

    def issue(self, username, ttl):
        token = secrets.token_urlsafe(32)
        with self.lock:
            now = monotonic()
            self.items = {key: value for key, value in self.items.items() if value[1] > now}
            if len(self.items) >= self.maximum:
                raise AppError('SESSION_CAPACITY', 'Limite de sessões atingido. Tente novamente mais tarde.', 503)
            self.items[sha256(token.encode()).digest()] = (username, now + ttl)
        return token

    def resolve(self, token):
        key = sha256((token or '').encode()).digest()
        with self.lock:
            value = self.items.get(key)
            if value and value[1] > monotonic():
                return value[0]
            self.items.pop(key, None)
        raise AppError('SESSION_EXPIRED', 'Sua sessão expirou. Entre novamente.', 401)

    def revoke(self, token):
        with self.lock:
            self.items.pop(sha256((token or '').encode()).digest(), None)


class MVPackageGateway:
    configured = True

    def __init__(self, pool):
        self.pool = pool
        self.sessions = Sessions()

    @staticmethod
    def user(username, name):
        return {'username': username, 'name': name, 'is_master': False,
                'can_transfer': False, 'all_sectors': True}

    def call(self, operation, payload, session, request_id):
        if operation == 'auth.logout':
            self.sessions.revoke(session)
            return {}
        username = None if operation in ('auth.login', 'health.ready') else self.sessions.resolve(session)
        try:
            with self.pool.connection(request_id) as connection:
                with connection.cursor() as cursor:
                    if operation not in ('permissions.update', 'transfers.create', 'transfers.batch'):
                        cursor.execute('SET TRANSACTION READ ONLY')
                    if operation == 'health.ready':
                        owner, package = self.pool.settings.oracle_mv_package.split('.')
                        cursor.execute("SELECT COUNT(*) FROM ALL_OBJECTS WHERE OWNER=:owner AND OBJECT_NAME=:package AND OBJECT_TYPE IN ('PACKAGE','PACKAGE BODY') AND STATUS='VALID'", owner=owner.upper(), package=package.upper())
                        if cursor.fetchone()[0] != 2:
                            raise AppError('PACKAGE_UNAVAILABLE', 'A rotina de consulta está indisponível.', 503)
                        cursor.execute("SELECT COUNT(*) FROM ALL_PROCEDURES WHERE OWNER=:owner AND OBJECT_NAME=:package AND PROCEDURE_NAME='LISTA_PENDENCIAS'", owner=owner.upper(), package=package.upper())
                        if cursor.fetchone()[0] != 1:
                            raise AppError('PACKAGE_UNAVAILABLE', 'A rotina de pendências ainda não foi instalada.', 503)
                        cursor.execute("SELECT COUNT(*) FROM ALL_OBJECTS WHERE OWNER='APP_SCHEMA' AND OBJECT_NAME='PKG_ASSINAJA_ACESSO' AND OBJECT_TYPE IN ('PACKAGE','PACKAGE BODY') AND STATUS='VALID'")
                        if cursor.fetchone()[0] != 2:
                            raise AppError('PACKAGE_UNAVAILABLE', 'A rotina de usuários e auditoria está indisponível.', 503)
                        if self.pool.settings.transfers_enabled:
                            cursor.execute("SELECT COUNT(*) FROM ALL_PROCEDURES WHERE OWNER='APP_SCHEMA' AND OBJECT_NAME='PKG_GERENCIADOR_ASSINATURA' AND PROCEDURE_NAME IN ('TRANSFERIR','DESTINATARIOS','BLOQUEIO')")
                            if cursor.fetchone()[0] != 3:
                                raise AppError('PACKAGE_UNAVAILABLE', 'A rotina de transferência está indisponível.', 503)
                        return {}
                    if operation == 'auth.login':
                        return self.login(cursor, payload, connection)
                    cursor.execute("SELECT NM_USUARIO FROM DBASGU.USUARIOS WHERE CD_USUARIO=:username AND SN_ATIVO='S'", username=username)
                    account = cursor.fetchone()
                    if not account:
                        self.sessions.revoke(session)
                        raise AppError('SESSION_EXPIRED', 'Usuário inativo. Entre novamente.', 401)
                    if operation == 'auth.session':
                        return {'user': access.profile(connection, cursor, username)}
                    if operation in ('documents.types', 'documents.summary'):
                        with connection.cursor() as result:
                            package = self.pool.settings.oracle_mv_package
                            if operation == 'documents.types':
                                cursor.callproc(package + '.TIPOS_DOCUMENTO', [result])
                                return {'types': [{'id': row[0], 'name': row[1]} for row in result]}
                            cursor.callproc(package + '.RESUMO_PENDENCIAS', [username, 'TODOS' if payload.get('scope') == 'all' else 'MEUS', result])
                            total, start, end = result.fetchone()
                            return {'total': int(total), 'start': start.date().isoformat(), 'end': end.date().isoformat()}
                    if operation == 'documents.list':
                        return self.documents(connection, cursor, username, payload)
                    if operation in ('transfers.create', 'transfers.batch', 'directory.recipients'):
                        if not self.pool.settings.transfers_enabled:
                            raise AppError('TRANSFERS_DISABLED', 'Transferências desabilitadas.', 503)
                        if operation == 'directory.recipients':
                            return transfers.recipients(connection, username, payload)
                        if operation == 'transfers.batch':
                            return transfers.batch(connection, username, payload, request_id)
                        return transfers.transfer(connection, username, payload, request_id)
                    if operation in ('directory.sectors', 'directory.users', 'permissions.update', 'audit.list'):
                        return access.dispatch(connection, cursor, operation, username, payload, request_id)
                    if operation == 'documents.content':
                        return {'kind': 'unavailable', 'fields': [], 'partial': False,
                                'message': 'A rotina atual fornece a listagem. A visualização do conteúdo ainda não está integrada.'}
                    raise AppError('FEATURE_UNAVAILABLE', 'Esta funcionalidade ainda não está disponível na integração atual.', 503)
        except oracledb.Error as error:
            code = getattr(error.args[0], 'code', None)
            logger.error('Oracle operation=%s code=%s request_id=%s', operation, code, request_id)
            if code == 20010:
                raise AppError('FORBIDDEN', 'Você não tem permissão para transferir documentos.', 403) from None
            if code == 20011:
                raise AppError('TRANSFER_BLOCKED', 'Documento não elegível para transferência. Atualize a consulta e confira o motivo nos detalhes.', 409) from None
            if code in (20012, 1403):
                raise AppError('INVALID_INPUT', 'Confira o destinatário ativo, o prestador e a justificativa.', 422) from None
            if code in (20013, 1, 54, 60, 30006):
                raise AppError('TRANSFER_CONFLICT', 'Documento alterado ou em uso. Atualize a consulta antes de tentar novamente.', 409) from None
            if code in (6550, 4043, 4063, 6508, 942):
                raise AppError('PACKAGE_UNAVAILABLE', 'As rotinas do AssinaJA estão ausentes ou inválidas no Oracle. Solicite a verificação da integração.', 503) from None
            if code == 20002:
                raise AppError('FORBIDDEN', 'Somente o master pode alterar permissões.', 403) from None
            if code in (20001, 20003):
                raise AppError('INVALID_INPUT', 'Usuário inativo ou dados inválidos.', 422) from None
            raise AppError('UNAVAILABLE', 'Não foi possível consultar o MV. Tente novamente.', 503) from None

    def login(self, cursor, payload, connection=None):
        username = payload['username'].strip().upper()
        password = payload['password']
        if not username or len(username) > 30 or not password or len(password) > 256:
            raise AppError('INVALID_CREDENTIALS', 'Usuário ou senha incorretos.', 401)
        # Existing institutional compatibility mechanism. Password is never kept
        # in the session, returned, logged or written to local persistence.
        expected = (username + password).upper().ljust(30, 'K')
        cursor.execute("""SELECT NM_USUARIO FROM DBASGU.USUARIOS
            WHERE CD_USUARIO=:username AND SN_ATIVO='S'
            AND DBASGU.CRIPTO_DESCRIPTO(CD_SENHA, 'SMVCRIPTON')=:expected""",
                       username=username, expected=expected)
        account = cursor.fetchone()
        if not account:
            raise AppError('INVALID_CREDENTIALS', 'Usuário ou senha incorretos.', 401)
        ttl = min(payload['ttl_seconds'], self.pool.settings.session_ttl_seconds)
        user = access.profile(connection, cursor, username) if connection is not None else self.user(username, account[0])
        return {'user': user, 'token': self.sessions.issue(username, ttl), 'expires_in': ttl}

    def documents(self, connection, cursor, username, payload):
        if payload.get('sector'):
            raise AppError('FILTER_UNAVAILABLE', 'A rotina atual não oferece filtro por setor.', 422)
        scope = payload.get('scope', 'mine')
        if scope not in ('all', 'mine'):
            raise AppError('INVALID_INPUT', 'Escopo de consulta inválido.', 422)
        limit = payload.get('limit', 50)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise AppError('INVALID_INPUT', 'Limite de página inválido.', 422)
        before = payload.get('before')
        first = datetime.combine(date.fromisoformat(payload['start']), time.min)
        # The package normalizes these dates to an inclusive calendar-day range.
        last = datetime.combine(date.fromisoformat(payload['end']), time(23, 59, 59))
        with connection.cursor() as result:
            result.arraysize = limit + 1
            arguments = [username, first, last, 'TODOS' if scope == 'all' else 'MEUS', before, limit, result]
            if payload.get('document_type'):
                arguments.extend([payload.get('provider') or None, payload['document_type']])
            elif payload.get('provider'):
                arguments.append(payload['provider'])
            cursor.callproc(self.pool.settings.oracle_mv_package + '.LISTA_PENDENCIAS',
                            arguments)
            keys = [column[0].upper() for column in result.description]
            required = {'CD_DOCUMENTO_CLINICO', 'CD_USUARIO', 'NM_OBJETO', 'TP_STATUS', 'DH_CRIACAO', 'SN_ASSINATURA'}
            if not required.issubset(keys):
                raise AppError('INVALID_PACKAGE_RESPONSE', 'Colunas da consulta incompatíveis com a integração.', 502)
            rows = result.fetchmany(limit + 1)
            records = [dict(zip(keys, row)) for row in rows]
        if scope == 'mine' and any(record['CD_USUARIO'] != username for record in records):
            raise AppError('FORBIDDEN', 'A consulta retornou documentos fora do seu usuário.', 403)
        if any(record['TP_STATUS'] != 'FECHADO' or record['SN_ASSINATURA'] != 'S' for record in records):
            raise AppError('INVALID_PACKAGE_RESPONSE', 'A consulta retornou documentos fora do filtro de pendências.', 502)
        ids = [record['CD_DOCUMENTO_CLINICO'] for record in records]
        if ids != sorted(set(ids), reverse=True) or (before is not None and any(identifier >= before for identifier in ids)):
            raise AppError('INVALID_PACKAGE_RESPONSE', 'Paginação incompatível com o contrato de consulta.', 502)
        documents = [{
            'id': record['CD_DOCUMENTO_CLINICO'], 'title': record['NM_OBJETO'] or 'Documento',
            'patient_name': record.get('NM_PACIENTE'), 'attendance_id': record.get('CD_ATENDIMENTO'),
            'provider_id': record.get('CD_PRESTADOR'), 'provider_name': record.get('NM_PRESTADOR'), 'mv_user': record['CD_USUARIO'],
            'discharge_at': record.get('DT_ALTA'),
            'created': record['DH_CRIACAO'], 'status': record['TP_STATUS'], 'can_transfer': False,
            'sector_id': None, 'sector_name': None,
        } for record in records[:limit]]
        if getattr(self.pool.settings, 'transfers_enabled', False):
            reasons = transfers.eligibility(connection, [doc['id'] for doc in documents])
            for doc in documents:
                reason = reasons.get(doc['id'], 'Documento não encontrado; atualize a consulta.')
                doc['transfer_block_reason'] = reason
                doc['can_transfer'] = reason is None
        return {'documents': documents, 'next_cursor': documents[-1]['id'] if len(records) > limit else None}

    def file(self, document_id, session, request_id):
        self.sessions.resolve(session)
        raise AppError('FILE_INTEGRATION_PENDING', 'Leitura de PDF ainda não integrada.', 503)
