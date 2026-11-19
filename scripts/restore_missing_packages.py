"""Restore missing application packages in smlmv without replacing existing objects."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool

root = Path(__file__).resolve().parents[1]
pool = OraclePool(Settings())
pool.start()
try:
    with pool.connection('restore-packages') as connection, connection.cursor() as cursor:
        cursor.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM DUAL")
        if cursor.fetchone()[0] != 'smlmv':
            raise SystemExit('Restore restricted to confirmed homologation database smlmv.')
        cursor.execute("SELECT COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME='PKG_GERENCIADOR_ASSINATURA'")
        if cursor.fetchone()[0]:
            raise SystemExit('Document package already exists; nothing overwritten.')
        for suffix in ('pks', 'pkb'):
            source = root / 'database/migrations/002_prepared' / f'proposed.{suffix}.sql'
            cursor.execute(source.read_text(encoding='utf-8'))
        cursor.execute("SELECT TYPE,LINE,POSITION,TEXT FROM USER_ERRORS WHERE NAME='PKG_GERENCIADOR_ASSINATURA' ORDER BY SEQUENCE")
        errors = cursor.fetchall()
        if errors:
            print(errors)
            raise SystemExit('Compilation failed. Inspect objects before retrying.')
        print('Document package restored. No clinical DML executed.')
finally:
    pool.close()
