from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidToolError


DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))


@dataclass(frozen=True)
class ToolFile:
    id: str
    label: str
    active_path: Path
    format: str
    path_label: str

    @property
    def filename(self) -> str:
        return self.active_path.name

    @property
    def ext(self) -> str:
        return self.active_path.suffix


@dataclass(frozen=True)
class ToolConfig:
    id: str
    name: str
    profile_dir: Path
    history_dir: Path
    lock_path: Path
    files: tuple[ToolFile, ...]

    @property
    def primary_file(self) -> ToolFile:
        return self.files[0]

    @property
    def active_path(self) -> Path:
        return self.primary_file.active_path

    @property
    def ext(self) -> str:
        return self.primary_file.ext

    @property
    def format(self) -> str:
        return self.primary_file.format

    @property
    def path_label(self) -> str:
        return " + ".join(file.path_label for file in self.files)

    def file_by_id(self, file_id: str) -> ToolFile:
        for file in self.files:
            if file.id == file_id:
                return file
        raise KeyError(file_id)


_codex_auth_path = Path(os.getenv("CODEX_CONFIG_PATH", "/config/codex/auth.json"))
_codex_toml_path = Path(os.getenv("CODEX_CONFIG_TOML_PATH", str(_codex_auth_path.with_name("config.toml"))))
_opencode_config_path = Path(os.getenv("OPENCODE_CONFIG_PATH", "/config/opencode/config.json"))


TOOLS: dict[str, ToolConfig] = {
    "claude": ToolConfig(
        id="claude",
        name="Claude",
        profile_dir=DATA_DIR / "profiles" / "claude",
        history_dir=DATA_DIR / "history" / "claude",
        lock_path=DATA_DIR / "locks" / "claude.lock",
        files=(
            ToolFile(
                id="settings",
                label="settings.json",
                active_path=Path(os.getenv("CLAUDE_CONFIG_PATH", "/config/claude/settings.json")),
                format="json",
                path_label="~/.claude/settings.json",
            ),
        ),
    ),
    "codex": ToolConfig(
        id="codex",
        name="Codex",
        profile_dir=DATA_DIR / "profiles" / "codex",
        history_dir=DATA_DIR / "history" / "codex",
        lock_path=DATA_DIR / "locks" / "codex.lock",
        files=(
            ToolFile(
                id="auth",
                label="auth.json",
                active_path=_codex_auth_path,
                format="json",
                path_label="~/.codex/auth.json",
            ),
            ToolFile(
                id="config",
                label="config.toml",
                active_path=_codex_toml_path,
                format="toml",
                path_label="~/.codex/config.toml",
            ),
        ),
    ),
    "opencode": ToolConfig(
        id="opencode",
        name="OpenCode",
        profile_dir=DATA_DIR / "profiles" / "opencode",
        history_dir=DATA_DIR / "history" / "opencode",
        lock_path=DATA_DIR / "locks" / "opencode.lock",
        files=(
            ToolFile(
                id="config",
                label="config.json",
                active_path=_opencode_config_path,
                format="json",
                path_label="~/.config/opencode/config.json",
            ),
        ),
    ),
}


def get_tool(tool_id: str) -> ToolConfig:
    try:
        return TOOLS[tool_id]
    except KeyError as exc:
        raise InvalidToolError() from exc


def public_tools() -> list[dict[str, str]]:
    return [
        {
            "id": tool.id,
            "name": tool.name,
            "format": tool.format,
            "profileExt": tool.ext,
            "pathLabel": tool.path_label,
            "files": [
                {
                    "id": file.id,
                    "label": file.label,
                    "filename": file.filename,
                    "format": file.format,
                    "pathLabel": file.path_label,
                }
                for file in tool.files
            ],
        }
        for tool in TOOLS.values()
    ]
