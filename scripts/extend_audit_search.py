from pathlib import Path
import re,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool
p=OraclePool(Settings());p.start()
try:
 with p.connection('audit-search-migration') as c,c.cursor() as q:
  q.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM DUAL");assert q.fetchone()[0].lower()=='smlmv'
  originals={};proposed={}
  folder=Path('database/migrations/009_audit_search');folder.mkdir(exist_ok=False)
  for kind in ('PACKAGE','PACKAGE BODY'):
   q.execute("SELECT TEXT FROM USER_SOURCE WHERE NAME='PKG_ASSINAJA_ACESSO' AND TYPE=:kind ORDER BY LINE",kind=kind)
   source=''.join(r[0] for r in q);assert source and 'p_busca' not in source.lower()
   originals[kind]=source
   source,n=re.subn(r'(PROCEDURE\s+auditoria\s*\(p_autor VARCHAR2,p_antes NUMBER,resultado OUT SYS_REFCURSOR)\)',r"\1,p_busca VARCHAR2 DEFAULT NULL,p_acao VARCHAR2 DEFAULT NULL,p_documento NUMBER DEFAULT NULL)",source,flags=re.I);assert n==1
   if kind=='PACKAGE BODY':
    source=source.replace('CD_DOCUMENTO,CD_ORIGEM,NM_ORIGEM,CD_DESTINO,NM_DESTINO','CD_DOCUMENTO,CD_ORIGEM,NM_ORIGEM,CD_DESTINO,NM_DESTINO,REQUEST_ID')
    old='WHERE p_antes IS NULL OR ID<p_antes ORDER BY ID DESC'
    assert old in source
    source=source.replace(old,"""WHERE (p_antes IS NULL OR ID<p_antes)
     AND (p_acao IS NULL OR ACAO=p_acao)
     AND (p_documento IS NULL OR CD_DOCUMENTO=p_documento)
     AND (TRIM(p_busca) IS NULL OR INSTR(
      TRANSLATE(UPPER(CD_AUTOR||' '||NM_AUTOR||' '||CD_ORIGEM||' '||NM_ORIGEM||' '||CD_DESTINO||' '||NM_DESTINO),'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ','AAAAAEEEEIIIIOOOOOUUUUC'),
      TRANSLATE(UPPER(TRIM(p_busca)),'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ','AAAAAEEEEIIIIOOOOOUUUUC'))>0)
     ORDER BY ID DESC""")
   suffix='spec' if kind=='PACKAGE' else 'body'
   (folder/f'original_{suffix}.backup').write_text(originals[kind],encoding='utf-8')
   proposed[kind]='CREATE OR REPLACE '+source
   (folder/f'current_{suffix}.sql').write_text(proposed[kind]+'\n/\n',encoding='utf-8')
  try:
   for source in proposed.values():q.execute(source)
   q.execute("SELECT LINE,TEXT FROM USER_ERRORS WHERE NAME='PKG_ASSINAJA_ACESSO' AND ATTRIBUTE='ERROR'")
   errors=q.fetchall()
   if errors:raise RuntimeError(str(errors))
  except Exception:
   for source in originals.values():q.execute('CREATE OR REPLACE '+source)
   raise
  Path('sql/PKG_ASSINAJA_ACESSO_completa.sql').write_text('\n/\n'.join(proposed.values())+'\n/\n',encoding='utf-8')
  print('Existing audit routine updated. No event or clinical data changed.')
finally:p.close()
