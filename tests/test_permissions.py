import tempfile
import unittest
from pathlib import Path
import legacy.server as server

class PermissionsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = server.DB
        server.DB = Path(self.temp.name) / 'data' / 'test.db'
        server.initialize()
        self.db = server.connect()
        self.secretary = self.db.execute('SELECT * FROM users WHERE id=1').fetchone()

    def tearDown(self):
        self.db.close()
        server.DB = self.old
        self.temp.cleanup()

    def test_forward_preserves_author_and_audits(self):
        server.forward(self.db,self.secretary,1,2,'Ausência do profissional responsável')
        row = self.db.execute('SELECT * FROM documents WHERE id=1').fetchone()
        self.assertEqual(row['author'],'André Lima')
        self.assertEqual(row['assignee'],2)
        self.assertEqual(row['status'],'encaminhado')
        audit = self.db.execute("SELECT * FROM audit WHERE action='Encaminhamento'").fetchone()
        self.assertEqual(audit['actor'],1)
        self.assertIn('Ausência',audit['detail'])

    def test_cross_area_sector_and_wrong_role_rejected(self):
        for recipient in (4,5,6,7,9):
            with self.subTest(recipient=recipient),self.assertRaises(ValueError):
                server.forward(self.db,self.secretary,1,recipient,'Justificativa de teste')

    def test_other_documents_and_signed_rejected(self):
        for document in (5,6,7,8,9):
            with self.subTest(document=document),self.assertRaises(ValueError):
                server.forward(self.db,self.secretary,document,2,'Justificativa de teste')

    def test_non_secretary_and_duplicate_rejected(self):
        for user_id in (2,4,7):
            user=self.db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
            with self.assertRaises(ValueError):
                server.forward(self.db,user,1,2,'Justificativa de teste')
        server.forward(self.db,self.secretary,1,3,'Justificativa de teste')
        with self.assertRaises(ValueError):
            server.forward(self.db,self.secretary,1,2,'Justificativa de teste')

    def test_scope(self):
        for doc in self.db.execute('SELECT * FROM documents'):
            self.assertEqual(server.visible(self.secretary,doc),doc['sector']=='Clínica médica' and doc['area']=='Medicina')

    def test_reason_required(self):
        for reason in ('','curta',' '*20,'a'*1001,None):
            with self.assertRaises(ValueError):
                server.forward(self.db,self.secretary,1,2,reason)

if __name__ == '__main__': unittest.main()
