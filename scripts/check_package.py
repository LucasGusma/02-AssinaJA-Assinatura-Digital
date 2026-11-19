"""Read-only contract check; no patient rows or credentials are printed."""
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oracledb
from backend.app.core.config import Settings

s = Settings()
try:
    oracledb.init_oracle_client(lib_dir=s.oracle_client_dir)
    with oracledb.connect(user=s.db_user, password=s.db_password.get_secret_value(), dsn=s.db_dsn,
                         tcp_connect_timeout=10, retry_count=0) as conn:
        conn.call_timeout = 15000
        with conn.cursor() as cur:
            cur.execute('SET TRANSACTION READ ONLY')
            cur.execute("SELECT object_name,status FROM all_objects WHERE owner=:owner AND object_name=:name AND object_type IN ('PACKAGE','PACKAGE BODY')", owner='APP_SCHEMA', name='PKG_GERENCIADOR_ASSINATURA')
            print('Package objects:', cur.fetchall())
            cur.execute("SELECT object_name,argument_name,position,in_out,data_type FROM all_arguments WHERE owner=:owner AND package_name=:name ORDER BY object_name,sequence", owner='APP_SCHEMA', name='PKG_GERENCIADOR_ASSINATURA')
            print('Arguments:', cur.fetchall())
            cur.execute("SELECT NM_USUARIO FROM DBASGU.USUARIOS WHERE 1=0 AND SN_ATIVO='S' AND DBASGU.CRIPTO_DESCRIPTO(CD_SENHA, 'SMVCRIPTON')=:expected", expected='schema-check')
            print('Institutional authentication SQL: accessible')
            with conn.cursor() as result:
                cur.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.LISTA_DOCUMENTOS', ['__ASSINAJA_SCHEMA_CHECK__', datetime(2026, 10, 9), datetime(2026, 10, 9), result])
                print('REF CURSOR columns:', [column[0] for column in result.description])
                print('Schema check complete (no clinical rows fetched).')
except oracledb.Error as error:
    print('Oracle diagnostic failed:', getattr(error.args[0], 'full_code', 'ORACLE_ERROR'))
    raise SystemExit(1)
