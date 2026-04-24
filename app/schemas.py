from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ActiveConfigResponse(BaseModel):
    tool: str
    content: str
    format: str
    mtime: float | None
    pathLabel: str


class SaveActiveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content: str
    last_known_mtime: float | None = Field(default=None, alias="lastKnownMtime")


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileCreateRequest(BaseModel):
    name: str
    source: str = "active"
    content: str | None = None


class ProfileSaveRequest(BaseModel):
    content: str


class ProfileResponse(BaseModel):
    tool: str
    name: str
    content: str
    format: str
    mtime: float | None


class BackupResponse(BaseModel):
    tool: str
    name: str
    content: str
    format: str
    mtime: float | None


class OkResponse(BaseModel):
    ok: bool = True
