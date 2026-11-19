"""Real smlmv transfer test. All transactional mutations are rolled back."""
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oracledb
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool

pool = OraclePool(Settings())
pool.start()
try:
    with pool.connection('verify-transfers') as c, c.cursor() as q:
        q.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM DUAL")
        assert q.fetchone()[0] == 'smlmv'
        q.execute("""SELECT * FROM (SELECT d.CD_DOCUMENTO_CLINICO,d.CD_USUARIO,d.CD_PRESTADOR,d.CD_ATENDIMENTO,d.DH_CRIACAO
         FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO d
         WHERE d.TP_STATUS='FECHADO' AND d.DH_CRIACAO>=SYSDATE-31
         AND EXISTS (SELECT 1 FROM USUARIO_BANCO.PRE_MED p WHERE p.CD_DOCUMENTO_CLINICO=d.CD_DOCUMENTO_CLINICO)
         AND SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.BLOQUEIO(d.CD_DOCUMENTO_CLINICO) IS NULL
         ORDER BY d.CD_DOCUMENTO_CLINICO DESC) WHERE ROWNUM=1""")
        row = q.fetchone()
        if row is None:
            raise SystemExit('No eligible sample found; no transfer tested.')
        document, old_user, old_provider, attendance, created = row
        q.execute("""SELECT * FROM (SELECT u.CD_USUARIO,p.CD_PRESTADOR FROM DBASGU.USUARIOS u
         JOIN USUARIO_BANCO.PRESTADOR p ON p.CD_PRESTADOR=u.CD_PRESTADOR
         WHERE u.SN_ATIVO='S' AND p.TP_SITUACAO='A' AND u.CD_USUARIO<>:old_user
         AND p.CD_PRESTADOR<>:old_provider AND p.CD_TIP_PRESTA=(SELECT CD_TIP_PRESTA FROM USUARIO_BANCO.PRESTADOR WHERE CD_PRESTADOR=:old_provider)
         ORDER BY u.CD_USUARIO) WHERE ROWNUM=1""", old_user=old_user, old_provider=old_provider)
        recipient, provider = q.fetchone()

        def appears_for(username):
            with c.cursor() as proc, c.cursor() as result:
                proc.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.LISTA_PENDENCIAS',
                              [username, created, created, 'MEUS', document + 1, 1, result])
                record = result.fetchone()
                return record is not None and record[0] == document

        assert appears_for(old_user) and not appears_for(recipient)

        def snapshot():
            result = []
            for sql, binds in [
                ('SELECT * FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO WHERE CD_DOCUMENTO_CLINICO=:id', {'id': document}),
                ('SELECT CD_PRE_MED,NM_USUARIO,CD_PRESTADOR,FL_IMPRESSO,SN_FECHADO,CD_DOCUMENTO_CLINICO FROM USUARIO_BANCO.PRE_MED WHERE CD_DOCUMENTO_CLINICO=:id', {'id': document}),
                ('SELECT CD_PRESTADOR FROM USUARIO_BANCO.ATENDIME WHERE CD_ATENDIMENTO=:id', {'id': attendance}),
                ('SELECT COUNT(*) FROM APP_SCHEMA.AJA_AUDITORIA', {}),
                ('SELECT COUNT(*) FROM APP_SCHEMA.AJA_TRANSFERENCIA', {}),
                ("SELECT SN_TRANSFERIR FROM APP_SCHEMA.AJA_PERMISSAO WHERE CD_USUARIO='ADMIN'", {}),
            ]:
                q.execute(sql, binds); result.append(q.fetchall())
            return result

        before = snapshot()
        q.callproc('APP_SCHEMA.PKG_ASSINAJA_ACESSO.PERMISSAO', ['ADMIN', 'ADMIN', 'N', 'test-rollback'])
        try:
            q.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.TRANSFERIR', ['ADMIN', document, old_user, recipient,
                       'Teste sem permissao', str(uuid4()), 'test-rollback', q.var(oracledb.DB_TYPE_NUMBER)])
            raise AssertionError('Unauthorized transfer accepted')
        except oracledb.Error as error:
            assert error.args[0].code == 20010
        q.callproc('APP_SCHEMA.PKG_ASSINAJA_ACESSO.PERMISSAO', ['ADMIN', 'ADMIN', 'S', 'test-rollback'])
        with c.cursor() as proc, c.cursor() as result:
            proc.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.DESTINATARIOS', ['ADMIN', document, recipient, result])
            assert any(r[0] == recipient for r in result.fetchall())
        output = q.var(oracledb.DB_TYPE_NUMBER)
        key = str(uuid4())
        arguments = ['ADMIN', document, old_user, recipient, 'Teste de integracao com rollback', key, 'test-rollback', output]
        q.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.TRANSFERIR', arguments)
        event = output.getvalue()
        q.execute('SELECT CD_USUARIO,CD_PRESTADOR FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO WHERE CD_DOCUMENTO_CLINICO=:id', id=document)
        assert q.fetchone() == (recipient, provider)
        assert not appears_for(old_user) and appears_for(recipient)
        q.execute('SELECT NM_USUARIO,CD_PRESTADOR FROM USUARIO_BANCO.PRE_MED WHERE CD_DOCUMENTO_CLINICO=:id', id=document)
        assert q.fetchone() == (recipient, provider)
        q.execute("SELECT CD_AUTOR,CD_ORIGEM,CD_DESTINO,NM_AUTOR,NM_ORIGEM,NM_DESTINO FROM APP_SCHEMA.AJA_AUDITORIA WHERE ID=:id", id=event)
        audit = q.fetchone()
        assert audit[:3] == ('ADMIN', old_user, recipient) and all(audit[3:])
        q.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.TRANSFERIR', arguments)
        assert output.getvalue() == event
        try:
            q.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.TRANSFERIR', [*arguments[:5], str(uuid4()), *arguments[6:]])
            raise AssertionError('Stale owner accepted')
        except oracledb.Error as error:
            assert error.args[0].code == 20013
        c.rollback()
        assert snapshot() == before
        # Force an audit insertion failure after clinical DML, proving atomic rollback.
        q.callproc('APP_SCHEMA.PKG_ASSINAJA_ACESSO.PERMISSAO', ['ADMIN', 'ADMIN', 'S', 'test-rollback'])
        checkpoint = snapshot()
        try:
            q.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.TRANSFERIR', [*arguments[:5], str(uuid4()), 'x' * 100, output])
            raise AssertionError('Audit failure expected')
        except oracledb.Error as error:
            assert error.args[0].code == 12899
        assert snapshot() == checkpoint
        c.rollback()
        assert snapshot() == before
        print('Transfer, source synchronization, audit, idempotency, permission denial, stale owner and atomic rollback: passed.')
finally:
    pool.close()
