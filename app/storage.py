from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock, Timeout

from .errors import APIError
from .registry import DATA_DIR, TOOLS, ToolConfig
from .validators import validate_backup_name, validate_content, validate_profile_name


STATE_PATH = DATA_DIR / "state.json"


def backup_retention() -> int:
    raw = os.getenv("BACKUP_RETENTION", "50")
    try:
        return max(1, int(raw))
    except ValueError:
        return 50


def default_content(tool: ToolConfig) -> str:
    return "{}\n" if tool.format == "json" else ""


def ensure_dirs(tool: ToolConfig) -> None:
    tool.active_path.parent.mkdir(parents=True, exist_ok=True)
    tool.profile_dir.mkdir(parents=True, exist_ok=True)
    tool.backup_dir.mkdir(parents=True, exist_ok=True)
    tool.lock_path.parent.mkdir(parents=True, exist_ok=True)


def ensure_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for tool in TOOLS.values():
        ensure_dirs(tool)
        if not tool.active_path.exists():
            atomic_write(tool.active_path, default_content(tool))
        default_profile = profile_path(tool, "default")
        if not default_profile.exists():
            atomic_write(default_profile, read_text_or_default(tool.active_path, default_content(tool)))
    if not STATE_PATH.exists():
        atomic_write(STATE_PATH, json.dumps({}, indent=2) + "\n")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        fsync_dir(path.parent)
    finally:
        if tmp_name:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def file_mtime(path: Path) -> float | None:
    if not path.exists():
        return None
    return path.stat().st_mtime


def read_text_or_default(path: Path, default: str) -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def lock_for(tool: ToolConfig) -> FileLock:
    return FileLock(str(tool.lock_path), timeout=5)


def backup_active(tool: ToolConfig, reason: str = "manual") -> Path | None:
    ensure_dirs(tool)
    src = tool.active_path
    if not src.exists():
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    dst = tool.backup_dir / f"{src.name}.{ts}.{reason}.bak"
    atomic_write(dst, src.read_text(encoding="utf-8"))
    prune_backups(tool)
    return dst


def prune_backups(tool: ToolConfig) -> None:
    backups = sorted(
        [path for path in tool.backup_dir.iterdir() if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_path in backups[backup_retention() :]:
        old_path.unlink(missing_ok=True)


def read_active(tool: ToolConfig) -> dict:
    ensure_dirs(tool)
    content = read_text_or_default(tool.active_path, default_content(tool))
    return {
        "tool": tool.id,
        "content": content,
        "format": tool.format,
        "mtime": file_mtime(tool.active_path),
        "pathLabel": tool.path_label,
    }


def save_active(tool: ToolConfig, content: str, last_known_mtime: float | None) -> dict:
    validate_content(tool.format, content)
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            current_mtime = file_mtime(tool.active_path)
            if (
                last_known_mtime is not None
                and current_mtime is not None
                and abs(current_mtime - last_known_mtime) > 0.0001
            ):
                raise APIError(
                    "CONFLICT_MODIFIED_EXTERNALLY",
                    "File was modified outside the web UI. Reload before saving.",
                    409,
                )
            backup_active(tool, "save")
            atomic_write(tool.active_path, content)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_active(tool)


def profile_path(tool: ToolConfig, name: str) -> Path:
    validate_profile_name(name)
    return tool.profile_dir / f"{name}{tool.ext}"


def list_profiles(tool: ToolConfig) -> list[dict]:
    ensure_dirs(tool)
    state = read_state().get(tool.id, {})
    items = []
    for path in sorted(tool.profile_dir.glob(f"*{tool.ext}")):
        name = path.name[: -len(tool.ext)]
        if not path.is_file():
            continue
        items.append(
            {
                "name": name,
                "mtime": file_mtime(path),
                "active": state.get("activeProfile") == name,
            }
        )
    return items


def read_profile(tool: ToolConfig, name: str) -> dict:
    path = profile_path(tool, name)
    if not path.exists():
        raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)
    return {
        "tool": tool.id,
        "name": name,
        "content": path.read_text(encoding="utf-8"),
        "format": tool.format,
        "mtime": file_mtime(path),
    }


def create_profile(tool: ToolConfig, name: str, source: str, content: str | None = None) -> dict:
    path = profile_path(tool, name)
    if source not in {"active", "empty", "content"}:
        raise APIError("INVALID_PROFILE_SOURCE", "Profile source must be active, empty, or content.", 400)
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            if path.exists():
                raise APIError("PROFILE_EXISTS", "Profile already exists.", 409)
            if source == "active":
                profile_content = read_text_or_default(tool.active_path, default_content(tool))
            elif source == "content":
                profile_content = content or default_content(tool)
            else:
                profile_content = default_content(tool)
            validate_content(tool.format, profile_content)
            atomic_write(path, profile_content)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, name)


def save_profile(tool: ToolConfig, name: str, content: str) -> dict:
    path = profile_path(tool, name)
    validate_content(tool.format, content)
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            if not path.exists():
                raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)
            atomic_write(path, content)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, name)


def delete_profile(tool: ToolConfig, name: str) -> None:
    path = profile_path(tool, name)
    ensure_dirs(tool)
    state = read_state().get(tool.id, {})
    if state.get("activeProfile") == name:
        raise APIError("PROFILE_ACTIVE", "Cannot delete the currently active profile.", 409)
    try:
        with lock_for(tool):
            if not path.exists():
                raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)
            path.unlink()
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc


def activate_profile(tool: ToolConfig, name: str) -> dict:
    profile = read_profile(tool, name)
    validate_content(tool.format, profile["content"])
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            backup_active(tool, "activate")
            atomic_write(tool.active_path, profile["content"])
            state = read_state()
            state[tool.id] = {
                "activeProfile": name,
                "lastActivatedAt": datetime.now(timezone.utc).isoformat(),
            }
            write_state(state)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_active(tool)


def list_backups(tool: ToolConfig) -> list[dict]:
    ensure_dirs(tool)
    backups = []
    for path in sorted(tool.backup_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.is_file():
            backups.append({"name": path.name, "mtime": file_mtime(path), "size": path.stat().st_size})
    return backups


def backup_path(tool: ToolConfig, name: str) -> Path:
    validate_backup_name(name)
    path = tool.backup_dir / name
    try:
        path.resolve().relative_to(tool.backup_dir.resolve())
    except ValueError as exc:
        raise APIError("INVALID_BACKUP_NAME", "Invalid backup name.", 400) from exc
    return path


def read_backup(tool: ToolConfig, name: str) -> dict:
    path = backup_path(tool, name)
    if not path.exists() or not path.is_file():
        raise APIError("BACKUP_NOT_FOUND", "Backup not found.", 404)
    return {
        "tool": tool.id,
        "name": name,
        "content": path.read_text(encoding="utf-8"),
        "format": tool.format,
        "mtime": file_mtime(path),
    }


def restore_backup(tool: ToolConfig, name: str) -> dict:
    backup = read_backup(tool, name)
    validate_content(tool.format, backup["content"])
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            backup_active(tool, "restore")
            atomic_write(tool.active_path, backup["content"])
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_active(tool)


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def write_state(state: dict) -> None:
    atomic_write(STATE_PATH, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
