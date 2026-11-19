import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
from mv_adapter import MVConfig, MVConfigurationError, oracle_readonly

class MVReadOnlyTest(unittest.TestCase):
    def test_env_preserves_literal_password_and_windows_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('MV_ENVIRONMENT=producao\nDB_USER=reader\nDB_PASSWORD="test#=$value"\nDB_DSN=db.test:1521/TEST\nDB_OWNER=usuario_banco\nORACLE_CLIENT_DIR=C:\\oracle\\client\n',encoding='utf-8')
            config, password = MVConfig.from_env(path)
            self.assertEqual(password,'test#=$value')
            self.assertEqual(config.client_dir,r'C:\oracle\client')
            self.assertEqual(config.owner,'USUARIO_BANCO')
            self.assertNotIn(password,repr(config))

    def test_incomplete_configuration_and_saved_password_rejected(self):
        base = {'environment':'homologacao','host':'db.test','port':1521,
                'service_name':'MVTEST','user':'reader','owner':'USUARIO_BANCO'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            for change in ({'host':''},{'password':'must-not-be-saved'},{'port':0}):
                path.write_text(json.dumps(base | change),encoding='utf-8')
                with self.assertRaises(MVConfigurationError):
                    MVConfig.from_file(path)

    def test_readonly_transaction_required_and_connection_closed(self):
        driver = MagicMock()
        connection = driver.connect.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        config = MVConfig('homologacao','db.test',1521,'MVTEST','reader','USUARIO_BANCO')
        with oracle_readonly(config,'test-password',driver):
            cursor.execute.assert_called_once_with('SET TRANSACTION READ ONLY')
        connection.close.assert_called_once()

    def test_readonly_failure_blocks_use_and_closes_connection(self):
        driver = MagicMock()
        connection = driver.connect.return_value
        connection.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError('denied')
        config = MVConfig('homologacao','db.test',1521,'MVTEST','reader','USUARIO_BANCO')
        with self.assertRaises(RuntimeError):
            with oracle_readonly(config,'test-password',driver):
                self.fail('Connection exposed after read-only transaction failed')
        connection.close.assert_called_once()
