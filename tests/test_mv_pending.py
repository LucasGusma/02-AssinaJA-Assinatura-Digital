import unittest
from datetime import datetime
from unittest.mock import MagicMock
from mv_pending import pending_query, query_pending, authorized_scopes

class PendingTest(unittest.TestCase):
    def test_sql_enforces_closed_signature_and_paired_scopes(self):
        sql,params=pending_query([(10,20),(30,40)],'2026-10-01','2026-10-06',100)
        self.assertIn("d.TP_STATUS = 'FECHADO'",sql)
        self.assertIn("o.SN_ASSINATURA = 'S'",sql)
        self.assertIn('(d.CD_SETOR = :sector_0 AND d.CD_OBJETO = :object_0)',sql)
        self.assertEqual(params['end_date'],datetime(2026,10,7))
        self.assertEqual(params['before_id'],100)

    def test_invalid_request_rejected_before_query(self):
        for scopes,start,end in [([], '2026-10-01','2026-10-06'),([(1,2)],'2026-01-01','2026-10-06'),([(1,2)],'2026-10-06','2026-10-01'),([('1 OR 1=1',2)],'2026-10-01','2026-10-06')]:
            with self.assertRaises((ValueError,PermissionError)):
                pending_query(scopes,start,end)

    def test_public_demo_account_cannot_receive_real_records(self):
        db=MagicMock()
        self.assertEqual(authorized_scopes(db,{'mv_code':'DEMO-007','id':7}),[])
        db.execute.assert_not_called()

    def test_nonpending_or_out_of_scope_results_rejected(self):
        for status,sector in [('ABERTO',10),('ASSINADO',10),('FECHADO',99)]:
            conn=MagicMock()
            conn.cursor.return_value.__enter__.return_value.fetchmany.return_value=[(1,2,3,'user',4,status,datetime(2026,10,1),20,'title','type','S',sector)]
            with self.assertRaises(PermissionError):
                query_pending(conn,[(10,20)],'2026-10-01','2026-10-06')

    def test_keyset_next_page_does_not_include_extra_record(self):
        conn=MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchmany.return_value=[(i,2,3,'user',4,'FECHADO',datetime(2026,10,1),20,'title','type','S',10) for i in (100,99,98)]
        result=query_pending(conn,[(10,20)],'2026-10-01','2026-10-06',limit=2)
        self.assertEqual([d['id'] for d in result['documents']],[100,99])
        self.assertEqual(result['next_cursor'],99)
