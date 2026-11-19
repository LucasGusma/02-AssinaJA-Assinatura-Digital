from uuid import uuid4

from starlette.responses import JSONResponse


class SecurityMiddleware:
    """Same-origin JSON mutations with a mandatory custom header prevent CSRF.

    No credentialed CORS is enabled. Reverse proxies must preserve Origin and
    Host. All request bodies are bounded, including chunked HTTP requests.
    """
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope.setdefault('state', {})['request_id'] = request_id
        headers = {key.lower(): value for key, value in scope.get('headers', [])}

        async def safe_send(message):
            if message['type'] == 'http.response.start':
                response_headers = list(message.get('headers', []))
                existing = {key.lower() for key, _ in response_headers}
                additions = {
                    b'x-request-id': request_id.encode(),
                    b'x-content-type-options': b'nosniff',
                    b'referrer-policy': b'no-referrer',
                    b'x-frame-options': b'DENY',
                    b'content-security-policy': b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
                }
                if scope['path'].startswith('/api'):
                    additions[b'cache-control'] = b'no-store'
                if self.settings.app_environment == 'production':
                    additions[b'strict-transport-security'] = b'max-age=31536000'
                response_headers.extend((key, value) for key, value in additions.items() if key not in existing)
                message['headers'] = response_headers
            await send(message)

        async def reject(status, code, message):
            response = JSONResponse({'error': {'code': code, 'message': message, 'request_id': request_id}}, status_code=status)
            await response(scope, receive, safe_send)

        if scope['method'] in ('POST', 'PUT', 'PATCH', 'DELETE'):
            origin = headers.get(b'origin', b'').decode('latin-1')
            if origin not in self.settings.allowed_origins or headers.get(b'x-csrf-protection') != b'1':
                return await reject(403, 'INVALID_ORIGIN', 'Origem da requisição não autorizada.')
            if headers.get(b'content-type', b'').split(b';')[0].strip().lower() != b'application/json':
                return await reject(415, 'INVALID_CONTENT_TYPE', 'Envie dados no formato JSON.')
            chunks, length = [], 0
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                length += len(message.get('body', b''))
                if length > 8192:
                    return await reject(413, 'REQUEST_TOO_LARGE', 'Requisição excede o limite permitido.')
                chunks.append(message.get('body', b''))
                if not message.get('more_body', False):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
                return await receive()

            return await self.app(scope, replay, safe_send)
        return await self.app(scope, receive, safe_send)
