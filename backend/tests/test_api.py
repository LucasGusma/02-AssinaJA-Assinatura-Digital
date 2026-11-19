from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import Settings
from backend.app.core.errors import AppError
from backend.app.main import create_app

HEADERS = {'Origin': 'http://localhost:8765', 'X-CSRF-Protection': '1'}
TOKEN = 'a' * 43


class FakeGateway:
    configured = True

    def __init__(self):
        self.calls = []
        self.user = {'username': 'TEST', 'name': 'Usuário de teste', 'is_master': False, 'can_transfer': True, 'all_sectors': False}
        self.active = True

    def call(self, operation, payload, session, request_id):
        self.calls.append((operation, payload, session))
        if operation == 'health.ready':
            return {}
        if operation == 'auth.login':
            self.active = True
            return {'user': self.user, 'token': TOKEN, 'expires_in': 3600}
        if session != TOKEN or not self.active:
            raise AppError('SESSION_EXPIRED', 'Sessão expirada.', 401)
        if operation == 'auth.session':
            return {'user': self.user}
        if operation == 'auth.logout':
            self.active = False
            return {}
        if operation == 'documents.list':
            return {'documents': [], 'next_cursor': None}
        if operation == 'documents.content':
            raise AppError('FORBIDDEN', 'Documento fora do escopo.', 403)
        if operation == 'directory.sectors':
            return {'sectors': [{'id': 1, 'name': 'Setor de teste'}]}
        if operation in ('directory.users', 'directory.recipients'):
            return {'users': []}
        if operation == 'permissions.update':
            return {}
        if operation == 'transfers.create':
            return {'transfer_id': 'TEST-1', 'message': 'Transferência confirmada.'}
        if operation == 'audit.list':
            return {'events': [], 'next_cursor': None}
        raise AssertionError(operation)

    def file(self, document_id, session, request_id):
        self.calls.append(('file', {'document_id': document_id}, session))
        raise AppError('FORBIDDEN', 'Documento fora do escopo.', 403)


@contextmanager
def client_for(gateway=None, **options):
    settings = Settings(_env_file=None, app_environment='test', **options)
    with TestClient(create_app(settings, gateway)) as client:
        yield client


def login(client):
    return client.post('/api/v1/auth/login', json={'username': 'TEST', 'password': 'test-password'}, headers=HEADERS)


def test_pending_integration_does_not_open_oracle_or_fake_login():
    with client_for() as client:
        assert client.get('/api/health/live').status_code == 200
        assert client.get('/api/health/ready').status_code == 503
        assert client.get('/api/v1/status').json()['integration'] == 'pending'
        assert login(client).status_code == 503


def test_login_cookie_and_revocation():
    gateway = FakeGateway()
    with client_for(gateway) as client:
        response = login(client)
        assert response.status_code == 200
        cookie = response.headers['set-cookie']
        assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Path=/api' in cookie
        assert 'token' not in response.json()
        assert client.get('/api/v1/auth/session').status_code == 200
        assert client.post('/api/v1/auth/logout', json={}, headers=HEADERS).status_code == 204
        client.cookies.set('assinaja_session', TOKEN)
        assert client.get('/api/v1/auth/session').status_code == 401


@pytest.mark.parametrize('headers', [{}, {'Origin': 'https://evil.test', 'X-CSRF-Protection': '1'}, {'Origin': 'http://localhost:8765'}])
def test_csrf_rejects_requests_before_gateway(headers):
    gateway = FakeGateway()
    with client_for(gateway) as client:
        assert client.post('/api/v1/auth/login', json={'username': 'TEST', 'password': 'secret'}, headers=headers).status_code == 403
        assert gateway.calls == []


def test_invalid_input_never_echoes_credentials_and_body_is_bounded():
    with client_for(FakeGateway()) as client:
        response = client.post('/api/v1/auth/login', json={'username': 'TEST', 'password': 'do-not-echo', 'extra': 'not-allowed'}, headers=HEADERS)
        assert response.status_code == 422 and 'do-not-echo' not in response.text
        response = client.post('/api/v1/auth/login', content=b'x' * 8193, headers={**HEADERS, 'Content-Type': 'application/json'})
        assert response.status_code == 413


def test_nonmaster_can_read_users_but_cannot_change_permissions():
    gateway = FakeGateway()
    with client_for(gateway) as client:
        login(client)
        assert client.get('/api/v1/users?sector=1').status_code == 200
        assert client.put('/api/v1/permissions', json={'username': 'OTHER', 'sector_id': 1, 'enabled': True}, headers=HEADERS).status_code == 403
        assert not any(op == 'permissions.update' for op, _, _ in gateway.calls)


def test_master_permissions_and_unknown_fields():
    gateway = FakeGateway()
    gateway.user['is_master'] = True
    with client_for(gateway) as client:
        login(client)
        assert client.get('/api/v1/users?sector=1').status_code == 200
        payload = {'username': 'OTHER', 'sector_id': 1, 'enabled': True}
        assert client.put('/api/v1/permissions', json=payload, headers=HEADERS).status_code == 200
        assert client.put('/api/v1/permissions', json={**payload, 'actor': 'ADMIN'}, headers=HEADERS).status_code == 422


def test_document_scope_is_enforced_on_content_and_file():
    gateway = FakeGateway()
    with client_for(gateway) as client:
        login(client)
        assert client.get('/api/v1/documents/42/content').status_code == 403
        assert client.get('/api/v1/documents/42/file').status_code == 403
        assert all(session == TOKEN for operation, _, session in gateway.calls if operation != 'auth.login')


def test_pagination_validates_period_and_preserves_cursor():
    gateway = FakeGateway()
    with client_for(gateway) as client:
        login(client)
        assert client.get('/api/v1/documents?start=2026-10-01&end=2026-10-08&before=55').status_code == 200
        assert gateway.calls[-1][1]['before'] == 55
        gateway.calls.clear()
        assert client.get('/api/v1/documents?start=2026-01-01&end=2026-10-08').status_code == 422
        assert not any(operation == 'documents.list' for operation, _, _ in gateway.calls)


def test_document_scope_is_explicit_and_cannot_select_another_owner():
    gateway = FakeGateway()
    with client_for(gateway) as client:
        login(client)
        url = '/api/v1/documents?start=2026-10-01&end=2026-10-09'
        for scope in ('all', 'mine'):
            assert client.get(url + '&scope=' + scope + '&username=OTHER').status_code == 200
            assert gateway.calls[-1][1]['scope'] == scope
            assert 'username' not in gateway.calls[-1][1]
        assert client.get(url + '&scope=OTHER').status_code == 422
    with client_for(gateway) as client:
        assert client.get(url + '&scope=all').status_code == 401


def test_transfer_requires_activation_and_passes_idempotency_key():
    gateway = FakeGateway()
    payload = {'recipient': 'OTHER', 'reason': 'Justificativa de teste', 'idempotency_key': str(uuid4())}
    with client_for(gateway) as client:
        login(client)
        assert client.post('/api/v1/documents/42/transfers', json=payload, headers=HEADERS).status_code == 503
    with client_for(gateway, transfers_enabled=True) as client:
        login(client)
        assert client.post('/api/v1/documents/42/transfers', json=payload, headers=HEADERS).status_code == 200
        assert gateway.calls[-1][1]['idempotency_key'] == payload['idempotency_key']


def test_sensitive_api_has_security_headers_and_no_static_secret_routes():
    with client_for() as client:
        response = client.get('/api/v1/status')
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['x-request-id']
        assert client.get('/.env').status_code == 404
        assert client.get('/api/missing').status_code == 404


def test_local_limiter_is_bounded_and_production_requires_https():
    from backend.app.core.security import LoginLimiter
    from pydantic import ValidationError
    limiter = LoginLimiter(limit=1, max_keys=2)
    limiter.check('a')
    with pytest.raises(AppError):
        limiter.check('a')
    limiter.check('b')
    limiter.check('c')
    assert len(limiter.entries) == 2
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_environment='production')


@pytest.mark.parametrize('start,end,expected', [
    ('2026-07-15', '2026-10-15', 200),
    ('2026-07-14', '2026-10-15', 422),
    ('2026-02-28', '2026-05-31', 200),
    ('2026-02-27', '2026-05-31', 422),
])
def test_three_calendar_months_boundary(start, end, expected):
    gateway = FakeGateway()
    with client_for(gateway) as client:
        login(client)
        response = client.get('/api/v1/documents', params={'start': start, 'end': end, 'document_type': 7})
        assert response.status_code == expected
        if expected == 200:
            assert gateway.calls[-1][1]['document_type'] == 7
