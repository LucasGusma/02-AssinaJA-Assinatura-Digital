"""Consulta das pendências confirmadas pelo hospital, sem escrita no Oracle."""
from datetime import date, datetime, time, timedelta
from mv_adapter import MVConfig, oracle_readonly

def period(start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except (ValueError, TypeError):
        raise ValueError('Informe datas válidas no formato AAAA-MM-DD.') from None
    if last < first or (last-first).days > 30:
        raise ValueError('Escolha um período de até 31 dias.')
    return datetime.combine(first,time.min), datetime.combine(last+timedelta(days=1),time.min)

def pending_query(scopes, start, end, before=None, limit=50):
    # Cada par concede acesso a um objeto específico dentro de um setor.
    if not scopes or len(scopes)>100:
        raise PermissionError('Nenhum vínculo MV autorizado para consulta.')
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('Página inválida.')
    first, stop = period(start,end)
    params={'start_date':first,'end_date':stop,'row_limit':limit+1}
    clauses=[]
    for i,(sector,obj) in enumerate(scopes):
        if sector is None and obj is None:
            clauses.append('1=1')  # Somente concessão master validada no servidor.
            continue
        if type(sector) is int and sector>0 and obj is None:
            clauses.append(f'd.CD_SETOR = :sector_{i}')
            params[f'sector_{i}']=sector
            continue
        if type(sector) is not int or type(obj) is not int or sector<=0 or obj<=0:
            raise PermissionError('Vínculo de setor e objeto inválido.')
        clauses.append(f'(d.CD_SETOR = :sector_{i} AND d.CD_OBJETO = :object_{i})')
        params[f'sector_{i}']=sector
        params[f'object_{i}']=obj
    cursor_clause=''
    if before is not None:
        if type(before) is not int or before<=0:
            raise ValueError('Marcador de página inválido.')
        cursor_clause='AND d.CD_DOCUMENTO_CLINICO < :before_id'
        params['before_id']=before
    query=f'''
      SELECT * FROM (
        SELECT d.CD_DOCUMENTO_CLINICO, d.CD_PACIENTE, d.CD_ATENDIMENTO,
               d.CD_USUARIO, d.CD_PRESTADOR, d.TP_STATUS, d.DH_CRIACAO,
               o.CD_OBJETO, o.NM_OBJETO, o.TP_OBJETO, o.SN_ASSINATURA, d.CD_SETOR,
               p.NM_PACIENTE, pr.NM_PRESTADOR, s.NM_SETOR
          FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO d
          JOIN USUARIO_BANCO.PAGU_OBJETO o ON o.CD_OBJETO = d.CD_OBJETO
          LEFT JOIN USUARIO_BANCO.PACIENTE p ON p.CD_PACIENTE = d.CD_PACIENTE
          LEFT JOIN USUARIO_BANCO.PRESTADOR pr ON pr.CD_PRESTADOR = d.CD_PRESTADOR
          LEFT JOIN USUARIO_BANCO.SETOR s ON s.CD_SETOR = d.CD_SETOR
         WHERE o.SN_ASSINATURA = 'S' AND d.TP_STATUS = 'FECHADO'
           AND d.DH_CRIACAO >= :start_date AND d.DH_CRIACAO < :end_date
           AND ({' OR '.join(clauses)}) {cursor_clause}
         ORDER BY d.CD_DOCUMENTO_CLINICO DESC
      ) WHERE ROWNUM <= :row_limit
    '''
    return query,params

def query_pending(connection, scopes, start, end, before=None, limit=50):
    query,params=pending_query(scopes,start,end,before,limit)
    keys=('id','patient_id','attendance_id','mv_user','provider_id','mv_status',
          'created','object_id','title','object_type','requires_signature','sector_id',
          'patient_name','provider_name','sector_name')
    with connection.cursor() as cursor:
        cursor.arraysize=limit+1
        cursor.execute(query,params)
        rows=cursor.fetchmany(limit+1)
    documents=[]
    for row in rows[:limit]:
        item=dict(zip(keys,row))
        # Verificação adicional evita apresentar resultados fora do filtro acordado.
        permitted=(None,None) in scopes or (item['sector_id'],None) in scopes or (item['sector_id'],item['object_id']) in scopes
        if item['mv_status']!='FECHADO' or item['requires_signature']!='S' or not permitted:
            raise PermissionError('Resultado incompatível com o escopo autorizado.')
        item['created']=item['created'].isoformat() if item['created'] else None
        documents.append(item)
    return {'documents':documents,'next_cursor':documents[-1]['id'] if len(rows)>limit else None,
            'source':'mv','filter':{'status':'FECHADO','signature':'S'}}

def read_pending(env_path, scopes, start, end, before=None):
    pending_query(scopes,start,end,before)  # Valida antes de abrir a conexão.
    config,password=MVConfig.from_env(env_path)
    with oracle_readonly(config,password) as connection:
        return query_pending(connection,scopes,start,end,before)

def authorized_scopes(db, user):
    # Não converter contas públicas da demo em contas reais, mesmo por engano.
    if not user['mv_code'] or user['mv_code'].startswith('DEMO-'):
        return []
    account=db.execute('SELECT all_sectors FROM mv_accounts WHERE user_id=? AND enabled=1',(user['id'],)).fetchone()
    if not account:
        return []
    # Política autorizada: todos os usuários MV habilitados têm leitura global.
    return [(None,None)]
