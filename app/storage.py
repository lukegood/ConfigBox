from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from .errors import APIError
from .registry import DATA_DIR, TOOLS, ToolConfig, ToolFile
from .validators import validate_backup_name, validate_content, validate_profile_name


STATE_PATH = DATA_DIR / "state.json"


def backup_retention() -> int:
    raw = os.getenv("BACKUP_RETENTION", "50")
    try:
        return max(1, int(raw))
    except ValueError:
        return 50


def default_file_content(file: ToolFile) -> str:
    return "{}\n" if file.format == "json" else ""


def default_content(tool: ToolConfig) -> str:
    return default_file_content(tool.primary_file)


def is_multi_file(tool: ToolConfig) -> bool:
    return len(tool.files) > 1


def ensure_dirs(tool: ToolConfig) -> None:
    for file in tool.files:
        file.active_path.parent.mkdir(parents=True, exist_ok=True)
    tool.profile_dir.mkdir(parents=True, exist_ok=True)
    tool.backup_dir.mkdir(parents=True, exist_ok=True)
    tool.lock_path.parent.mkdir(parents=True, exist_ok=True)


def ensure_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for tool in TOOLS.values():
        ensure_dirs(tool)
        for file in tool.files:
            if not file.active_path.exists():
                atomic_write(file.active_path, default_file_content(file))
        migrate_legacy_profiles(tool)
        if not profile_exists(tool, "default"):
            write_profile_files(tool, "default", read_active_contents(tool))
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


def tree_mtime(path: Path) -> float | None:
    if not path.exists():
        return None
    if path.is_file():
        return file_mtime(path)
    mtimes = [item.stat().st_mtime for item in path.iterdir() if item.is_file()]
    return max(mtimes, default=path.stat().st_mtime)


def tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.iterdir() if item.is_file())


def read_text_or_default(path: Path, default: str) -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def lock_for(tool: ToolConfig) -> FileLock:
    return FileLock(str(tool.lock_path), timeout=5)


def file_response(file: ToolFile, content: str, mtime: float | None) -> dict:
    return {
        "id": file.id,
        "label": file.label,
        "filename": file.filename,
        "content": content,
        "format": file.format,
        "mtime": mtime,
        "pathLabel": file.path_label,
    }


def read_active_contents(tool: ToolConfig) -> dict[str, str]:
    return {
        file.id: read_text_or_default(file.active_path, default_file_content(file))
        for file in tool.files
    }


def read_active(tool: ToolConfig) -> dict:
    ensure_dirs(tool)
    contents = read_active_contents(tool)
    files = [
        file_response(file, contents[file.id], file_mtime(file.active_path))
        for file in tool.files
    ]
    primary = files[0]
    return {
        "tool": tool.id,
        "content": primary["content"],
        "format": primary["format"],
        "mtime": primary["mtime"],
        "pathLabel": tool.path_label,
        "files": files,
    }


def save_active(
    tool: ToolConfig,
    content: str | None,
    last_known_mtime: float | None,
    files: list[dict[str, Any]] | None = None,
) -> dict:
    incoming = normalize_incoming_contents(tool, content, files)
    known_mtimes = normalize_known_mtimes(tool, last_known_mtime, files)
    validate_contents(tool, incoming)
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            for file_id in incoming:
                file = tool.file_by_id(file_id)
                current_mtime = file_mtime(file.active_path)
                known_mtime = known_mtimes.get(file_id)
                if (
                    known_mtime is not None
                    and current_mtime is not None
                    and abs(current_mtime - known_mtime) > 0.0001
                ):
                    raise APIError(
                        "CONFLICT_MODIFIED_EXTERNALLY",
                        "File was modified outside the web UI. Reload before saving.",
                        409,
                    )
            backup_active(tool, "save")
            for file_id, file_content in incoming.items():
                atomic_write(tool.file_by_id(file_id).active_path, file_content)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_active(tool)


def normalize_incoming_contents(
    tool: ToolConfig,
    content: str | None,
    files: list[dict[str, Any]] | None,
) -> dict[str, str]:
    if files is None:
        if content is None:
            raise APIError("NO_CONTENT", "No config content supplied.", 400)
        return {tool.primary_file.id: content}

    incoming: dict[str, str] = {}
    for item in files:
        file_id = str(item.get("id", ""))
        if file_id in incoming:
            raise APIError("DUPLICATE_FILE", "Duplicate config file in request.", 400)
        try:
            tool.file_by_id(file_id)
        except KeyError as exc:
            raise APIError("UNKNOWN_FILE", "Unknown config file in request.", 400) from exc
        incoming[file_id] = str(item.get("content", ""))
    if not incoming:
        raise APIError("NO_CONTENT", "No config content supplied.", 400)
    return incoming


def normalize_known_mtimes(
    tool: ToolConfig,
    last_known_mtime: float | None,
    files: list[dict[str, Any]] | None,
) -> dict[str, float | None]:
    if files is None:
        return {tool.primary_file.id: last_known_mtime}
    return {str(item.get("id", "")): item.get("lastKnownMtime") for item in files}


def validate_contents(tool: ToolConfig, contents: dict[str, str]) -> None:
    for file_id, content in contents.items():
        validate_content(tool.file_by_id(file_id).format, content)


def backup_active(tool: ToolConfig, reason: str = "manual") -> Path | None:
    ensure_dirs(tool)
    existing_files = [file for file in tool.files if file.active_path.exists()]
    if not existing_files:
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    if not is_multi_file(tool):
        src = tool.primary_file.active_path
        dst = tool.backup_dir / f"{src.name}.{ts}.{reason}.bak"
        atomic_write(dst, src.read_text(encoding="utf-8"))
    else:
        dst = tool.backup_dir / f"{tool.id}.{ts}.{reason}.bak"
        dst.mkdir(parents=True, exist_ok=False)
        for file in existing_files:
            atomic_write(dst / file.filename, file.active_path.read_text(encoding="utf-8"))
        fsync_dir(dst.parent)
    prune_backups(tool)
    return dst


def prune_backups(tool: ToolConfig) -> None:
    backups = sorted(
        [path for path in tool.backup_dir.iterdir() if path.is_file() or path.is_dir()],
        key=tree_mtime,
        reverse=True,
    )
    for old_path in backups[backup_retention() :]:
        if old_path.is_dir():
            shutil.rmtree(old_path)
        else:
            old_path.unlink(missing_ok=True)


def profile_path(tool: ToolConfig, name: str) -> Path:
    validate_profile_name(name)
    if is_multi_file(tool):
        return tool.profile_dir / name
    return tool.profile_dir / f"{name}{tool.ext}"


def legacy_profile_path(tool: ToolConfig, name: str) -> Path:
    validate_profile_name(name)
    return tool.profile_dir / f"{name}{tool.ext}"


def profile_exists(tool: ToolConfig, name: str) -> bool:
    path = profile_path(tool, name)
    if path.exists():
        return True
    return is_multi_file(tool) and legacy_profile_path(tool, name).exists()


def profile_file_path(tool: ToolConfig, name: str, file: ToolFile) -> Path:
    if is_multi_file(tool):
        return profile_path(tool, name) / file.filename
    return profile_path(tool, name)


def migrate_legacy_profiles(tool: ToolConfig) -> None:
    if not is_multi_file(tool):
        return
    ensure_dirs(tool)
    for legacy_path in sorted(tool.profile_dir.glob(f"*{tool.ext}")):
        if not legacy_path.is_file():
            continue
        name = legacy_path.name[: -len(tool.ext)]
        try:
            validate_profile_name(name)
        except APIError:
            continue
        next_path = profile_path(tool, name)
        if next_path.exists():
            continue
        contents = read_active_contents(tool)
        contents[tool.primary_file.id] = legacy_path.read_text(encoding="utf-8")
        validate_contents(tool, contents)
        write_profile_files(tool, name, contents)


def write_profile_files(tool: ToolConfig, name: str, contents: dict[str, str]) -> None:
    path = profile_path(tool, name)
    if is_multi_file(tool):
        path.mkdir(parents=True, exist_ok=True)
        for file in tool.files:
            atomic_write(path / file.filename, contents.get(file.id, default_file_content(file)))
    else:
        atomic_write(path, contents.get(tool.primary_file.id, default_content(tool)))


def list_profiles(tool: ToolConfig) -> list[dict]:
    ensure_dirs(tool)
    migrate_legacy_profiles(tool)
    state = read_state().get(tool.id, {})
    items: dict[str, dict] = {}
    if is_multi_file(tool):
        for path in sorted(tool.profile_dir.iterdir()):
            if not path.is_dir():
                continue
            name = path.name
            items[name] = {
                "name": name,
                "mtime": tree_mtime(path),
                "active": state.get("activeProfile") == name,
            }
    for path in sorted(tool.profile_dir.glob(f"*{tool.ext}")):
        name = path.name[: -len(tool.ext)]
        if not path.is_file() or name in items:
            continue
        items[name] = {
            "name": name,
            "mtime": file_mtime(path),
            "active": state.get("activeProfile") == name,
        }
    return sorted(items.values(), key=lambda item: item["name"])


def read_profile_contents(tool: ToolConfig, name: str) -> tuple[dict[str, str], float | None]:
    path = profile_path(tool, name)
    if is_multi_file(tool) and path.is_dir():
        contents = {
            file.id: read_text_or_default(path / file.filename, default_file_content(file))
            for file in tool.files
        }
        return contents, tree_mtime(path)

    legacy_path = legacy_profile_path(tool, name)
    if legacy_path.exists() and legacy_path.is_file():
        contents = {tool.primary_file.id: legacy_path.read_text(encoding="utf-8")}
        if is_multi_file(tool):
            active_contents = read_active_contents(tool)
            for file in tool.files[1:]:
                contents[file.id] = active_contents[file.id]
        return contents, file_mtime(legacy_path)

    raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)


def read_profile(tool: ToolConfig, name: str) -> dict:
    contents, mtime = read_profile_contents(tool, name)
    files = [
        file_response(file, contents[file.id], file_mtime(profile_file_path(tool, name, file)))
        for file in tool.files
    ]
    primary = files[0]
    return {
        "tool": tool.id,
        "name": name,
        "content": primary["content"],
        "format": primary["format"],
        "mtime": mtime,
        "files": files,
    }


def create_profile(
    tool: ToolConfig,
    name: str,
    source: str,
    content: str | None = None,
    files: list[dict[str, Any]] | None = None,
) -> dict:
    if source not in {"active", "empty", "content"}:
        raise APIError("INVALID_PROFILE_SOURCE", "Profile source must be active, empty, or content.", 400)
    ensure_dirs(tool)
    migrate_legacy_profiles(tool)
    try:
        with lock_for(tool):
            if profile_exists(tool, name):
                raise APIError("PROFILE_EXISTS", "Profile already exists.", 409)
            if source == "active":
                profile_contents = read_active_contents(tool)
            elif source == "content":
                profile_contents = {
                    file.id: default_file_content(file)
                    for file in tool.files
                }
                profile_contents.update(normalize_incoming_contents(tool, content, files))
            else:
                profile_contents = {file.id: default_file_content(file) for file in tool.files}
            validate_contents(tool, profile_contents)
            write_profile_files(tool, name, profile_contents)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, name)


def save_profile(
    tool: ToolConfig,
    name: str,
    content: str | None,
    files: list[dict[str, Any]] | None = None,
) -> dict:
    ensure_dirs(tool)
    migrate_legacy_profiles(tool)
    try:
        with lock_for(tool):
            if not profile_exists(tool, name):
                raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)
            existing, _ = read_profile_contents(tool, name)
            existing.update(normalize_incoming_contents(tool, content, files))
            validate_contents(tool, existing)
            write_profile_files(tool, name, existing)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, name)


def delete_profile(tool: ToolConfig, name: str) -> None:
    ensure_dirs(tool)
    migrate_legacy_profiles(tool)
    state = read_state().get(tool.id, {})
    if state.get("activeProfile") == name:
        raise APIError("PROFILE_ACTIVE", "Cannot delete the currently active profile.", 409)
    try:
        with lock_for(tool):
            path = profile_path(tool, name)
            legacy_path = legacy_profile_path(tool, name)
            if path.exists() and path.is_dir():
                shutil.rmtree(path)
            elif path.exists() and path.is_file():
                path.unlink()
            elif legacy_path.exists() and legacy_path.is_file():
                legacy_path.unlink()
            else:
                raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc


def activate_profile(tool: ToolConfig, name: str) -> dict:
    contents, _ = read_profile_contents(tool, name)
    validate_contents(tool, contents)
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            backup_active(tool, "activate")
            for file in tool.files:
                atomic_write(file.active_path, contents[file.id])
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
    for path in sorted(tool.backup_dir.iterdir(), key=tree_mtime, reverse=True):
        if path.is_file() or path.is_dir():
            backups.append({"name": path.name, "mtime": tree_mtime(path), "size": tree_size(path)})
    return backups


def backup_path(tool: ToolConfig, name: str) -> Path:
    validate_backup_name(name)
    path = tool.backup_dir / name
    try:
        path.resolve().relative_to(tool.backup_dir.resolve())
    except ValueError as exc:
        raise APIError("INVALID_BACKUP_NAME", "Invalid backup name.", 400) from exc
    return path


def read_backup_contents(tool: ToolConfig, name: str) -> tuple[dict[str, str], float | None, Path]:
    path = backup_path(tool, name)
    if not path.exists() or not (path.is_file() or path.is_dir()):
        raise APIError("BACKUP_NOT_FOUND", "Backup not found.", 404)
    if path.is_dir():
        contents = {
            file.id: read_text_or_default(path / file.filename, default_file_content(file))
            for file in tool.files
        }
        return contents, tree_mtime(path), path
    return {tool.primary_file.id: path.read_text(encoding="utf-8")}, file_mtime(path), path


def read_backup(tool: ToolConfig, name: str) -> dict:
    contents, mtime, path = read_backup_contents(tool, name)
    files = [
        file_response(file, contents[file.id], file_mtime(path / file.filename) if path.is_dir() else file_mtime(path))
        for file in tool.files
        if file.id in contents
    ]
    primary = files[0]
    return {
        "tool": tool.id,
        "name": name,
        "content": primary["content"],
        "format": primary["format"],
        "mtime": mtime,
        "files": files,
    }


def restore_backup(tool: ToolConfig, name: str) -> dict:
    contents, _, _ = read_backup_contents(tool, name)
    validate_contents(tool, contents)
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            backup_active(tool, "restore")
            for file_id, content in contents.items():
                atomic_write(tool.file_by_id(file_id).active_path, content)
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
