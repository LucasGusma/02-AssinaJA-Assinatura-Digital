"""Move transfer routines into the existing manager; never create another package."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool

MAIN = 'PKG_GERENCIADOR_ASSINATURA'
OLD = 'PKG_ASSINAJA_TRANSF'
pool = OraclePool(Settings())
pool.start()
try:
    with pool.connection('consolidate-transfers') as connection, connection.cursor() as cursor:
        cursor.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM DUAL")
        if cursor.fetchone()[0].lower() != 'smlmv':
            raise SystemExit('Only confirmed homologation allowed.')
        def source(name, kind):
            cursor.execute('SELECT TEXT FROM USER_SOURCE WHERE NAME=:name AND TYPE=:kind ORDER BY LINE', name=name, kind=kind)
            text = ''.join(row[0] for row in cursor)
            if not text:
                raise RuntimeError('Required existing package missing: ' + name)
            return text
        originals = {kind: source(MAIN, kind) for kind in ('PACKAGE', 'PACKAGE BODY')}
        old = {kind: source(OLD, kind) for kind in originals}
        if re.search(r'PROCEDURE\s+transferir\b', originals['PACKAGE'], re.I):
            raise SystemExit('Already consolidated; inspect before retrying.')
        cursor.execute("SELECT NAME,TYPE FROM USER_DEPENDENCIES WHERE REFERENCED_NAME=:name AND NAME<>:name", name=OLD)
        if cursor.fetchall():
            raise SystemExit('Other database objects depend on old package; inspect first.')
        folder = Path(__file__).resolve().parents[1] / 'database/migrations/007_consolidated_transfers'
        folder.mkdir(exist_ok=False)
        proposed = {}
        for kind in originals:
            suffix = 'pks' if kind == 'PACKAGE' else 'pkb'
            for label, content in [('original', originals[kind]), ('removed', old[kind])]:
                (folder / f'{label}.{suffix}.backup').write_text(content, encoding='utf-8')
            inner = re.sub(r'^PACKAGE\s+(?:BODY\s+)?(?:APP_SCHEMA\.)?PKG_ASSINAJA_TRANSF\s+(?:AUTHID\s+DEFINER\s+)?(?:AS|IS)\b', '', old[kind], count=1, flags=re.I)
            if inner == old[kind]:
                raise RuntimeError('Unexpected source header')
            inner, count = re.subn(r'END\s*(?:PKG_ASSINAJA_TRANSF)?\s*;\s*$', '', inner, count=1, flags=re.I)
            if count != 1:
                raise RuntimeError('Unexpected source ending')
            merged, count = re.subn(r'END\s+PKG_GERENCIADOR_ASSINATURA\s*;\s*$', lambda _: inner + '\nEND ' + MAIN + ';\n', originals[kind], count=1, flags=re.I)
            if count != 1:
                raise RuntimeError('Unexpected manager ending')
            proposed[kind] = 'CREATE OR REPLACE ' + merged
            (folder / f'current.{suffix}.sql').write_text(proposed[kind], encoding='utf-8')
        try:
            for statement in proposed.values():
                cursor.execute(statement)
            cursor.execute("SELECT LINE,TEXT FROM USER_ERRORS WHERE NAME=:name AND ATTRIBUTE='ERROR'", name=MAIN)
            errors = cursor.fetchall()
            if errors:
                raise RuntimeError(str(errors))
            cursor.execute('SELECT APP_SCHEMA.' + MAIN + '.BLOQUEIO(-1) FROM DUAL')
            assert cursor.fetchone()[0]
        except Exception:
            for statement in originals.values():
                cursor.execute('CREATE OR REPLACE ' + statement)
            raise
        cursor.execute('DROP PACKAGE APP_SCHEMA.' + OLD)
        cursor.execute("SELECT COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME=:name AND OBJECT_TYPE='PACKAGE'", name=OLD+'_HML')
        if cursor.fetchone()[0]:
            cursor.execute('DROP PACKAGE APP_SCHEMA.' + OLD + '_HML')
        print('Existing manager updated; old transfer packages removed. No clinical DML executed.')
finally:
    pool.close()
