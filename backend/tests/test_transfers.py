from unittest.mock import MagicMock

import pytest

from backend.app.core.errors import AppError
from backend.app.infrastructure.oracle.transfers import transfer, eligibility
from backend.app.infrastructure.oracle.transfers import batch


@pytest.mark.parametrize('providers,events,success', [([(7,), (7,)], [101, 102], True),
                                                    ([(7,), (8,)], [], False),
                                                    ([(7,), (7,)], [101, None], False)])
def test_batch_requires_same_provider_and_commits_only_whole_batch(providers, events, success):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = providers
    cursor.var.return_value.getvalue.side_effect = events
    payload = {'documents': [{'document_id': i, 'expected_owner': 'OLD', 'idempotency_key': str(i)}
                             for i in (1, 2)], 'recipient': 'NEW', 'reason': 'Justificativa teste'}
    if success:
        result = batch(connection, 'ACTOR', payload, 'trace')
        assert len(result['transfers']) == 2
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()
        assert all(call.args[1][3] == 'NEW' for call in cursor.callproc.call_args_list)
    else:
        with pytest.raises(AppError):
            batch(connection, 'ACTOR', payload, 'trace')
        connection.commit.assert_not_called()
        connection.rollback.assert_called_once()


def test_transfer_commits_only_after_valid_oracle_confirmation():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.var.return_value.getvalue.return_value = 123
    payload = {'document_id': 42, 'expected_owner': 'OLD', 'recipient': 'NEW',
               'reason': 'Motivo de teste', 'idempotency_key': 'request-key'}
    result = transfer(connection, 'ACTOR', payload, 'trace')
    assert result['transfer_id'] == '123'
    assert cursor.callproc.call_args.args[0] == 'SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.TRANSFERIR'
    assert cursor.callproc.call_args.args[1][:7] == ['ACTOR', 42, 'OLD', 'NEW', 'Motivo de teste', 'request-key', 'trace']
    connection.commit.assert_called_once()


@pytest.mark.parametrize('event', [None, 0, -1])
def test_invalid_confirmation_never_commits(event):
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.var.return_value.getvalue.return_value = event
    with pytest.raises(AppError):
        transfer(connection, 'ACTOR', {'document_id': 42, 'expected_owner': 'OLD', 'recipient': 'NEW',
                 'reason': 'Motivo de teste', 'idempotency_key': 'key'}, 'trace')
    connection.commit.assert_not_called()


def test_missing_previous_owner_never_calls_oracle():
    connection = MagicMock()
    with pytest.raises(AppError):
        transfer(connection, 'ACTOR', {}, 'trace')
    connection.cursor.assert_not_called()


def test_eligibility_batches_identifiers_as_binds():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(10, None), (11, 'Documento assinado')]
    assert eligibility(connection, [10, 11]) == {10: None, 11: 'Documento assinado'}
    assert cursor.execute.call_args.args[1] == {'id0': 10, 'id1': 11}
