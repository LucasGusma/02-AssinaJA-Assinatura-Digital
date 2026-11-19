class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def integration_pending():
    return AppError('INTEGRATION_PENDING', 'Integração Oracle pendente: a package ainda não foi configurada.', 503)


ERRORS = {
    'INVALID_CREDENTIALS': (401, 'Usuário ou senha incorretos.'),
    'SESSION_EXPIRED': (401, 'Sua sessão expirou. Entre novamente.'),
    'FORBIDDEN': (403, 'Você não tem permissão para esta operação.'),
    'NOT_FOUND': (404, 'Registro não encontrado ou indisponível.'),
    'CONFLICT': (409, 'O registro foi atualizado. Consulte novamente antes de continuar.'),
    'INVALID_INPUT': (422, 'Confira os dados informados.'),
    'RATE_LIMITED': (429, 'Muitas tentativas. Aguarde antes de tentar novamente.'),
    'UNAVAILABLE': (503, 'Serviço Oracle temporariamente indisponível.'),
}
