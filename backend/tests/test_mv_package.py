from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.app.core.errors import AppError
from backend.app.infrastructure.oracle.mv_gateway import MVPackageGateway, Sessions


def fixture():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ('Nome de teste',)
    cursor.fetchall.return_value = [('TEST', 'Nome de teste', 'N', 'N')]
    cursor.description = [(key,) for key in ('CD_DOCUMENTO_CLINICO', 'CD_USUARIO', 'NM_OBJETO', 'TP_STATUS', 'DH_CRIACAO', 'SN_ASSINATURA')]
    cursor.fetchmany.return_value = [(identifier, 'TEST', 'Documento', 'FECHADO', datetime(2026, 10, 9), 'S') for identifier in (3, 2, 1)]

    @contextmanager
    def connection(request_id):
        yield conn

    pool = SimpleNamespace(connection=connection, settings=SimpleNamespace(oracle_mv_package='SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA', session_ttl_seconds=3600, transfers_enabled=False))
    gateway = MVPackageGateway(pool)
    return gateway, conn, cursor


def test_refcursor_uses_authenticated_username_and_inclusive_end_of_day():
    gateway, conn, cursor = fixture()
    token = gateway.sessions.issue('TEST', 3600)
    result = gateway.call('documents.list', {'start': '2026-10-01', 'end': '2026-10-09', 'limit': 2}, token, 'request')
    args = cursor.callproc.call_args.args
    assert args[0] == 'SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.LISTA_PENDENCIAS'
    assert args[1][0] == 'TEST'
    assert args[1][2] == datetime(2026, 10, 9, 23, 59, 59)
    assert [doc['id'] for doc in result['documents']] == [3, 2]
    assert args[1][3:6] == ['MEUS', None, 2]
    assert result['documents'][1]['status'] == 'FECHADO'
    assert result['next_cursor'] == 2
    conn.commit.assert_not_called()


def test_provider_filter_is_bound_to_oracle_with_pagination():
    gateway, conn, cursor = fixture()
    token = gateway.sessions.issue('TEST', 3600)
    gateway.call('documents.list', {'start': '2026-10-01', 'end': '2026-10-09',
                                  'provider': "José O'Neil", 'before': 10}, token, 'request')
    args = cursor.callproc.call_args.args[1]
    assert args[4] == 10
    assert args[7] == "José O'Neil"
    conn.commit.assert_not_called()


def test_pagination_is_sent_to_oracle_and_rejects_incompatible_results():
    gateway, conn, cursor = fixture()
    token = gateway.sessions.issue('TEST', 3600)
    payload = {'start': '2026-10-01', 'end': '2026-10-09', 'limit': 2, 'before': 2}
    cursor.fetchmany.return_value = cursor.fetchmany.return_value[-1:]
    result = gateway.call('documents.list', payload, token, 'request')
    assert [doc['id'] for doc in result['documents']] == [1]
    assert result['next_cursor'] is None
    assert cursor.callproc.call_args.args[1][4:6] == [2, 2]
    cursor.fetchmany.assert_called_with(3)
    cursor.fetchmany.return_value = [(3, 'TEST', 'Documento', 'FECHADO', datetime(2026, 10, 9), 'S')]
    with pytest.raises(AppError) as error:
        gateway.call('documents.list', payload, token, 'request')
    assert error.value.code == 'INVALID_PACKAGE_RESPONSE'


def test_global_scope_is_available_to_authenticated_nonmaster():
    gateway, conn, cursor = fixture()
    token = gateway.sessions.issue('OTHER', 3600)
    result = gateway.call('documents.list', {'start': '2026-10-01', 'end': '2026-10-09', 'scope': 'all'}, token, 'request')
    assert len(result['documents']) == 3
    assert cursor.callproc.call_args.args[1][0] == 'OTHER'
    assert cursor.callproc.call_args.args[1][3] == 'TODOS'
    assert gateway.user('OTHER', 'Nome')['is_master'] is False
    conn.commit.assert_not_called()


@pytest.mark.parametrize('status,signature', [('ABERTO', 'S'), ('ASSINADO', 'S'), ('CANCELADO', 'S'), ('FECHADO', 'N')])
def test_both_scopes_reject_results_outside_pending_signature_contract(status, signature):
    gateway, conn, cursor = fixture()
    token = gateway.sessions.issue('TEST', 3600)
    cursor.fetchmany.return_value = [(3, 'TEST', 'Documento', status, datetime(2026, 10, 9), signature)]
    for scope in ('all', 'mine'):
        with pytest.raises(AppError) as error:
            gateway.call('documents.list', {'start': '2026-10-01', 'end': '2026-10-09', 'scope': scope}, token, 'request')
        assert error.value.code == 'INVALID_PACKAGE_RESPONSE'


def test_out_of_scope_and_mutations_are_rejected():
    gateway, conn, cursor = fixture()
    token = gateway.sessions.issue('OTHER', 3600)
    with pytest.raises(AppError) as error:
        gateway.call('documents.list', {'start': '2026-10-01', 'end': '2026-10-09'}, token, 'request')
    assert error.value.status == 403
    cursor.callproc.reset_mock()
    with pytest.raises(AppError):
        gateway.call('transfers.create', {}, token, 'request')
    cursor.callproc.assert_not_called()
    conn.commit.assert_not_called()


def test_login_preserves_institutional_auth_and_session_revocation():
    gateway, conn, cursor = fixture()
    result = gateway.call('auth.login', {'username': ' test ', 'password': 'example', 'ttl_seconds': 3600}, None, 'request')
    assert result['user']['username'] == 'TEST'
    assert result['user']['is_master'] is False
    assert cursor.execute.call_args.kwargs['expected'] == 'TESTEXAMPLE'.ljust(30, 'K')
    assert gateway.sessions.resolve(result['token']) == 'TEST'
    gateway.call('auth.logout', {}, result['token'], 'request')
    with pytest.raises(AppError):
        gateway.sessions.resolve(result['token'])
    conn.commit.assert_not_called()


def test_disabled_user_loses_session_and_expired_session_is_rejected():
    gateway, conn, cursor = fixture()
    token = gateway.sessions.issue('TEST', 3600)
    cursor.fetchone.return_value = None
    with pytest.raises(AppError):
        gateway.call('auth.session', {}, token, 'request')
    with pytest.raises(AppError):
        gateway.sessions.resolve(token)
    store = Sessions()
    expired = store.issue('TEST', -1)
    with pytest.raises(AppError):
        store.resolve(expired)

@pytest.mark.parametrize('value', ['20/10/2026 14:35:12', '20/10/2026', None])
def test_discharge_comes_from_pending_cursor_without_extra_query(value):
    gateway, conn, cursor = fixture()
    cursor.description += [('DT_ALTA',)]
    cursor.fetchmany.return_value = [(3, 'TEST', 'Documento', 'FECHADO', datetime(2026, 10, 9), 'S', value)]
    result = gateway.documents(conn, cursor, 'TEST', {'start':'2026-10-01', 'end':'2026-10-21'})
    assert result['documents'][0]['discharge_at'] == value
    cursor.execute.assert_not_called()
    conn.commit.assert_not_called()
