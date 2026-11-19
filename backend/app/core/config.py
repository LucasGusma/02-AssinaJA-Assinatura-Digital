"""Validated settings. Process environment overrides the local .env file."""
from functools import lru_cache
from pathlib import Path
import re
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
ROUTINE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*\.[A-Za-z][A-Za-z0-9_$#]*(?:\.[A-Za-z][A-Za-z0-9_$#]*)?$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', env_file_encoding='utf-8-sig', extra='ignore')

    app_environment: str = 'development'
    db_user: str = ''
    db_password: SecretStr = SecretStr('')
    db_dsn: str = ''
    oracle_client_dir: str = ''
    # Empty until the DBA confirms the contracts documented in docs/oracle-contract.md.
    oracle_package_routine: str = ''
    oracle_file_routine: str = ''
    oracle_integration_mode: Literal['json', 'mv_refcursor'] = 'json'
    oracle_mv_package: str = 'SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA'
    oracle_pool_min: int = Field(default=1, ge=0, le=20)
    oracle_pool_max: int = Field(default=5, ge=1, le=50)
    oracle_pool_wait_ms: int = Field(default=3000, ge=100, le=30000)
    oracle_call_timeout_ms: int = Field(default=15000, ge=1000, le=120000)
    session_cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=3600, ge=300, le=28800)
    allowed_hosts: list[str] = ['127.0.0.1', 'localhost', 'testserver']
    allowed_origins: list[str] = ['http://127.0.0.1:8765', 'http://localhost:8765', 'http://localhost:5173', 'http://127.0.0.1:5173']
    transfers_enabled: bool = False
    frontend_dist: Path = ROOT / 'frontend' / 'dist'

    @model_validator(mode='after')
    def validate_configuration(self):
        if self.app_environment not in ('development', 'test', 'production'):
            raise ValueError('APP_ENVIRONMENT inválido')
        if self.oracle_pool_min > self.oracle_pool_max:
            raise ValueError('Pool mínimo maior que o máximo')
        for value in (self.oracle_package_routine, self.oracle_file_routine, self.oracle_mv_package):
            if value and not ROUTINE.fullmatch(value):
                raise ValueError('Rotina Oracle deve usar PACKAGE.PROCEDURE ou SCHEMA.PACKAGE.PROCEDURE')
        if self.oracle_file_routine and not self.oracle_package_routine:
            raise ValueError('Configure primeiro a rotina principal')
        if self.oracle_configured and not all((self.db_user, self.db_password.get_secret_value(), self.db_dsn, self.oracle_client_dir)):
            raise ValueError('Conexão e Instant Client obrigatórios para ativar a package')
        if self.app_environment == 'production':
            if not self.session_cookie_secure or not self.allowed_origins or any(not origin.startswith('https://') for origin in self.allowed_origins):
                raise ValueError('Produção exige HTTPS e cookie Secure')
            if not self.allowed_hosts or any('*' in host or host == 'testserver' for host in self.allowed_hosts):
                raise ValueError('Produção exige hosts explícitos')
        return self

    @property
    def oracle_configured(self):
        return self.oracle_integration_mode == 'mv_refcursor' or bool(self.oracle_package_routine)


@lru_cache
def get_settings() -> Settings:
    return Settings()
