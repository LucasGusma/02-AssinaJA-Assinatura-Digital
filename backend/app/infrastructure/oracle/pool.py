"""Synchronous Thick pool: one per worker, no shared connection across requests."""
from contextlib import contextmanager

import oracledb

from backend.app.core.config import Settings


class OraclePool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool = None

    def start(self):
        settings = self.settings
        oracledb.init_oracle_client(lib_dir=settings.oracle_client_dir)
        if oracledb.is_thin_mode():
            raise RuntimeError('Oracle Thick é obrigatório')
        self.pool = oracledb.create_pool(
            user=settings.db_user, password=settings.db_password.get_secret_value(),
            dsn=settings.db_dsn, min=settings.oracle_pool_min, max=settings.oracle_pool_max,
            increment=1, getmode=oracledb.POOL_GETMODE_TIMEDWAIT,
            wait_timeout=settings.oracle_pool_wait_ms, timeout=60,
            tcp_connect_timeout=10, retry_count=0, stmtcachesize=30,
        )

    @contextmanager
    def connection(self, request_id: str):
        if self.pool is None:
            raise RuntimeError('Pool não inicializado')
        with self.pool.acquire() as connection:
            connection.call_timeout = self.settings.oracle_call_timeout_ms
            connection.autocommit = False
            connection.module = 'AssinaJA'
            connection.action = request_id[:32]
            # Package authenticates the supplied opaque session token. No user ID
            # from the browser is ever used as the Oracle security identity.
            connection.client_identifier = ''
            try:
                yield connection
            finally:
                connection.rollback()
                connection.client_identifier = ''
                connection.action = ''
                connection.module = ''

    def close(self):
        if self.pool is not None:
            self.pool.close()
            self.pool = None
