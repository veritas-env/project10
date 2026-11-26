"""Request and response bodies. Every input is length- and format-bounded and
unknown fields are rejected."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]{1,189}\.[A-Za-z]{2,24}$")

Role = Literal["viewer", "member", "manager", "owner"]
InviteRole = Literal["viewer", "member", "manager"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def normalize_email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 254 or not _EMAIL_RE.match(v):
        raise ValueError("invalid email address")
    return v


# --- auth -----------------------------------------------------------------------

class LoginIn(StrictModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v)


class PasswordChangeIn(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_platform_admin: bool


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


# --- workspaces, members, invitations ------------------------------------------

class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    role: str


class MemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    job_title: str | None
    role: str
    joined_at: datetime


class RoleIn(StrictModel):
    role: Role


class InvitationIn(StrictModel):
    email: str = Field(max_length=254)
    role: InviteRole = "member"

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v)


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


class InvitationCreated(InvitationOut):
    invite_url: str  # shown once to the inviter; the token isn't stored in clear


class InvitationPreview(BaseModel):
    workspace_name: str
    email: str
    role: str
    account_exists: bool


class InvitationTokenIn(StrictModel):
    token: str = Field(min_length=20, max_length=100)


class InvitationRegisterIn(InvitationTokenIn):
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


# --- warehouse ----------------------------------------------------------------------

POStatus = Literal["draft", "placed", "received", "cancelled"]


class LocationIn(StrictModel):
    code: str = Field(min_length=1, max_length=16, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(default="", max_length=80)


class LocationOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class ProductIn(StrictModel):
    sku: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=160)
    unit: str = Field(default="each", max_length=12, pattern=r"^[a-z]+$")
    reorder_level: int = Field(default=0, ge=0, le=1_000_000)


class ProductUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    unit: str | None = Field(default=None, max_length=12, pattern=r"^[a-z]+$")
    reorder_level: int | None = Field(default=None, ge=0, le=1_000_000)


class StockLevelOut(BaseModel):
    location_id: uuid.UUID
    location_code: str
    quantity: int


class ProductOut(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    unit: str
    reorder_level: int
    total_quantity: int
    low_stock: bool
    levels: list[StockLevelOut] = []


class AdjustIn(StrictModel):
    location_id: uuid.UUID
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    note: str = Field(default="", max_length=200)


class TransferIn(StrictModel):
    product_id: uuid.UUID
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    quantity: int = Field(ge=1, le=1_000_000)


class TransferOut(BaseModel):
    id: uuid.UUID
    reference: str
    product_id: uuid.UUID
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    quantity: int
    status: str
    created_at: datetime


class PurchaseOrderIn(StrictModel):
    supplier: str = Field(min_length=1, max_length=120)
    product_id: uuid.UUID
    location_id: uuid.UUID
    quantity: int = Field(ge=1, le=1_000_000)


class PurchaseOrderOut(BaseModel):
    id: uuid.UUID
    reference: str
    supplier: str
    product_id: uuid.UUID
    location_id: uuid.UUID
    quantity: int
    status: str
    created_at: datetime


class ActivityOut(BaseModel):
    id: int
    at: datetime
    actor_name: str | None
    summary: str


class DashboardOut(BaseModel):
    products: int
    locations: int
    total_units: int
    low_stock: int
    open_purchase_orders: int
    recent_activity: list[ActivityOut]


# --- platform admin -------------------------------------------------------------

class EventOut(BaseModel):
    id: int
    at: datetime
    type: str
    severity: str
    actor_user_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    ip: str | None
    request_id: str | None
    detail: dict


class AlertOut(BaseModel):
    id: int
    at: datetime
    rule: str
    severity: str
    summary: str
    event_id: int | None
    status: str