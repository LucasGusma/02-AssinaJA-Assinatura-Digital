"""Conexão Oracle de leitura e diagnóstico de esquema, separado do dashboard demo."""
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Protocol, Iterable

class MVConfigurationError(ValueError):
    pass

def read_env(path):
    """Lê valores literais; não executa comandos nem expande variáveis."""
    try:
        lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    except OSError as exc:
        raise MVConfigurationError('Arquivo .env não disponível.') from exc
    values = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key.strip()):
            raise MVConfigurationError('Linha inválida no .env; use CHAVE=valor.')
        value = value.strip()
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        values[key.strip()] = value
    return values

@dataclass(frozen=True)
class MVConfig:
    environment: str
    host: str
    port: int
    service_name: str
    user: str
    owner: str
    client_dir: str = ''

    @classmethod
    def from_env(cls, path):
        values = read_env(path)
        match = re.fullmatch(r'([^\s:/]+):(\d{1,5})/([^\s/]+)',values.get('DB_DSN',''))
        if not match or not 1 <= int(match[2]) <= 65535:
            raise MVConfigurationError('DB_DSN deve usar servidor:porta/servico.')
        environment = values.get('MV_ENVIRONMENT','')
        user = values.get('DB_USER','')
        owner = values.get('DB_OWNER','')
        if environment not in ('homologacao','producao') or not user or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_$#]*',owner):
            raise MVConfigurationError('Confira MV_ENVIRONMENT, DB_USER e DB_OWNER no .env.')
        return cls(environment,match[1],int(match[2]),match[3],user,owner.upper(),values.get('ORACLE_CLIENT_DIR','')), values.get('DB_PASSWORD','')

    @classmethod
    def from_file(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            raise MVConfigurationError('Crie mv.local.json a partir de mv.example.json e preencha a conexão.') from exc
        required = {'environment','host','port','service_name','user','owner'}
        if not isinstance(data,dict) or set(data) != required:
            raise MVConfigurationError('Use somente os campos do modelo. A senha não deve ser salva neste arquivo.')
        if data['environment'] not in ('homologacao','producao'):
            raise MVConfigurationError('Ambiente deve ser homologacao ou producao.')
        if type(data['port']) is not int or not 1 <= data['port'] <= 65535:
            raise MVConfigurationError('Porta Oracle inválida.')
        for key in ('host','service_name','user','owner'):
            if not isinstance(data[key],str) or not data[key].strip():
                raise MVConfigurationError(f'Preencha o campo {key}.')
            data[key] = data[key].strip()
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_$#]*',data['owner']):
            raise MVConfigurationError('Owner Oracle inválido.')
        data['owner'] = data['owner'].upper()
        return cls(**data)

@contextmanager
def oracle_readonly(config, password, driver=None):
    if not isinstance(password,str) or not password:
        raise MVConfigurationError('Informe a senha localmente no terminal.')
    if driver is None:
        try:
            import oracledb as driver
        except ImportError as exc:
            raise MVConfigurationError('Instale o driver com: python -m pip install -r requirements-mv.txt') from exc
    if config.client_dir:
        driver.init_oracle_client(lib_dir=config.client_dir)
    connection = driver.connect(user=config.user,password=password,host=config.host,
                                port=config.port,service_name=config.service_name,
                                tcp_connect_timeout=10,retry_count=0)
    try:
        connection.call_timeout = 15000
        with connection.cursor() as cursor:
            # Se a transação de leitura falhar, nenhuma consulta será executada.
            cursor.execute('SET TRANSACTION READ ONLY')
        yield connection
    finally:
        connection.close()

def inspect_schema(connection, owner):
    """Retorna somente metadados das duas tabelas informadas; não lê pacientes."""
    with connection.cursor() as cursor:
        cursor.execute('''
            SELECT OWNER, TABLE_NAME, COLUMN_NAME, DATA_TYPE,
                   DATA_LENGTH, NULLABLE, COLUMN_ID
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = :owner
              AND TABLE_NAME IN ('PW_DOCUMENTO_CLINICO', 'PW_DOCUMENTO_ASSINADO')
            ORDER BY TABLE_NAME, COLUMN_ID
        ''', owner=owner)
        keys = ('owner','table','column','type','length','nullable','position')
        columns = [dict(zip(keys,row)) for row in cursor.fetchall()]
        cursor.execute('''
            SELECT C.TABLE_NAME, C.CONSTRAINT_NAME, C.CONSTRAINT_TYPE,
                   CC.COLUMN_NAME, CC.POSITION,
                   R.OWNER, R.TABLE_NAME, RC.COLUMN_NAME
            FROM ALL_CONSTRAINTS C
            JOIN ALL_CONS_COLUMNS CC
              ON CC.OWNER = C.OWNER AND CC.CONSTRAINT_NAME = C.CONSTRAINT_NAME
            LEFT JOIN ALL_CONSTRAINTS R
              ON R.OWNER = C.R_OWNER AND R.CONSTRAINT_NAME = C.R_CONSTRAINT_NAME
            LEFT JOIN ALL_CONS_COLUMNS RC
              ON RC.OWNER = R.OWNER AND RC.CONSTRAINT_NAME = R.CONSTRAINT_NAME
             AND RC.POSITION = CC.POSITION
            WHERE C.OWNER = :owner
              AND C.TABLE_NAME IN ('PW_DOCUMENTO_CLINICO', 'PW_DOCUMENTO_ASSINADO')
              AND C.CONSTRAINT_TYPE IN ('P','U','R')
            ORDER BY C.TABLE_NAME, C.CONSTRAINT_NAME, CC.POSITION
        ''', owner=owner)
        keys = ('table','constraint','kind','column','position','target_owner','target_table','target_column')
        relationships = [dict(zip(keys,row)) for row in cursor.fetchall()]
    found = {item['table'] for item in columns}
    missing = sorted({'PW_DOCUMENTO_CLINICO','PW_DOCUMENTO_ASSINADO'} - found)
    return {'columns':columns,'relationships':relationships,'missing_or_inaccessible':missing}

@dataclass(frozen=True)
class MVDocument:
    mv_id: str
    title: str
    original_author_id: str
    sector_id: str
    professional_area: str
    signed: bool

class MVReader(Protocol):
    def documents(self) -> Iterable[MVDocument]:
        """Consultar somente após validar o esquema e autorizar a conexão."""
        ...

class UnconfiguredMVReader:
    def documents(self):
        raise RuntimeError('MV não configurado. Validar esquema e acesso de homologação antes da integração.')
