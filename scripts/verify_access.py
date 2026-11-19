"""Validate directory, authorization and atomic audit; roll back permission probes."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oracledb
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool
from backend.app.infrastructure.oracle.access import profile, query, PACKAGE

pool = OraclePool(Settings())
pool.start()
try:
    with pool.connection('verify-access') as c, c.cursor() as q:
        master = profile(c, q, 'ADMIN')
        assert master['is_master']
        sectors = query(c, q, 'SETORES', ['ADMIN'])
        seen = set()
        for sector in sectors:
            rows = query(c, q, 'USUARIOS', ['ADMIN', sector[0]])
            seen.update(row[0] for row in rows)
        q.execute("SELECT CD_USUARIO FROM DBASGU.USUARIOS WHERE SN_ATIVO='S'")
        expected = {r[0] for r in q.fetchall()}
        assert seen == expected, 'Directory must cover every active account'
        other = next(u for u in seen if u != 'ADMIN')
        try:
            q.callproc(PACKAGE + 'PERMISSAO', [other, 'ADMIN', 'S', 'verification-denied'])
            raise AssertionError('Nonmaster write accepted')
        except oracledb.Error as error:
            assert error.args[0].code == 20002
        c.rollback()
        q.execute('SELECT COUNT(*) FROM APP_SCHEMA.AJA_AUDITORIA')
        baseline = q.fetchone()[0]
        enabled = 'N' if master['can_transfer'] else 'S'
        q.callproc(PACKAGE + 'PERMISSAO', ['ADMIN', 'ADMIN', enabled, 'verification-rollback'])
        assert profile(c, q, 'ADMIN')['can_transfer'] != master['can_transfer']
        events = query(c, q, 'AUDITORIA', ['ADMIN', None])
        assert events[0][2] == 'ADMIN' and events[0][4] == 'PERMISSAO'
        assert events[0][9] == 'ADMIN' and events[0][3] and events[0][10]
        c.rollback()
        q.execute('SELECT COUNT(*) FROM APP_SCHEMA.AJA_AUDITORIA')
        assert q.fetchone()[0] == baseline
        assert profile(c, q, 'ADMIN')['can_transfer'] == master['can_transfer']
        print('Active directory coverage, master authorization and permission/audit rollback: passed.')
finally:
    pool.close()
