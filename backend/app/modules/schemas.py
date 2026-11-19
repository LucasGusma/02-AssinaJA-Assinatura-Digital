"""Public API schemas. Packages return data matching these contracts."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Login(Input):
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=256)


class User(BaseModel):
    username: str
    name: str
    is_master: bool = False
    can_transfer: bool = False
    all_sectors: bool = False


class Session(BaseModel):
    user: User


class LoginResult(Session):
    token: str = Field(min_length=32, max_length=512, pattern=r'^[A-Za-z0-9_-]+$')
    expires_in: int = Field(ge=1, le=28800)


class Sector(BaseModel):
    id: int = Field(ge=0)
    name: str


class Sectors(BaseModel):
    sectors: list[Sector]


class Member(BaseModel):
    username: str
    name: str
    profile: str | None = None
    can_forward: bool = False


class Members(BaseModel):
    users: list[Member]


class Document(BaseModel):
    id: int = Field(gt=0)
    title: str
    patient_name: str | None = None
    attendance_id: int | None = None
    provider_id: int | None = None
    provider_name: str | None = None
    mv_user: str | None = None
    sector_id: int | None = None
    sector_name: str | None = None
    created: datetime | None = None
    discharge_at: str | None = None
    status: str
    can_transfer: bool = False
    transfer_block_reason: str | None = None


class Documents(BaseModel):
    documents: list[Document] = Field(max_length=50)
    next_cursor: int | None = Field(default=None, gt=0)


class DocumentField(BaseModel):
    label: str
    value: str
    truncated: bool = False


class Content(BaseModel):
    kind: Literal['pdf', 'editor', 'unavailable']
    title: str | None = None
    fields: list[DocumentField] = Field(default_factory=list, max_length=300)
    partial: bool = False
    message: str | None = None


class PermissionChange(Input):
    username: str = Field(min_length=1, max_length=128)
    sector_id: int = Field(ge=0)
    enabled: bool = Field(strict=True)


class Transfer(Input):
    recipient: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=10, max_length=1000)
    idempotency_key: UUID
    expected_owner: str | None = Field(default=None, min_length=1, max_length=128)


class TransferResult(BaseModel):
    transfer_id: str
    message: str


class AuditEvent(BaseModel):
    request_id: str | None = None
    id: int
    created: datetime
    actor: str
    action: str
    detail: str
    document_id: int | None = None
    source_user: str | None = None
    source_name: str | None = None
    target_user: str | None = None
    target_name: str | None = None


class AuditPage(BaseModel):
    events: list[AuditEvent] = Field(max_length=50)
    next_cursor: int | None = Field(default=None, gt=0)


class BatchItem(Input):
    document_id: int = Field(gt=0)
    expected_owner: str = Field(min_length=1, max_length=128)
    idempotency_key: UUID


class BatchTransfer(Input):
    documents: list[BatchItem] = Field(min_length=1, max_length=50)
    recipient: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=10, max_length=1000)
