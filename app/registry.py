from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidToolError


DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))


@dataclass(frozen=True)
class ToolConfig:
    id: str
    name: str
    active_path: Path
    profile_dir: Path
    backup_dir: Path
    lock_path: Path
    ext: str
    format: str
    path_label: str


TOOLS: dict[str, ToolConfig] = {
    "claude": ToolConfig(
        id="claude",
        name="Claude",
        active_path=Path(os.getenv("CLAUDE_CONFIG_PATH", "/config/claude/settings.json")),
        profile_dir=DATA_DIR / "profiles" / "claude",
        backup_dir=DATA_DIR / "backups" / "claude",
        lock_path=DATA_DIR / "locks" / "claude.lock",
        ext=".json",
        format="json",
        path_label="~/.claude/settings.json",
    ),
    "codex": ToolConfig(
        id="codex",
        name="Codex",
        active_path=Path(os.getenv("CODEX_CONFIG_PATH", "/config/codex/auth.json")),
        profile_dir=DATA_DIR / "profiles" / "codex",
        backup_dir=DATA_DIR / "backups" / "codex",
        lock_path=DATA_DIR / "locks" / "codex.lock",
        ext=".json",
        format="json",
        path_label="~/.codex/auth.json",
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
        }
        for tool in TOOLS.values()
    ]
