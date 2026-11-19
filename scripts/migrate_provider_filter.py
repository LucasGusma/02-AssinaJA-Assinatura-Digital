"""Add an optional provider filter without changing existing seven-argument calls."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.infrastructure.oracle.pool import OraclePool

root = Path(__file__).resolve().parents[1]
pool = OraclePool(Settings()); pool.start()
try:
    with pool.connection('provider-filter-migration') as c, c.cursor() as q:
        q.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM DUAL")
        if q.fetchone()[0] != 'smlmv':
            raise SystemExit('Only confirmed homologation allowed.')
        originals = {}
        proposed = {}
        for kind in ('PACKAGE', 'PACKAGE BODY'):
            q.execute("SELECT TEXT FROM USER_SOURCE WHERE NAME='PKG_GERENCIADOR_ASSINATURA' AND TYPE=:kind ORDER BY LINE", kind=kind)
            source = ''.join(r[0] for r in q)
            if not source or 'p_prestador_nome' in source.lower():
                raise SystemExit('Package missing or filter already installed; inspect before retrying.')
            originals[kind] = 'CREATE OR REPLACE ' + source
            pattern = r'(PROCEDURE\s+lista_pendencias\s*\(.*?documentos\s+OUT\s+SYS_REFCURSOR)(\s*\))'
            source, count = re.subn(pattern, r'\1,\n        p_prestador_nome IN VARCHAR2 DEFAULT NULL\2', source, count=1, flags=re.I | re.S)
            if count != 1:
                raise SystemExit('Expected procedure signature not found.')
            if kind == 'PACKAGE BODY':
                clause = "AND (p_antes IS NULL OR dc.cd_documento_clinico < p_antes)"
                if source.count(clause) != 1:
                    raise SystemExit('Expected pagination clause not found.')
                normalize = lambda expr: f"TRANSLATE(UPPER({expr}), 'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ', 'AAAAAEEEEIIIIOOOOOUUUUC')"
                source = source.replace(clause, clause + '\n                   AND (TRIM(p_prestador_nome) IS NULL OR INSTR(' + normalize('pre.nm_prestador') + ', ' + normalize('TRIM(p_prestador_nome)') + ') > 0)')
            proposed[kind] = 'CREATE OR REPLACE ' + source
        folder = root / 'database/migrations/006_provider_filter'
        folder.mkdir(exist_ok=False)
        for kind in originals:
            suffix = 'pks' if kind == 'PACKAGE' else 'pkb'
            (folder / f'original.{suffix}.sql').write_text(originals[kind], encoding='utf-8')
            (folder / f'proposed.{suffix}.sql').write_text(proposed[kind], encoding='utf-8')
        try:
            for kind in proposed:
                q.execute(proposed[kind])
            q.execute("SELECT TYPE,LINE,TEXT FROM USER_ERRORS WHERE NAME='PKG_GERENCIADOR_ASSINATURA' AND ATTRIBUTE='ERROR'")
            errors = q.fetchall()
            if errors:
                raise RuntimeError(str(errors))
        except Exception:
            for kind in originals:
                q.execute(originals[kind])
            raise
        print('Optional provider filter installed; clinical data unchanged.')
finally:
    pool.close()
