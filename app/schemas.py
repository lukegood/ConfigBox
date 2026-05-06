from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConfigFileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    content: str
    last_known_mtime: float | None = Field(default=None, alias="lastKnownMtime")


class ConfigFileResponse(BaseModel):
    id: str
    label: str
    filename: str
    content: str
    format: str
    mtime: float | None
    pathLabel: str


class ActiveConfigResponse(BaseModel):
    tool: str
    content: str
    format: str
    mtime: float | None
    pathLabel: str
    files: list[ConfigFileResponse] = Field(default_factory=list)


class SaveActiveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content: str | None = None
    last_known_mtime: float | None = Field(default=None, alias="lastKnownMtime")
    files: list[ConfigFileRequest] | None = None


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


class ProfileResponse(BaseModel):
    tool: str
    name: str
    content: str
    format: str
    mtime: float | None
    files: list[ConfigFileResponse] = Field(default_factory=list)


class BackupResponse(BaseModel):
    tool: str
    name: str
    content: str
    format: str
    mtime: float | None
    files: list[ConfigFileResponse] = Field(default_factory=list)


class OkResponse(BaseModel):
    ok: bool = True
