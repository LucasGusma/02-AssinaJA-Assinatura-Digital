"""Install additive access objects; refuses to overwrite an existing installation."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool

pool = OraclePool(Settings())
pool.start()
try:
    with pool.connection('install-access') as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME IN ('AJA_PERMISSAO','AJA_AUDITORIA','AJA_AUDITORIA_SEQ','PKG_ASSINAJA_ACESSO')")
        if cursor.fetchone()[0]:
            raise SystemExit('Access objects already exist; inspect before applying a new migration.')
        source = (Path(__file__).resolve().parents[1] / 'database/migrations/003_access.sql').read_text(encoding='utf-8')
        for statement in source.split('\n/\n'):
            if statement.strip():
                cursor.execute(statement.strip().removesuffix('/').strip())
        cursor.execute("SELECT TYPE,LINE,POSITION,TEXT FROM USER_ERRORS WHERE NAME='PKG_ASSINAJA_ACESSO' ORDER BY SEQUENCE")
        errors = cursor.fetchall()
        if errors:
            print(errors)
            raise SystemExit('Compilation failed; DDL objects retained for repair.')
        connection.commit()
        print('Access package compiled; no clinical records changed.')
finally:
    pool.close()
