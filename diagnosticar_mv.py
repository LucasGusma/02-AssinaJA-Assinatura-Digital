"""Execute no terminal local: python diagnosticar_mv.py. Não importa documentos."""
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from mv_adapter import MVConfig, MVConfigurationError, oracle_readonly, inspect_schema

ROOT = Path(__file__).resolve().parent

def main():
    try:
        if (ROOT / '.env').exists():
            config, password = MVConfig.from_env(ROOT / '.env')
        else:
            config = MVConfig.from_file(ROOT / 'mv.local.json')
            password = ''
        if not password:
            if not sys.stdin.isatty():
                raise MVConfigurationError('Informe DB_PASSWORD no .env local ou execute em terminal interativo.')
            password = getpass.getpass('Senha Oracle (não será salva): ')
        print(f'Ambiente: {config.environment}. Consulta de metadados; nenhum documento será importado.')
        with oracle_readonly(config,password) as connection:
            report = inspect_schema(connection,config.owner)
        password = None
        report['checked_at'] = datetime.now(timezone.utc).isoformat()
        report['environment'] = config.environment
        output = ROOT / 'data' / 'mv-schema.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Diagnóstico salvo em {output}')
        if report['missing_or_inaccessible']:
            print('Tabelas ausentes ou sem visibilidade: ' + ', '.join(report['missing_or_inaccessible']))
            return 2
        print('Estrutura consultada. O mapeamento de documentos e permissões ainda precisa ser validado.')
        return 0
    except MVConfigurationError as exc:
        print(str(exc),file=sys.stderr)
        return 1
    except Exception as exc:
        # Não imprimir mensagens do driver que podem incluir dados internos de conexão.
        error = exc.args[0] if exc.args else None
        code = getattr(error,'full_code',None)
        print(f'Não foi possível concluir o diagnóstico{": " + code if code else ""}. Verifique conexão, serviço e permissões com a TI.',file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
