"""Leitura do arquivo original ou campos reais do Editor MV, sem gerar assinatura."""
import base64
import binascii
from mv_adapter import MVConfig,oracle_readonly

MAX_FILE=20*1024*1024

def decode_pdf(raw):
    if len(raw)>MAX_FILE: raise ValueError('Arquivo excede o limite de visualização de 20 MB.')
    if raw.startswith(b'%PDF-'): return raw
    try:
        decoded=base64.b64decode(b''.join(raw.split()),validate=True)
    except (ValueError,binascii.Error):
        raise ValueError('Formato de arquivo não suportado pelo visualizador.') from None
    if not decoded.startswith(b'%PDF-'):
        raise ValueError('O conteúdo disponível não é um PDF válido.')
    return decoded

def document(env_path,document_id,file=False):
    if type(document_id) is not int or document_id<=0: raise ValueError('Documento inválido.')
    config,password=MVConfig.from_env(env_path)
    with oracle_readonly(config,password) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT d.CD_DOCUMENTO_DIGITAL,o.NM_OBJETO
                FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO d JOIN USUARIO_BANCO.PAGU_OBJETO o ON o.CD_OBJETO=d.CD_OBJETO
                WHERE d.CD_DOCUMENTO_CLINICO=:doc AND d.TP_STATUS='FECHADO' AND o.SN_ASSINATURA='S' ''',doc=document_id)
            row=cur.fetchone()
            if not row: raise LookupError('Documento fora da lista de pendências ou não encontrado. Atualize a consulta.')
            digital_id,title=row
            if digital_id:
                cur.execute('SELECT LO_DOCUMENTO FROM USUARIO_BANCO.DOCUMENTO_DIGITAL WHERE CD_DOCUMENTO_DIGITAL=:doc',doc=digital_id)
                blobrow=cur.fetchone()
                if blobrow and blobrow[0]:
                    blob=blobrow[0]
                    if blob.size()>MAX_FILE: raise ValueError('Arquivo excede o limite de visualização de 20 MB.')
                    pdf=decode_pdf(blob.read())
                    return pdf if file else {'kind':'pdf','title':title,'id':document_id}
            if file: raise LookupError('PDF original indisponível para esta pendência.')
            cur.execute('''SELECT pec.CD_EDITOR_REGISTRO,pec.CD_DOCUMENTO,ed.DS_DOCUMENTO
                FROM USUARIO_BANCO.PW_EDITOR_CLINICO pec
                LEFT JOIN USUARIO_BANCO.EDITOR_DOCUMENTO ed ON ed.CD_DOCUMENTO=pec.CD_DOCUMENTO
                WHERE pec.CD_DOCUMENTO_CLINICO=:doc ORDER BY pec.CD_EDITOR_CLINICO''',doc=document_id)
            editors=cur.fetchmany(2)
            if len(editors)>1:
                return {'kind':'unavailable','message':'Há múltiplos registros de editor vinculados. É necessário validar a versão oficial no MV.'}
            if not editors:
                return {'kind':'unavailable','message':'Este tipo de documento não possui PDF nem registro do Editor vinculado. A visualização oficial depende do módulo de origem no MV.'}
            editor_id,model_id,model_title=editors[0]
            cur.execute('''SELECT c.DS_CAMPO,c.DS_IDENTIFICADOR,r.DS_VALOR,r.LO_VALOR
                FROM USUARIO_BANCO.EDITOR_REGISTRO_CAMPO r JOIN USUARIO_BANCO.EDITOR_CAMPO c ON c.CD_CAMPO=r.CD_CAMPO
                WHERE r.CD_REGISTRO=:reg ORDER BY r.CD_CAMPO''',reg=editor_id)
            rows=cur.fetchmany(301)
            fields=[]
            total=0
            partial=len(rows)>300
            for label,identifier,value,lob in rows[:300]:
                truncated=False
                if lob:
                    truncated=lob.size()>20000
                    value=lob.read(1,20000)
                if value is None or not str(value).strip(): continue
                value=str(value)
                if total+len(value)>500000:
                    partial=True
                    break
                total+=len(value)
                fields.append({'label':label or identifier or 'Campo sem identificação','value':value,'truncated':truncated})
                partial=partial or truncated
            return {'kind':'editor','title':model_title or title,'model_id':model_id,'fields':fields,
                    'partial':partial,'notice':'Conteúdo real dos campos do Editor MV. Esta visualização não reproduz o formulário oficial, não inclui imagens e não comprova assinatura.'}
