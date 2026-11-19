"""Read-only verification of scope/filter/pagination; never prints clinical rows."""
from datetime import date, datetime, time, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool


def main():
    settings = Settings()
    pool = OraclePool(settings)
    pool.start()
    try:
        with pool.connection('verify-pending-scopes') as connection:
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                # Use an existing active account only as the procedure scope
                # parameter. This check neither creates an app session nor logs in.
                cursor.execute("SELECT CD_USUARIO FROM DBASGU.USUARIOS WHERE SN_ATIVO='S' AND ROWNUM=1")
                account = cursor.fetchone()
                if not account:
                    raise RuntimeError('Nenhum usuário ativo para conferir o contrato.')
                username = account[0]
                today = date(2026, 10, 9)
                start = datetime.combine(today - timedelta(days=6), time.min)
                end = datetime.combine(today, time(23, 59, 59))

                def read(scope, user, before=None):
                    with connection.cursor() as result:
                        cursor.callproc(settings.oracle_mv_package + '.LISTA_PENDENCIAS', [user, start, end, scope, before, 50, result])
                        keys = [column[0] for column in result.description]
                        rows = [dict(zip(keys, row)) for row in result.fetchmany(52)]
                    assert len(rows) <= 51
                    assert all(row['TP_STATUS'] == 'FECHADO' and row['SN_ASSINATURA'] == 'S' for row in rows)
                    ids = [row['CD_DOCUMENTO_CLINICO'] for row in rows]
                    assert ids == sorted(set(ids), reverse=True)
                    assert before is None or all(identifier < before for identifier in ids)
                    assert scope != 'MEUS' or all(row['CD_USUARIO'] == user for row in rows)
                    return rows

                first = read('TODOS', username)
                print('Visão geral: filtro FECHADO + assinatura S, ordem e limite conferidos.')
                if len(first) == 51:
                    read('TODOS', username, first[49]['CD_DOCUMENTO_CLINICO'])
                    print('Próxima página: cursor conferido.')
                sample_user = next((row['CD_USUARIO'] for row in first if row['CD_USUARIO']), username)
                read('MEUS', sample_user)
                print('Meus documentos: escopo de usuário e filtro de pendências conferidos.')
                print('Somente leitura; nenhum dado clínico exibido ou alterado.')
    finally:
        pool.close()


if __name__ == '__main__':
    main()
