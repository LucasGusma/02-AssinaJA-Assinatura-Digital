"""Prepare or apply the additive pending-query procedure, preserving existing code.

Default: read source and save original/proposed DDL. --apply verifies no source
changed since preparation, compiles, checks errors and restores on failure.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oracledb
from backend.app.core.config import ROOT, Settings

OWNER, PACKAGE = 'APP_SCHEMA', 'PKG_GERENCIADOR_ASSINATURA'
OUTPUT = ROOT / 'database' / 'migrations' / '002_prepared'


def read_source(cursor):
    cursor.execute("SELECT TYPE,TEXT FROM ALL_SOURCE WHERE OWNER=:owner AND NAME=:name AND TYPE IN ('PACKAGE','PACKAGE BODY') ORDER BY TYPE,LINE", owner=OWNER, name=PACKAGE)
    source = {'PACKAGE': '', 'PACKAGE BODY': ''}
    for kind, text in cursor:
        source[kind] += text
    if not all(source.values()):
        raise RuntimeError('Package original não encontrada.')
    return source


def fingerprint(source):
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


def ddl(kind, text):
    return re.sub(r'^PACKAGE\s+(BODY\s+)?\w+',
                  lambda match: 'CREATE OR REPLACE PACKAGE ' + ('BODY ' if kind == 'PACKAGE BODY' else '') + OWNER + '.' + PACKAGE,
                  text, count=1, flags=re.I)


def require_valid(cursor):
    cursor.execute("SELECT TYPE,LINE,POSITION,TEXT FROM ALL_ERRORS WHERE OWNER=:owner AND NAME=:name AND ATTRIBUTE='ERROR' ORDER BY TYPE,SEQUENCE", owner=OWNER, name=PACKAGE)
    errors = cursor.fetchall()
    if errors:
        raise RuntimeError(str(errors))
    cursor.execute("SELECT COUNT(*) FROM ALL_OBJECTS WHERE OWNER=:owner AND OBJECT_NAME=:name AND OBJECT_TYPE IN ('PACKAGE','PACKAGE BODY') AND STATUS='VALID'", owner=OWNER, name=PACKAGE)
    if cursor.fetchone()[0] != 2:
        raise RuntimeError('Package não está válida.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    settings = Settings()
    oracledb.init_oracle_client(lib_dir=settings.oracle_client_dir)
    with oracledb.connect(user=settings.db_user, password=settings.db_password.get_secret_value(),
                         dsn=settings.db_dsn, tcp_connect_timeout=10, retry_count=0) as connection:
        connection.call_timeout = 30000
        with connection.cursor() as cursor:
            require_valid(cursor)
            source = read_source(cursor)
            if not args.apply:
                if OUTPUT.exists():
                    raise RuntimeError('Preparação já existe; preservada para revisão.')
                if 'lista_pendencias' in source['PACKAGE'].lower():
                    raise RuntimeError('Procedure já existe; revisar antes de substituir.')
                OUTPUT.mkdir(parents=True)
                for kind, suffix, fragment in [('PACKAGE', 'pks', 'spec'), ('PACKAGE BODY', 'pkb', 'body')]:
                    original = ddl(kind, source[kind])
                    extension = (ROOT / 'database' / 'migrations' / f'002_lista_pendencias_{fragment}.sql').read_text(encoding='utf-8')
                    proposed, count = re.subn(r'END\s+pkg_gerenciador_assinatura\s*;\s*$', lambda match: extension + '\n' + match[0], original, count=1, flags=re.I)
                    if count != 1:
                        raise RuntimeError('Final da package não identificado.')
                    (OUTPUT / f'original.{suffix}.sql').write_text(original, encoding='utf-8')
                    (OUTPUT / f'proposed.{suffix}.sql').write_text(proposed, encoding='utf-8')
                (OUTPUT / 'source.sha256').write_text(fingerprint(source), encoding='ascii')
                print('DDL original e proposto preparados; nenhuma alteração Oracle realizada.')
                return
            if fingerprint(source) != (OUTPUT / 'source.sha256').read_text(encoding='ascii'):
                raise RuntimeError('Fonte Oracle mudou após a preparação; aplicação cancelada.')
            try:
                for suffix in ('pks', 'pkb'):
                    cursor.execute((OUTPUT / f'proposed.{suffix}.sql').read_text(encoding='utf-8'))
                require_valid(cursor)
            except Exception:
                for suffix in ('pks', 'pkb'):
                    cursor.execute((OUTPUT / f'original.{suffix}.sql').read_text(encoding='utf-8'))
                require_valid(cursor)
                print('Falha na compilação: package original restaurada.')
                raise
            print('LISTA_PENDENCIAS adicionada. Package e corpo VALID; nenhum UPDATE clínico executado.')


if __name__ == '__main__':
    try:
        main()
    except oracledb.Error as error:
        print('Oracle:', getattr(error.args[0], 'full_code', 'ORACLE_ERROR'))
        raise SystemExit(1)
