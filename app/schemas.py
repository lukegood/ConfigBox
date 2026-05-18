from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConfigFileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    content: str
    last_known_mtime: float | None = Field(default=None, alias="lastKnownMtime")


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileCreateRequest(BaseModel):
    name: str
    source: str = "active"
    content: str | None = None
    files: list[ConfigFileRequest] | None = None


class ProfileSaveRequest(BaseModel):
    content: str | None = None
    files: list[ConfigFileRequest] | None = None


class OkResponse(BaseModel):
    ok: bool = True
