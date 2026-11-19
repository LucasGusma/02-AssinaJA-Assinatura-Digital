"""Autenticação MV compatível com o fluxo do app institucional já instalado."""
from mv_adapter import MVConfig, oracle_readonly

def authenticate(env_path, username, password):
    if not isinstance(username,str) or not isinstance(password,str) or not password:
        return None
    username=username.strip().upper()
    if len(username)>30 or len(password)>256:
        return None
    # Comparação realizada no banco, sem retornar senha ou material de autenticação.
    expected=(username+password).upper().ljust(30,'K')
    config,db_password=MVConfig.from_env(env_path)
    with oracle_readonly(config,db_password) as connection:
        with connection.cursor() as cursor:
            cursor.execute('''SELECT NM_USUARIO FROM DBASGU.USUARIOS
                WHERE CD_USUARIO=:username AND SN_ATIVO='S'
                  AND DBASGU.CRIPTO_DESCRIPTO(CD_SENHA, 'SMVCRIPTON')=:expected''',
                username=username,expected=expected)
            row=cursor.fetchone()
    return row[0] if row else None
