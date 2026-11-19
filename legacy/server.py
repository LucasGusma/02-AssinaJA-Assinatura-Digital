"""AssinaJA: demonstração local. Execute: python server.py."""
import hashlib
import argparse
import hmac
import json
import os
import secrets
import socket
import sqlite3
import time
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from mv_pending import authorized_scopes, read_pending
from mv_adapter import read_env
from mv_auth import authenticate as authenticate_mv
from mv_directory import sectors as mv_sectors, sector_users, is_master, save_forward_permission
from mv_document import document as mv_document
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'assinaja.db'
SESSIONS = {}
ROLES = ('coordenador', 'superintendente')
LOGIN_ATTEMPTS = {}
LOGIN_LOCK = Lock()

class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

def connect():
    db = sqlite3.connect(DB, factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200000).hex()

def initialize():
    DB.parent.mkdir(exist_ok=True)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, role TEXT, sector TEXT, area TEXT, mv_code TEXT UNIQUE, salt TEXT, password TEXT);
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, title TEXT, patient TEXT, author TEXT, sector TEXT, area TEXT, created TEXT, status TEXT, assignee INTEGER REFERENCES users(id), mv_id TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, document_id INTEGER REFERENCES documents(id), actor INTEGER REFERENCES users(id), action TEXT, detail TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS mv_access(user_id INTEGER REFERENCES users(id), sector_id INTEGER NOT NULL, object_id INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,sector_id,object_id));
        CREATE TABLE IF NOT EXISTS mv_accounts(user_id INTEGER PRIMARY KEY REFERENCES users(id), all_sectors INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS mv_forward_permissions(mv_user TEXT NOT NULL,sector_id INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,updated_by INTEGER REFERENCES users(id),updated_at TEXT,PRIMARY KEY(mv_user,sector_id));
        CREATE TABLE IF NOT EXISTS mv_permission_audit(id INTEGER PRIMARY KEY,actor_id INTEGER REFERENCES users(id),mv_user TEXT,sector_id INTEGER,enabled INTEGER,created TEXT);
        ''')
        if 'is_master' not in {r['name'] for r in db.execute('PRAGMA table_info(mv_accounts)')}:
            db.execute('ALTER TABLE mv_accounts ADD COLUMN is_master INTEGER NOT NULL DEFAULT 0')
        if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
            return
        users = [
            ('secretaria','Marina Alves','secretaria','Clínica médica','Medicina'),
            ('coordenador','Rafael Costa','coordenador','Clínica médica','Medicina'),
            ('superintendente','Helena Souza','superintendente','Clínica médica','Medicina'),
            ('medico','André Lima','profissional','Clínica médica','Medicina'),
            ('enfermagem','Beatriz Santos','coordenador','Clínica médica','Enfermagem'),
            ('cirurgia','Paulo Mendes','coordenador','Centro cirúrgico','Medicina'),
            ('admin','Administrador demo','administrador','Todos','Todas'),
            ('tecnico','Joana Martins','profissional','Clínica médica','Técnicos'),
            ('multi','Camila Reis','coordenador','Clínica médica','Multiprofissional'),
        ]
        for i, (username,name,role,sector,area) in enumerate(users,1):
            salt = secrets.token_hex(16)
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?,?,?)', (i,username,name,role,sector,area,f'DEMO-{i:03}',salt,password_hash('Demo@2026',salt)))
        examples = [
            ('Evolução médica','Paciente fictício A','André Lima','Clínica médica','Medicina','pendente',None),
            ('Resumo de alta','Paciente fictício B','Residente demo','Clínica médica','Medicina','pendente',None),
            ('Prescrição médica','Paciente fictício C','André Lima','Clínica médica','Medicina','encaminhado',2),
            ('Avaliação clínica','Paciente fictício D','Residente demo','Clínica médica','Medicina','pendente',None),
            ('Evolução de enfermagem','Paciente fictício E','Beatriz Santos','Clínica médica','Enfermagem','pendente',None),
            ('Descrição cirúrgica','Paciente fictício F','Paulo Mendes','Centro cirúrgico','Medicina','pendente',None),
            ('Avaliação nutricional','Paciente fictício G','Camila Reis','Clínica médica','Multiprofissional','pendente',None),
            ('Anotação de cuidados','Paciente fictício H','Joana Martins','Clínica médica','Técnicos','pendente',None),
            ('Evolução médica','Paciente fictício I','André Lima','Clínica médica','Medicina','assinado',2),
        ]
        for i,row in enumerate(examples,1):
            title,patient,author,sector,area,status,assignee = row
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',(i,title,patient,author,sector,area,f'2026-10-0{(i % 4)+1}T10:00:00Z',status,assignee,f'DEMO-{1000+i}'))
            db.execute('INSERT INTO audit(document_id,actor,action,detail,created) VALUES(?,?,?,?,?)',(i,7,'Carga de demonstração','Registro fictício; não recebido do MV.',datetime.now(timezone.utc).isoformat()))

def configure_master():
    if not (ROOT/'.env').exists(): return
    username=read_env(ROOT/'.env').get('MV_MASTER_USER','').strip().upper()
    if not username: return
    with connect() as db:
        user=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if not user:
            salt=secrets.token_hex(16)
            db.execute('INSERT INTO users(username,name,role,sector,area,mv_code,salt,password) VALUES(?,?,?,?,?,?,?,?)',
                       (username,username,'administrador','Todos os setores','TI',username,salt,password_hash(secrets.token_urlsafe(32),salt)))
            user=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if user['mv_code']!=username or user['mv_code'].startswith('DEMO-'):
            raise ValueError('O administrador MV deve ter uma conta distinta da demonstração.')
        db.execute('UPDATE mv_accounts SET is_master=0')
        db.execute('INSERT OR REPLACE INTO mv_accounts(user_id,all_sectors,enabled,is_master) VALUES(?,1,1,1)',(user['id'],))

def visible(user, doc):
    return user['role'] == 'administrador' or (user['sector'] == doc['sector'] and user['area'] == doc['area'])

def forward(db, user, document_id, recipient_id, reason):
    doc = db.execute('SELECT * FROM documents WHERE id=?',(document_id,)).fetchone()
    recipient = db.execute('SELECT * FROM users WHERE id=?',(recipient_id,)).fetchone()
    if user['role'] != 'secretaria' or not doc or not visible(user,doc):
        raise ValueError('Somente a secretaria autorizada do mesmo setor e área pode encaminhar.')
    if not recipient or recipient['role'] not in ROLES or recipient['sector'] != doc['sector'] or recipient['area'] != doc['area']:
        raise ValueError('O destinatário deve ser coordenador ou superintendente do mesmo setor e área.')
    if doc['status'] != 'pendente':
        raise ValueError('Somente documentos pendentes podem ser encaminhados.')
    if not isinstance(reason,str) or not 10 <= len(reason.strip()) <= 1000:
        raise ValueError('Informe uma justificativa entre 10 e 1.000 caracteres.')
    result = db.execute("UPDATE documents SET assignee=?,status='encaminhado' WHERE id=? AND status='pendente'",(recipient_id,document_id))
    if result.rowcount != 1:
        raise ValueError('Este documento já foi atualizado. Recarregue a lista.')
    db.execute('INSERT INTO audit(document_id,actor,action,detail,created) VALUES(?,?,?,?,?)',(document_id,user['id'],'Encaminhamento',f"Para {recipient['name']}. Justificativa: {reason.strip()}",datetime.now(timezone.utc).isoformat()))

class Handler(BaseHTTPRequestHandler):
    def send(self, status, data, cookie=None):
        body = json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(body)

    def user(self, db):
        cookies = SimpleCookie(self.headers.get('Cookie',''))
        token = cookies.get('session')
        session = SESSIONS.get(token.value if token else '')
        if session and session[1] > time.time():
            return db.execute('SELECT * FROM users WHERE id=?',(session[0],)).fetchone()
        return None

    def do_GET(self):
        if self.path.startswith('/api/'):
            with connect() as db:
                user = self.user(db)
                if not user: return self.send(401,{'error':'Entre para continuar.'})
                path=urlsplit(self.path).path
                if path in ('/api/mv/sectors','/api/mv/users','/api/mv/document','/api/mv/document/file'):
                    if not authorized_scopes(db,user): return self.send(403,{'error':'Acesso disponível somente para usuários autenticados no MV.'})
                    params=parse_qs(urlsplit(self.path).query)
                    try:
                        if path=='/api/mv/sectors':
                            return self.send(200,{'sectors':mv_sectors(ROOT/'.env')})
                        if path=='/api/mv/users':
                            if not is_master(db,user): return self.send(403,{'error':'Acessos e permissões são exclusivos do administrador master.'})
                            sector=int(params.get('sector',['0'])[0])
                            members=sector_users(ROOT/'.env',sector)
                            permissions={r['mv_user']:bool(r['enabled']) for r in db.execute('SELECT mv_user,enabled FROM mv_forward_permissions WHERE sector_id=?',(sector,))}
                            for member in members: member['can_forward']=permissions.get(member['username'],False)
                            return self.send(200,{'users':members,'can_manage':is_master(db,user)})
                        docid=int(params.get('id',['0'])[0])
                        content=mv_document(ROOT/'.env',docid,file=path.endswith('/file'))
                        if path.endswith('/file'):
                            self.send_response(200)
                            self.send_header('Content-Type','application/pdf')
                            self.send_header('Content-Length',str(len(content)))
                            self.send_header('Content-Disposition',f'inline; filename="documento-{docid}.pdf"')
                            self.send_header('Cache-Control','no-store')
                            self.send_header('X-Content-Type-Options','nosniff')
                            self.send_header('X-Frame-Options','SAMEORIGIN')
                            self.send_header('Content-Security-Policy',"frame-ancestors 'self'")
                            self.end_headers()
                            self.wfile.write(content)
                            return
                        return self.send(200,content)
                    except LookupError as exc: return self.send(404,{'error':str(exc)})
                    except ValueError as exc: return self.send(400,{'error':str(exc)})
                    except Exception: return self.send(503,{'error':'Não foi possível obter os dados do MV. Tente novamente.'})
                if urlsplit(self.path).path == '/api/mv/documents':
                    scopes=authorized_scopes(db,user)
                    if not scopes:
                        return self.send(403,{'error':'Consulta real bloqueada: seu usuário ainda não possui vínculos MV autorizados.'})
                    try:
                        params=parse_qs(urlsplit(self.path).query)
                        sector=params.get('sector',[''])[0]
                        if sector:
                            scopes=[(int(sector),None)] if (None,None) in scopes else [scope for scope in scopes if scope[0]==int(sector)]
                        before=params.get('before',[''])[0]
                        result=read_pending(ROOT/'.env',scopes,params.get('start',[''])[0],params.get('end',[''])[0],int(before) if before else None)
                        return self.send(200,result)
                    except PermissionError:
                        return self.send(403,{'error':'Setor ou objeto fora do seu escopo MV autorizado.'})
                    except ValueError as exc:
                        return self.send(400,{'error':str(exc)})
                    except Exception:
                        return self.send(503,{'error':'Não foi possível consultar o MV. Tente novamente ou contate a TI.'})
                if self.path == '/api/state':
                    docs = [dict(r) for r in db.execute('SELECT d.*,u.name AS recipient FROM documents d LEFT JOIN users u ON u.id=d.assignee ORDER BY d.created DESC') if visible(user,r)]
                    ids = {d['id'] for d in docs}
                    audit = [dict(r) for r in db.execute('SELECT a.*,u.name AS actor_name FROM audit a JOIN users u ON u.id=a.actor ORDER BY a.id DESC') if r['document_id'] in ids]
                    users = [dict(r) for r in db.execute('SELECT id,name,role,sector,area,mv_code FROM users') if user['role']=='administrador' or (r['sector']==user['sector'] and r['area']==user['area'])]
                    scopes=authorized_scopes(db,user)
                    if scopes: docs,users,audit=[],[],[]
                    return self.send(200,{'user':{k:user[k] for k in ('id','name','role','sector','area','mv_code')},'documents':docs,'users':users,'audit':audit,'integration':{'mode':'mv' if scopes else 'demo','mv_query_ready':True,'mv_access':bool(scopes),'is_master':is_master(db,user),'all_sectors':(None,None) in scopes,'sectors':sorted({s[0] for s in scopes if s[0] is not None}),'pending_status':'FECHADO','requires_signature':'S'}})
                return self.send(404,{'error':'Rota inexistente.'})
        files = {'/':'index.html','/app.js':'app.js','/style.css':'style.css','/logo-baleia.png':'logo-baleia.png'}
        name = files.get(self.path.split('?')[0])
        if not name: return self.send(404,{'error':'Página não encontrada.'})
        content = (ROOT/'static'/name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8','png':'image/png'}[name.split('.')[-1]])
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host',''):
            return self.send(403,{'error':'Origem não autorizada.'})
        try:
            size = int(self.headers.get('Content-Length','0'))
            if not 0 < size <= 8192: raise ValueError('Requisição inválida.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError('Requisição inválida.')
            with connect() as db:
                if self.path == '/api/login':
                    username,password = data.get('username',''),data.get('password','')
                    if not isinstance(username,str) or not isinstance(password,str): raise ValueError('Credenciais inválidas.')
                    key=(self.client_address[0],username.upper())
                    with LOGIN_LOCK:
                        recent=[t for t in LOGIN_ATTEMPTS.get(key,[]) if t>time.time()-300]
                        if len(recent)>=8:
                            return self.send(429,{'error':'Muitas tentativas. Aguarde cinco minutos.'})
                        LOGIN_ATTEMPTS[key]=recent+[time.time()]
                    user = db.execute('SELECT * FROM users WHERE LOWER(username)=LOWER(?)',(username,)).fetchone()
                    authenticated=False
                    if not user or (user['mv_code'] and not user['mv_code'].startswith('DEMO-')):
                        account=db.execute('SELECT enabled FROM mv_accounts WHERE user_id=?',(user['id'],)).fetchone() if user else None
                        if account is None or account['enabled']:
                            try:
                                name=authenticate_mv(ROOT/'.env',username.strip().upper(),password)
                            except Exception:
                                return self.send(503,{'error':'Autenticação MV indisponível. Tente novamente.'})
                            authenticated=bool(name)
                            if authenticated:
                                if not user:
                                    mv_username=username.strip().upper()
                                    salt=secrets.token_hex(16)
                                    db.execute('''INSERT INTO users(username,name,role,sector,area,mv_code,salt,password)
                                        VALUES(?,?,?,?,?,?,?,?)''',(mv_username,name,'profissional','Todos os setores','Consulta MV',mv_username,salt,password_hash(secrets.token_urlsafe(32),salt)))
                                    user=db.execute('SELECT * FROM users WHERE username=?',(mv_username,)).fetchone()
                                db.execute('UPDATE users SET name=? WHERE id=?',(name,user['id']))
                                db.execute('INSERT OR IGNORE INTO mv_accounts(user_id,all_sectors,enabled,is_master) VALUES(?,1,1,0)',(user['id'],))
                    elif user:
                        authenticated=hmac.compare_digest(user['password'],password_hash(password,user['salt']))
                    if not authenticated:
                        return self.send(401,{'error':'Usuário ou senha incorretos.'})
                    with LOGIN_LOCK: LOGIN_ATTEMPTS.pop(key,None)
                    token = secrets.token_urlsafe(32)
                    SESSIONS[token] = (user['id'],time.time()+3600)
                    return self.send(200,{'ok':True},f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600')
                user = self.user(db)
                if not user: return self.send(401,{'error':'Sua sessão expirou. Entre novamente.'})
                if self.path == '/api/mv/permissions':
                    if not is_master(db,user): return self.send(403,{'error':'Somente o administrador master pode alterar permissões.'})
                    target=data.get('username','')
                    sector=data.get('sector_id')
                    enabled=data.get('enabled')
                    if not isinstance(target,str) or not target or type(sector) is not int or type(enabled) is not bool:
                        return self.send(400,{'error':'Usuário, setor e permissão inválidos.'})
                    try:
                        members=sector_users(ROOT/'.env',sector)
                        save_forward_permission(db,user,target,sector,enabled,members)
                        db.commit()
                        return self.send(200,{'ok':True,'message':'Permissão salva no AssinaJA. Transferência real no MV ainda depende da integração e aprovação específicas.'})
                    except PermissionError as exc: return self.send(403,{'error':str(exc)})
                    except ValueError as exc: return self.send(400,{'error':str(exc)})
                    except Exception: return self.send(503,{'error':'Não foi possível salvar a permissão.'})
                if self.path == '/api/logout':
                    cookie = SimpleCookie(self.headers.get('Cookie',''))
                    if cookie.get('session'): SESSIONS.pop(cookie['session'].value,None)
                    return self.send(200,{'ok':True},'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if self.path == '/api/forward':
                    forward(db,user,int(data.get('document_id',0)),int(data.get('recipient_id',0)),data.get('reason',''))
                    db.commit()
                    return self.send(200,{'ok':True})
                return self.send(404,{'error':'Operação não disponível.'})
        except (ValueError,TypeError):
            return self.send(400,{'error': 'Dados inválidos ou encaminhamento não permitido. Verifique perfil, setor, área, situação e justificativa (10–1.000 caracteres).'})
        except sqlite3.Error:
            return self.send(503,{'error':'Banco indisponível. Tente novamente.'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AssinaJA: servidor de demonstração')
    parser.add_argument('--lan', action='store_true', help='Permitir conexões da rede local')
    args = parser.parse_args()
    initialize()
    configure_master()
    port = int(os.environ.get('PORT','8765'))
    address = '0.0.0.0' if args.lan else '127.0.0.1'
    try:
        httpd = ThreadingHTTPServer((address,port),Handler)
    except OSError:
        print(f'Não foi possível iniciar na porta {port}. Verifique se o AssinaJA já está aberto.',flush=True)
        raise SystemExit(1)
    print(f'AssinaJA demo: http://127.0.0.1:{port}',flush=True)
    if args.lan:
        for ip in sorted(set(socket.gethostbyname_ex(socket.gethostname())[2])):
            if not ip.startswith(('127.','169.254.')):
                print(f'Rede local: http://{ip}:{port}',flush=True)
    httpd.serve_forever()
