"""Type-by-type Oracle integration tests. Clinical data stay in memory; writes roll back."""
import json
import argparse
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oracledb
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool

MAPPING = {
    'ANEXO': ('ARQUIVO_ATENDIMENTO', None, None),
    'ANOENF': ('EVO_ENF', 'NM_USUARIO', 'CD_PRESTADOR'),
    'EVOMED': ('PRE_MED', 'NM_USUARIO', 'CD_PRESTADOR'),
    'MEDICA': ('PRE_MED', 'NM_USUARIO', 'CD_PRESTADOR'),
    'PRESCR': ('PRE_MED', 'NM_USUARIO', 'CD_PRESTADOR'),
    'ENFERM': ('PRE_MED', 'NM_USUARIO', 'CD_PRESTADOR'),
    'TRATMT': ('PRE_MED', 'NM_USUARIO', 'CD_PRESTADOR'),
    'AFERIC': ('COLETA_SINAL_VITAL', 'NM_USUARIO', 'CD_PRESTADOR'),
    'ALTMED': ('PW_REGISTRO_ALTA', 'CD_USUARIO', 'CD_PRESTADOR'),
    'AVALIA': ('PAGU_AVALIACAO', 'NM_USUARIO', None),
    'DIAEST': ('DIAGNOSTICO_ATENDIME', 'NM_USUARIO', None),
    'DIAENF': ('SAE_DIAGNOSTICO_REALIZADO', None, 'CD_PRESTADOR'),
    'HISENF': ('SAE_HISTORICO_ENFERMAGEM', None, 'CD_PRESTADOR'),
    'RESENF': ('PW_SAE_RESULTADO_ENFERMG_RLZD', None, 'CD_PRESTADOR'),
    'DOCELE': ('PW_EDITOR_CLINICO', None, None),
}
PACKAGE = 'SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.'
parser = argparse.ArgumentParser()
parser.add_argument('--types', default='')
parser.add_argument('--requested', action='store_true')
args_cli = parser.parse_args()
selected_types = set(args_cli.types.split(',')) if args_cli.types else set(MAPPING)
pool = OraclePool(Settings()); pool.start()
report_path = Path(__file__).resolve().parents[1] / 'data/transfer-types-results.json'
report = [r for r in json.loads(report_path.read_text()) if r['case'].split('/')[0] not in selected_types] if args_cli.types and report_path.exists() else []
try:
    with pool.connection('verify-type-matrix') as c, c.cursor() as q:
        c.call_timeout = 60000
        q.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM DUAL")
        if q.fetchone()[0] != 'smlmv':
            raise SystemExit('Only confirmed homologation allowed.')

        def rows(sql, **binds):
            q.execute(sql, binds)
            return [tuple(v.read() if isinstance(v, oracledb.LOB) else v for v in r) for r in q.fetchall()]

        coverage = rows("SELECT o.TP_OBJETO,a.TP_ATENDIMENTO,COUNT(*) FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO d JOIN USUARIO_BANCO.PAGU_OBJETO o ON o.CD_OBJETO=d.CD_OBJETO JOIN USUARIO_BANCO.ATENDIME a ON a.CD_ATENDIMENTO=d.CD_ATENDIMENTO WHERE d.DH_CRIACAO>=SYSDATE-31 AND d.TP_STATUS='FECHADO' AND o.SN_ASSINATURA='S' GROUP BY o.TP_OBJETO,a.TP_ATENDIMENTO")
        legacy = {'ANEXO': 16657221, 'ANOENF': 13986159, 'EVOMED': 17904230, 'MEDICA': 6832767}
        if args_cli.requested:
            legacy.update({'ANEXO': 19701650, 'DOCELE': 19701647})
        for kind, (table, user_column, provider_column) in MAPPING.items():
            if kind not in selected_types:
                continue
            for urgent in (False, True):
                label = kind + ('/urgencia' if urgent else '/outros')
                try:
                    if kind in legacy and urgent:
                        continue
                    if kind not in legacy and not any(k == kind and (a == 'U') == urgent for k, a, _ in coverage):
                        report.append({'case': label, 'result': 'no_sample'}); print(label, 'no sample', flush=True); continue
                    if kind in legacy:
                        sample = rows("SELECT CD_DOCUMENTO_CLINICO,CD_USUARIO,CD_PRESTADOR,CD_ATENDIMENTO,DH_CRIACAO FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO WHERE CD_DOCUMENTO_CLINICO=:id AND SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.BLOQUEIO(CD_DOCUMENTO_CLINICO) IS NULL", id=legacy[kind])
                    else:
                        sample = rows("""SELECT * FROM (SELECT d.CD_DOCUMENTO_CLINICO,d.CD_USUARIO,d.CD_PRESTADOR,
                         d.CD_ATENDIMENTO,d.DH_CRIACAO FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO d
                         JOIN USUARIO_BANCO.PAGU_OBJETO o ON o.CD_OBJETO=d.CD_OBJETO
                         JOIN USUARIO_BANCO.ATENDIME a ON a.CD_ATENDIMENTO=d.CD_ATENDIMENTO
                         WHERE o.TP_OBJETO=:kind AND d.DH_CRIACAO>=SYSDATE-31 AND d.TP_STATUS='FECHADO'
                         AND ((:urgent=1 AND a.TP_ATENDIMENTO='U') OR (:urgent=0 AND a.TP_ATENDIMENTO<>'U'))
                         AND SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.BLOQUEIO(d.CD_DOCUMENTO_CLINICO) IS NULL
                         ORDER BY d.CD_DOCUMENTO_CLINICO DESC) WHERE ROWNUM=1""", kind=kind, urgent=int(urgent))
                    if not sample:
                        report.append({'case': label, 'result': 'no_eligible_sample'})
                        print(label, 'no eligible sample', flush=True)
                        continue
                    document, old_user, old_provider, attendance, created = sample[0]
                    destination = rows("""SELECT * FROM (SELECT u.CD_USUARIO,p.CD_PRESTADOR FROM DBASGU.USUARIOS u
                     JOIN USUARIO_BANCO.PRESTADOR p ON p.CD_PRESTADOR=u.CD_PRESTADOR
                     WHERE u.SN_ATIVO='S' AND p.TP_SITUACAO='A' AND u.CD_USUARIO<>:old_user
                     AND p.CD_PRESTADOR<>:old_provider AND p.CD_TIP_PRESTA=(SELECT CD_TIP_PRESTA FROM USUARIO_BANCO.PRESTADOR WHERE CD_PRESTADOR=:old_provider)
                     ORDER BY u.CD_USUARIO) WHERE ROWNUM=1""", old_user=old_user, old_provider=old_provider)
                    if not destination:
                        report.append({'case': label, 'result': 'no_recipient'}); continue
                    recipient, provider = destination[0]

                    def snapshot():
                        return {
                            'document': rows('SELECT * FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO WHERE CD_DOCUMENTO_CLINICO=:id', id=document),
                            'origin': rows('SELECT * FROM USUARIO_BANCO.' + table + ' WHERE CD_DOCUMENTO_CLINICO=:id ORDER BY ROWID', id=document),
                            'attendance': rows('SELECT * FROM USUARIO_BANCO.ATENDIME WHERE CD_ATENDIMENTO=:id', id=attendance),
                            'billing': rows('SELECT * FROM USUARIO_BANCO.ITREG_AMB WHERE CD_ATENDIMENTO=:id ORDER BY ROWID', id=attendance),
                            'movements': rows('SELECT * FROM USUARIO_BANCO.MOV_PRESTADOR WHERE CD_ATENDIMENTO=:id ORDER BY ROWID', id=attendance),
                            'editor': rows('SELECT r.* FROM USUARIO_BANCO.EDITOR_REGISTRO r JOIN USUARIO_BANCO.PW_EDITOR_CLINICO e ON e.CD_EDITOR_REGISTRO=r.CD_REGISTRO WHERE e.CD_DOCUMENTO_CLINICO=:id ORDER BY r.CD_REGISTRO', id=document),
                            'snomed': rows('SELECT * FROM USUARIO_BANCO.SNOMEDCT_PACIENTE WHERE CD_DOCUMENTO_CLINICO=:id ORDER BY ROWID', id=document),
                            'audit': rows('SELECT COUNT(*) FROM APP_SCHEMA.AJA_AUDITORIA'),
                            'transfers': rows('SELECT COUNT(*) FROM APP_SCHEMA.AJA_TRANSFERENCIA'),
                        }

                    def personal(username):
                        with c.cursor() as proc, c.cursor() as result:
                            proc.callproc('SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.LISTA_PENDENCIAS',
                                          [username, created, created, 'MEUS', document + 1, 1, result])
                            r = result.fetchone()
                            return r is not None and r[0] == document

                    baseline = snapshot()
                    q.callproc('APP_SCHEMA.PKG_ASSINAJA_ACESSO.PERMISSAO', ['ADMIN', 'ADMIN', 'S', 'type-test-rollback'])
                    event = q.var(oracledb.DB_TYPE_NUMBER)
                    args = ['ADMIN', document, old_user, recipient, 'Homologacao de tipo com rollback', str(uuid4()), 'type-test-rollback', event]
                    assert personal(old_user) and not personal(recipient), 'personal scope before'
                    q.callproc(PACKAGE + 'TRANSFERIR', args)
                    after = snapshot()
                    assert not personal(old_user) and personal(recipient), 'personal scope after'
                    assert rows('SELECT CD_USUARIO,CD_PRESTADOR FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO WHERE CD_DOCUMENTO_CLINICO=:id', id=document) == [(recipient, provider)], 'document ownership'
                    for col, expected in ((user_column, recipient), (provider_column, provider)):
                        if col:
                            assert all(r[0] == expected for r in rows('SELECT ' + col + ' FROM USUARIO_BANCO.' + table + ' WHERE CD_DOCUMENTO_CLINICO=:id', id=document)), 'origin ownership'
                    for target, columns, changed in [('document', 'PW_DOCUMENTO_CLINICO', {'CD_USUARIO', 'CD_PRESTADOR'}), ('origin', table, {user_column, provider_column})]:
                        names = [r[0] for r in rows('SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE OWNER=\'USUARIO_BANCO\' AND TABLE_NAME=:t ORDER BY COLUMN_ID', t=columns)]
                        before_stable = [tuple(v for name, v in zip(names, r) if name not in changed) for r in baseline[target]]
                        after_stable = [tuple(v for name, v in zip(names, r) if name not in changed) for r in after[target]]
                        assert before_stable == after_stable, target + ' unrelated fields changed'
                    for target in ('attendance', 'billing', 'movements', 'snomed', 'editor'):
                        assert baseline[target] == after[target], target + ' changed'
                    audit = rows('SELECT CD_AUTOR,CD_ORIGEM,CD_DESTINO,NM_AUTOR,NM_ORIGEM,NM_DESTINO FROM APP_SCHEMA.AJA_AUDITORIA WHERE ID=:id', id=event.getvalue())[0]
                    assert audit[:3] == ('ADMIN', old_user, recipient) and all(audit[3:]), 'audit'
                    previous_event = event.getvalue()
                    q.callproc(PACKAGE + 'TRANSFERIR', args)
                    assert event.getvalue() == previous_event, 'idempotency'
                    c.rollback()
                    assert snapshot() == baseline, 'rollback'
                    q.callproc('APP_SCHEMA.PKG_ASSINAJA_ACESSO.PERMISSAO', ['ADMIN', 'ADMIN', 'S', 'type-test-rollback'])
                    checkpoint = snapshot()
                    try:
                        q.callproc(PACKAGE + 'TRANSFERIR', [*args[:5], str(uuid4()), 'x' * 100, event])
                        raise AssertionError('Expected audit failure')
                    except oracledb.Error as error:
                        assert error.args[0].code == 12899, 'unexpected atomic failure code'
                    assert snapshot() == checkpoint, 'atomic rollback'
                    c.rollback()
                    assert snapshot() == baseline, 'final rollback'
                    report.append({'case': label, 'result': 'passed'})
                    print(label, 'passed', flush=True)
                except oracledb.Error as error:
                    c.rollback()
                    report.append({'case': label, 'result': 'oracle_error', 'code': error.args[0].code})
                    print(label, 'Oracle code', error.args[0].code, flush=True)
                except AssertionError as error:
                    c.rollback()
                    report.append({'case': label, 'result': 'failed', 'check': str(error)})
                    print(label, 'failed:', str(error), flush=True)
finally:
    pool.close()
    (Path(__file__).resolve().parents[1] / 'data/transfer-types-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
if any(r['result'] in ('oracle_error', 'failed') for r in report):
    raise SystemExit(1)
