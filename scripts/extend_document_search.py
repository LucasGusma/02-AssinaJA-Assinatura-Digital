from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool
pool=OraclePool(Settings());pool.start()
try:
 with pool.connection('extend-document-search') as c,c.cursor() as q:
  q.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM DUAL")
  assert q.fetchone()[0].lower()=='smlmv'
  originals={}
  for kind in ('PACKAGE','PACKAGE BODY'):
   q.execute("SELECT TEXT FROM USER_SOURCE WHERE NAME='PKG_GERENCIADOR_ASSINATURA' AND TYPE=:kind ORDER BY LINE",kind=kind)
   originals[kind]=''.join(r[0] for r in q)
  assert all(originals.values()) and 'p_tipo_documento' not in originals['PACKAGE'].lower()
  folder=Path('database/migrations/008_document_search');folder.mkdir(exist_ok=False)
  spec=originals['PACKAGE'].replace('p_prestador_nome IN VARCHAR2 DEFAULT NULL','p_prestador_nome IN VARCHAR2 DEFAULT NULL, p_tipo_documento IN NUMBER DEFAULT NULL')
  body=originals['PACKAGE BODY'].replace('p_prestador_nome IN VARCHAR2 DEFAULT NULL','p_prestador_nome IN VARCHAR2 DEFAULT NULL, p_tipo_documento IN NUMBER DEFAULT NULL')
  assert 'TRUNC(p_dt_fim) - TRUNC(p_dt_ini) > 30' in body
  body=body.replace('TRUNC(p_dt_fim) - TRUNC(p_dt_ini) > 30',"TRUNC(p_dt_ini) < ADD_MONTHS(TRUNC(p_dt_fim), -3)").replace('Periodo deve conter ate 31 dias.','Periodo deve conter ate 3 meses.')
  body=body.replace('AND (p_antes IS NULL OR dc.cd_documento_clinico < p_antes)', 'AND (p_tipo_documento IS NULL OR dc.cd_objeto = p_tipo_documento) AND (p_antes IS NULL OR dc.cd_documento_clinico < p_antes)')
  declarations="""
 PROCEDURE tipos_documento(resultado OUT SYS_REFCURSOR);
 PROCEDURE resumo_pendencias(p_usuario VARCHAR2,p_escopo VARCHAR2,resultado OUT SYS_REFCURSOR);
"""
  routines="""
 PROCEDURE tipos_documento(resultado OUT SYS_REFCURSOR) IS BEGIN
  OPEN resultado FOR SELECT cd_objeto,nm_objeto FROM pagu_objeto WHERE sn_assinatura='S' ORDER BY UPPER(nm_objeto),cd_objeto;
 END;
 PROCEDURE resumo_pendencias(p_usuario VARCHAR2,p_escopo VARCHAR2,resultado OUT SYS_REFCURSOR) IS BEGIN
  IF p_usuario IS NULL OR p_escopo IS NULL OR p_escopo NOT IN ('TODOS','MEUS') THEN
   raise_application_error(-20001,'Usuario e escopo obrigatorios.');
  END IF;
  OPEN resultado FOR SELECT COUNT(*) total, ADD_MONTHS(TRUNC(SYSDATE),-3) inicio,TRUNC(SYSDATE) fim
   FROM pw_documento_clinico dc JOIN pagu_objeto obj ON obj.cd_objeto=dc.cd_objeto
   WHERE dc.tp_status='FECHADO' AND obj.sn_assinatura='S'
   AND dc.dh_criacao>=ADD_MONTHS(TRUNC(SYSDATE),-3) AND dc.dh_criacao<TRUNC(SYSDATE)+1
   AND (p_escopo='TODOS' OR dc.cd_usuario=p_usuario);
 END;
"""
  import re
  proposed={}
  for kind,text,extra in [('PACKAGE',spec,declarations),('PACKAGE BODY',body,routines)]:
   text,n=re.subn(r'END\s+PKG_GERENCIADOR_ASSINATURA\s*;\s*$',lambda m:extra+'\nEND PKG_GERENCIADOR_ASSINATURA;',text,flags=re.I)
   assert n==1
   suffix='pks' if kind=='PACKAGE' else 'pkb'
   (folder/f'original.{suffix}.backup').write_text(originals[kind],encoding='utf-8')
   proposed[kind]='CREATE OR REPLACE '+text
   (folder/f'current.{suffix}.sql').write_text(proposed[kind]+'\n/\n',encoding='utf-8')
  try:
   for text in proposed.values():q.execute(text)
   q.execute("SELECT LINE,TEXT FROM USER_ERRORS WHERE NAME='PKG_GERENCIADOR_ASSINATURA' AND ATTRIBUTE='ERROR'")
   errors=q.fetchall()
   if errors:raise RuntimeError(str(errors))
  except Exception:
   for text in originals.values():q.execute('CREATE OR REPLACE '+text)
   raise
  for kind,suffix in [('PACKAGE','spec'),('PACKAGE BODY','body')]:
   Path(f'sql/PKG_GERENCIADOR_ASSINATURA_{suffix}.sql').write_text(proposed[kind]+'\n/\n',encoding='utf-8')
  Path('sql/PKG_GERENCIADOR_ASSINATURA_completa.sql').write_text('\n/\n'.join(proposed.values())+'\n/\n',encoding='utf-8')
  print('Existing package updated and exported. No clinical DML.')
finally:pool.close()
