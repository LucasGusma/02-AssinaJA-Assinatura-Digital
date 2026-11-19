import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.app.core.config import Settings
from backend.app.core.errors import AppError
from backend.app.infrastructure.oracle.gateway import OracleGateway
from backend.app.infrastructure.oracle.pool import OraclePool


def pool_and_connection(reply):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.var.return_value.getvalue.return_value = json.dumps(reply)

    @contextmanager
    def acquire(request_id):
        try:
            yield connection
        finally:
            connection.rollback()

    pool = SimpleNamespace(connection=acquire, settings=SimpleNamespace(oracle_package_routine='TEST_PKG.RUN'))
    return pool, connection, cursor


def test_gateway_binds_json_and_commits_only_success():
    pool, connection, cursor = pool_and_connection({'ok': True, 'data': {'sectors': []}})
    assert OracleGateway(pool).call('directory.sectors', {}, 'opaque-session', 'request') == {'sectors': []}
    connection.commit.assert_called_once()
    assert cursor.callproc.call_args.args[0] == 'TEST_PKG.RUN'
    source = json.loads(cursor.var.return_value.setvalue.call_args.args[1])
    assert source['session'] == 'opaque-session'


def test_gateway_rolls_back_business_failure_and_masks_message():
    pool, connection, cursor = pool_and_connection({'ok': False, 'error': {'code': 'FORBIDDEN', 'message': 'private SQL secret'}})
    with pytest.raises(AppError) as captured:
        OracleGateway(pool).call('permissions.update', {}, 'session', 'request')
    assert captured.value.status == 403
    assert 'secret' not in str(captured.value)
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()


def test_invalid_package_response_does_not_commit():
    pool, connection, cursor = pool_and_connection({'ok': True, 'data': []})
    with pytest.raises(AppError) as captured:
        OracleGateway(pool).call('auth.login', {}, None, 'request')
    assert captured.value.status == 502
    connection.commit.assert_not_called()


def test_login_rejection_preserves_security_counters():
    pool, connection, cursor = pool_and_connection({'ok': False, 'error': {'code': 'INVALID_CREDENTIALS'}})
    with pytest.raises(AppError) as captured:
        OracleGateway(pool).call('auth.login', {'username': 'TEST', 'password': 'test'}, None, 'request')
    assert captured.value.status == 401
    connection.commit.assert_called_once()


def test_malformed_transfer_success_is_rejected_before_commit():
    pool, connection, cursor = pool_and_connection({'ok': True, 'data': {}})
    with pytest.raises(AppError) as captured:
        OracleGateway(pool).call('transfers.create', {}, 'session', 'request')
    assert captured.value.status == 502
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()


def test_pool_initializes_thick_once_and_cleans_connection_after_failure():
    settings = Settings(_env_file=None, oracle_client_dir='C:/oracle/test', db_user='test', db_password='test', db_dsn='test')
    with patch('backend.app.infrastructure.oracle.pool.oracledb') as driver:
        driver.is_thin_mode.return_value = False
        pool = OraclePool(settings)
        pool.start()
        connection = driver.create_pool.return_value.acquire.return_value.__enter__.return_value
        with pytest.raises(RuntimeError):
            with pool.connection('request'):
                raise RuntimeError('simulated')
        driver.init_oracle_client.assert_called_once_with(lib_dir='C:/oracle/test')
        connection.rollback.assert_called_once()
        assert connection.client_identifier == ''
        pool.close()
        driver.create_pool.return_value.close.assert_called_once()
