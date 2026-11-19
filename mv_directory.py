"""Diretório MV de setores e perfis. Exclusivamente SELECT."""
from mv_adapter import MVConfig, oracle_readonly

def sectors(env_path):
    config,password=MVConfig.from_env(env_path)
    with oracle_readonly(config,password) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT CD_SETOR,NM_SETOR FROM USUARIO_BANCO.SETOR WHERE SN_ATIVO='S' ORDER BY NM_SETOR,CD_SETOR")
            return [{'id':row[0],'name':row[1] or 'Setor sem nome'} for row in cur.fetchall()]

def sector_users(env_path,sector_id):
    if type(sector_id) is not int or sector_id<=0: raise ValueError('Setor inválido.')
    config,password=MVConfig.from_env(env_path)
    with oracle_readonly(config,password) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT DISTINCT u.CD_USUARIO,u.NM_USUARIO,u.CD_PRESTADOR,
                   p.NM_PRESTADOR,t.NM_TIP_PRESTA
                FROM USUARIO_BANCO.USUARIO_SETOR us
                JOIN USUARIO_BANCO.SETOR s ON s.CD_SETOR=us.CD_SETOR AND s.SN_ATIVO='S'
                JOIN DBASGU.USUARIOS u ON u.CD_USUARIO=us.NM_USUARIO
                LEFT JOIN USUARIO_BANCO.PRESTADOR p ON p.CD_PRESTADOR=u.CD_PRESTADOR
                LEFT JOIN USUARIO_BANCO.TIP_PRESTA t ON t.CD_TIP_PRESTA=p.CD_TIP_PRESTA
                WHERE us.CD_SETOR=:sector_id AND u.SN_ATIVO='S'
                ORDER BY u.NM_USUARIO,u.CD_USUARIO''',sector_id=sector_id)
            return [dict(zip(('username','name','provider_id','provider_name','profile'),r)) for r in cur.fetchall()]

def is_master(db,user):
    if not user['mv_code'] or user['mv_code'].startswith('DEMO-'): return False
    row=db.execute('SELECT is_master FROM mv_accounts WHERE user_id=? AND enabled=1',(user['id'],)).fetchone()
    return bool(row and row['is_master'])

def save_forward_permission(db, actor, username, sector_id, enabled, verified_users):
    if not is_master(db,actor): raise PermissionError('Somente o administrador master pode alterar permissões.')
    if type(enabled) is not bool or type(sector_id) is not int or sector_id<=0:
        raise ValueError('Permissão inválida.')
    if not any(u['username']==username for u in verified_users):
        raise ValueError('Usuário ativo não vinculado ao setor no MV.')
    from datetime import datetime,timezone
    now=datetime.now(timezone.utc).isoformat()
    db.execute('''INSERT INTO mv_forward_permissions(mv_user,sector_id,enabled,updated_by,updated_at)
        VALUES(?,?,?,?,?) ON CONFLICT(mv_user,sector_id) DO UPDATE SET
        enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=excluded.updated_at''',
        (username,sector_id,int(enabled),actor['id'],now))
    db.execute('INSERT INTO mv_permission_audit(actor_id,mv_user,sector_id,enabled,created) VALUES(?,?,?,?,?)',
               (actor['id'],username,sector_id,int(enabled),now))
