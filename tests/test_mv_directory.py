import base64
import tempfile
import unittest
from pathlib import Path
import legacy.server as server
from mv_directory import is_master,save_forward_permission
from mv_pending import authorized_scopes
from mv_document import decode_pdf

class AccessTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=server.DB
  server.DB=Path(self.temp.name)/'data'/'test.db';server.initialize();self.db=server.connect()
  for identifier,master in [(20,1),(21,0)]:
   self.db.execute('INSERT INTO users(id,username,mv_code) VALUES(?,?,?)',(identifier,str(identifier),str(identifier)))
   self.db.execute('INSERT INTO mv_accounts(user_id,all_sectors,enabled,is_master) VALUES(?,1,1,?)',(identifier,master))
  self.master=self.db.execute('SELECT * FROM users WHERE id=20').fetchone()
  self.member=self.db.execute('SELECT * FROM users WHERE id=21').fetchone()
 def tearDown(self):
  self.db.close();server.DB=self.old;self.temp.cleanup()
 def test_global_read_does_not_grant_master(self):
  self.assertEqual(authorized_scopes(self.db,self.member),[(None,None)])
  self.assertFalse(is_master(self.db,self.member))
  for actor in [self.member,self.db.execute('SELECT * FROM users WHERE id=7').fetchone()]:
   with self.assertRaises(PermissionError):save_forward_permission(self.db,actor,'21',1,True,[{'username':'21'}])
 def test_permission_and_audit_and_membership(self):
  for enabled in [True,False]:save_forward_permission(self.db,self.master,'21',1,enabled,[{'username':'21'}])
  self.assertEqual(self.db.execute('SELECT enabled FROM mv_forward_permissions').fetchone()[0],0)
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM mv_permission_audit').fetchone()[0],2)
  with self.assertRaises(ValueError):save_forward_permission(self.db,self.master,'21',2,True,[])
 def test_disabled_account_denied(self):
  self.db.execute('UPDATE mv_accounts SET enabled=0 WHERE user_id=21')
  self.assertEqual(authorized_scopes(self.db,self.member),[])
 def test_pdf_raw_base64_and_invalid(self):
  pdf=b'%PDF-1.7\nfixture'
  self.assertEqual(decode_pdf(pdf),pdf)
  self.assertEqual(decode_pdf(base64.b64encode(pdf)),pdf)
  for raw in [b'<html>bad</html>',base64.b64encode(b'not pdf')]:
   with self.assertRaises(ValueError):decode_pdf(raw)

 def test_directory_http_denies_nonmaster(self):
  import threading,time,urllib.request,urllib.error
  from unittest.mock import patch
  from http.server import ThreadingHTTPServer
  self.db.commit()
  server.SESSIONS['test-member']=(21,time.time()+60)
  httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
  try:
   with patch('legacy.server.sector_users') as directory:
    req=urllib.request.Request('http://127.0.0.1:'+str(httpd.server_port)+'/api/mv/users?sector=1',headers={'Cookie':'session=test-member'})
    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
    self.assertEqual(error.exception.code,403)
    error.exception.close()
    directory.assert_not_called()
  finally:
   httpd.shutdown();httpd.server_close();thread.join();server.SESSIONS.pop('test-member',None)
