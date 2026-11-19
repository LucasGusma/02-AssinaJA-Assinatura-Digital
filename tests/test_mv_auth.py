import unittest
from unittest.mock import patch, MagicMock
from mv_auth import authenticate
from mv_pending import pending_query, authorized_scopes

class InstitutionalAuthTest(unittest.TestCase):
    @patch('mv_auth.oracle_readonly')
    @patch('mv_auth.MVConfig.from_env')
    def test_password_not_returned_and_username_is_bound(self,load,connection):
        load.return_value=(object(),'database-secret')
        cursor=connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value=('Test User',)
        self.assertEqual(authenticate('.env','f015114','test-only'),'Test User')
        sql=cursor.execute.call_args.args[0]
        self.assertIn("SN_ATIVO='S'",sql)
        self.assertNotIn('test-only',sql)
        self.assertEqual(cursor.execute.call_args.kwargs['username'],'ADMIN')
        cursor.fetchone.return_value=None
        self.assertIsNone(authenticate('.env','f015114','incorrect'))

    def test_master_access_requires_explicit_account_grant(self):
        db=MagicMock()
        db.execute.return_value.fetchone.return_value=None
        self.assertEqual(authorized_scopes(db,{'mv_code':'ADMIN','id':10}),[])
        db.execute.return_value.fetchone.return_value={'all_sectors':1}
        self.assertEqual(authorized_scopes(db,{'mv_code':'ADMIN','id':10}),[(None,None)])
        sql,params=pending_query([(None,None)],'2026-10-01','2026-10-06')
        self.assertIn("d.TP_STATUS = 'FECHADO'",sql)
        sql,params=pending_query([(12,None)],'2026-10-01','2026-10-06')
        self.assertIn('d.CD_SETOR = :sector_0',sql)
        self.assertEqual(params['sector_0'],12)
