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
from .validators import validate_content, validate_history_entry_name, validate_profile_name


STATE_PATH = DATA_DIR / "state.json"
CODEX_GATEWAY_DIR = Path(os.getenv("CODEX_GATEWAY_DIR", str(DATA_DIR / "codex-gateway")))
CODEX_GATEWAY_SNAPSHOT_PATH = CODEX_GATEWAY_DIR / "codex-snapshot.json"


def history_retention() -> int:
    raw = os.getenv("HISTORY_RETENTION", "50")
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
    tool.history_dir.mkdir(parents=True, exist_ok=True)
    tool.lock_path.parent.mkdir(parents=True, exist_ok=True)


def ensure_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state = read_state()
    state_changed = False
    for tool in TOOLS.values():
        ensure_dirs(tool)
        for file in tool.files:
            if not file.active_path.exists():
                atomic_write(file.active_path, default_file_content(file))
        migrate_legacy_profiles(tool)
        if not profile_exists(tool, "default"):
            write_profile_files(tool, "default", read_runtime_contents(tool))
        active_name = state.get(tool.id, {}).get("activeProfile")
        if not active_name or not profile_exists(tool, active_name):
            state[tool.id] = {
                "activeProfile": "default",
                "lastActivatedAt": datetime.now(timezone.utc).isoformat(),
            }
            state_changed = True
    if not STATE_PATH.exists() or state_changed:
        write_state(state)


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


def read_runtime_contents(tool: ToolConfig) -> dict[str, str]:
    return {
        file.id: read_text_or_default(file.active_path, default_file_content(file))
        for file in tool.files
    }


def runtime_changed_for_profile(tool: ToolConfig, contents: dict[str, str]) -> bool:
    if tool.id == "codex" and CODEX_GATEWAY_SNAPSHOT_PATH.exists():
        snapshot_contents = codex_gateway_snapshot_contents(tool)
        if snapshot_contents is None:
            return False
        return contents != snapshot_contents
    return contents != read_runtime_contents(tool)


def codex_gateway_snapshot_contents(tool: ToolConfig) -> dict[str, str] | None:
    if not CODEX_GATEWAY_SNAPSHOT_PATH.exists():
        return None
    try:
        snapshot = json.loads(CODEX_GATEWAY_SNAPSHOT_PATH.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return None
    raw_contents = snapshot.get("runtimeContents")
    if not isinstance(raw_contents, dict):
        return None
    contents: dict[str, str] = {}
    for file in tool.files:
        value = raw_contents.get(file.id)
        if not isinstance(value, str):
            return None
        contents[file.id] = value
    return contents


def sync_profile_to_runtime(tool: ToolConfig, contents: dict[str, str]) -> None:
    for file in tool.files:
        atomic_write(file.active_path, contents[file.id])


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


def normalize_known_mtimes(files: list[dict[str, Any]] | None) -> dict[str, float | None]:
    if files is None:
        return {}
    return {str(item.get("id", "")): item.get("lastKnownMtime") for item in files}


def validate_contents(tool: ToolConfig, contents: dict[str, str]) -> None:
    for file_id, content in contents.items():
        validate_content(tool.file_by_id(file_id).format, content)


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
        contents = read_runtime_contents(tool)
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


def active_profile_name(tool: ToolConfig) -> str:
    state = read_state().get(tool.id, {})
    name = state.get("activeProfile")
    if isinstance(name, str) and profile_exists(tool, name):
        return name
    return "default"


def list_profiles(tool: ToolConfig) -> list[dict]:
    ensure_dirs(tool)
    migrate_legacy_profiles(tool)
    active_name = active_profile_name(tool)
    items: dict[str, dict] = {}
    if is_multi_file(tool):
        for path in sorted(tool.profile_dir.iterdir()):
            if not path.is_dir():
                continue
            name = path.name
            items[name] = {
                "name": name,
                "mtime": tree_mtime(path),
                "active": active_name == name,
            }
    for path in sorted(tool.profile_dir.glob(f"*{tool.ext}")):
        name = path.name[: -len(tool.ext)]
        if not path.is_file() or name in items:
            continue
        items[name] = {
            "name": name,
            "mtime": file_mtime(path),
            "active": active_name == name,
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
            runtime_contents = read_runtime_contents(tool)
            for file in tool.files[1:]:
                contents[file.id] = runtime_contents[file.id]
        return contents, file_mtime(legacy_path)

    raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)


def read_profile(tool: ToolConfig, name: str) -> dict:
    contents, mtime = read_profile_contents(tool, name)
    files = [
        file_response(file, contents[file.id], file_mtime(profile_file_path(tool, name, file)))
        for file in tool.files
    ]
    primary = files[0]
    active = active_profile_name(tool) == name
    return {
        "tool": tool.id,
        "name": name,
        "content": primary["content"],
        "format": primary["format"],
        "mtime": mtime,
        "files": files,
        "active": active,
        "runtimeChanged": active and runtime_changed_for_profile(tool, contents),
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
                profile_contents, _ = read_profile_contents(tool, active_profile_name(tool))
            elif source == "content":
                profile_contents = {file.id: default_file_content(file) for file in tool.files}
                profile_contents.update(normalize_incoming_contents(tool, content, files))
            else:
                profile_contents = {file.id: default_file_content(file) for file in tool.files}
            validate_contents(tool, profile_contents)
            write_profile_files(tool, name, profile_contents)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, name)


def ensure_profile_not_modified(tool: ToolConfig, name: str, files: list[dict[str, Any]] | None) -> None:
    known_mtimes = normalize_known_mtimes(files)
    for file_id, known_mtime in known_mtimes.items():
        if known_mtime is None:
            continue
        try:
            file = tool.file_by_id(file_id)
        except KeyError:
            continue
        current_mtime = file_mtime(profile_file_path(tool, name, file))
        if current_mtime is not None and abs(current_mtime - known_mtime) > 0.0001:
            raise APIError(
                "CONFLICT_MODIFIED_EXTERNALLY",
                "Profile was modified outside the web UI. Reload before saving.",
                409,
            )


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
            ensure_profile_not_modified(tool, name, files)
            existing, _ = read_profile_contents(tool, name)
            next_contents = dict(existing)
            next_contents.update(normalize_incoming_contents(tool, content, files))
            validate_contents(tool, next_contents)
            create_history_entry(tool, name, "save", existing)
            write_profile_files(tool, name, next_contents)
            if active_profile_name(tool) == name:
                sync_profile_to_runtime(tool, next_contents)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, name)


def delete_profile(tool: ToolConfig, name: str) -> None:
    ensure_dirs(tool)
    migrate_legacy_profiles(tool)
    if active_profile_name(tool) == name:
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
            profile_history = history_profile_path(tool, name)
            if profile_history.exists():
                shutil.rmtree(profile_history)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc


def activate_profile(tool: ToolConfig, name: str) -> dict:
    contents, _ = read_profile_contents(tool, name)
    validate_contents(tool, contents)
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            sync_profile_to_runtime(tool, contents)
            state = read_state()
            state[tool.id] = {
                "activeProfile": name,
                "lastActivatedAt": datetime.now(timezone.utc).isoformat(),
            }
            write_state(state)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, name)


def import_runtime_to_profile(tool: ToolConfig, name: str) -> dict:
    ensure_dirs(tool)
    migrate_legacy_profiles(tool)
    try:
        with lock_for(tool):
            if not profile_exists(tool, name):
                raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)
            if active_profile_name(tool) != name:
                raise APIError("PROFILE_NOT_ACTIVE", "Only the active profile can import current config.", 409)
            runtime_contents = read_runtime_contents(tool)
            validate_contents(tool, runtime_contents)
            existing, _ = read_profile_contents(tool, name)
            create_history_entry(tool, name, "import-runtime", existing)
            write_profile_files(tool, name, runtime_contents)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, name)


def history_profile_path(tool: ToolConfig, profile_name: str) -> Path:
    validate_profile_name(profile_name)
    return tool.history_dir / profile_name


def history_entry_path(tool: ToolConfig, profile_name: str, entry_name: str) -> Path:
    validate_history_entry_name(entry_name)
    path = history_profile_path(tool, profile_name) / entry_name
    try:
        path.resolve().relative_to(tool.history_dir.resolve())
    except ValueError as exc:
        raise APIError("INVALID_HISTORY_ENTRY", "Invalid history entry name.", 400) from exc
    return path


def create_history_entry(
    tool: ToolConfig,
    profile_name: str,
    reason: str,
    contents: dict[str, str] | None = None,
) -> Path:
    contents = contents or read_profile_contents(tool, profile_name)[0]
    validate_contents(tool, contents)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    entry_name = f"{ts}.{reason}"
    path = history_entry_path(tool, profile_name, entry_name)
    path.mkdir(parents=True, exist_ok=False)
    for file in tool.files:
        atomic_write(path / file.filename, contents[file.id])
    atomic_write(
        path / "meta.json",
        json.dumps(
            {
                "profileName": profile_name,
                "reason": reason,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    fsync_dir(path.parent)
    prune_history(tool, profile_name)
    return path


def prune_history(tool: ToolConfig, profile_name: str) -> None:
    root = history_profile_path(tool, profile_name)
    if not root.exists():
        return
    entries = sorted([path for path in root.iterdir() if path.is_dir()], key=tree_mtime, reverse=True)
    for old_path in entries[history_retention() :]:
        shutil.rmtree(old_path)


def list_history(tool: ToolConfig) -> list[dict]:
    ensure_dirs(tool)
    entries: list[dict] = []
    for profile_root in sorted(tool.history_dir.iterdir()):
        if not profile_root.is_dir():
            continue
        profile_name = profile_root.name
        try:
            validate_profile_name(profile_name)
        except APIError:
            continue
        for path in sorted(profile_root.iterdir(), key=tree_mtime, reverse=True):
            if not path.is_dir():
                continue
            entries.append(
                {
                    "profileName": profile_name,
                    "name": path.name,
                    "mtime": tree_mtime(path),
                    "size": tree_size(path),
                    "reason": read_history_reason(path),
                }
            )
    return sorted(entries, key=lambda item: item["mtime"] or 0, reverse=True)


def read_history_reason(path: Path) -> str:
    meta_path = path / "meta.json"
    if not meta_path.exists():
        return "save"
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return "save"
    return str(data.get("reason") or "save")


def clear_history(tool: ToolConfig) -> int:
    ensure_dirs(tool)
    removed = 0
    for path in list(tool.history_dir.iterdir()):
        if path.is_dir():
            shutil.rmtree(path)
            removed += 1
        elif path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def read_history_contents(
    tool: ToolConfig,
    profile_name: str,
    entry_name: str,
) -> tuple[dict[str, str], float | None, Path]:
    path = history_entry_path(tool, profile_name, entry_name)
    if not path.exists() or not path.is_dir():
        raise APIError("HISTORY_NOT_FOUND", "History entry not found.", 404)
    contents = {
        file.id: read_text_or_default(path / file.filename, default_file_content(file))
        for file in tool.files
    }
    return contents, tree_mtime(path), path


def delete_history(tool: ToolConfig, profile_name: str, entry_name: str) -> None:
    path = history_entry_path(tool, profile_name, entry_name)
    if not path.exists() or not path.is_dir():
        raise APIError("HISTORY_NOT_FOUND", "History entry not found.", 404)
    shutil.rmtree(path)


def read_history(tool: ToolConfig, profile_name: str, entry_name: str) -> dict:
    contents, mtime, path = read_history_contents(tool, profile_name, entry_name)
    files = [
        file_response(file, contents[file.id], file_mtime(path / file.filename))
        for file in tool.files
    ]
    primary = files[0]
    return {
        "tool": tool.id,
        "profileName": profile_name,
        "name": entry_name,
        "content": primary["content"],
        "format": primary["format"],
        "mtime": mtime,
        "files": files,
    }


def restore_history(tool: ToolConfig, profile_name: str, entry_name: str) -> dict:
    contents, _, _ = read_history_contents(tool, profile_name, entry_name)
    validate_contents(tool, contents)
    ensure_dirs(tool)
    try:
        with lock_for(tool):
            if not profile_exists(tool, profile_name):
                raise APIError("PROFILE_NOT_FOUND", "Profile not found.", 404)
            current_contents, _ = read_profile_contents(tool, profile_name)
            create_history_entry(tool, profile_name, "restore", current_contents)
            write_profile_files(tool, profile_name, contents)
            if active_profile_name(tool) == profile_name:
                sync_profile_to_runtime(tool, contents)
    except Timeout as exc:
        raise APIError("LOCK_TIMEOUT", "Timed out waiting for the file lock.", 423) from exc
    return read_profile(tool, profile_name)


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def write_state(state: dict) -> None:
    atomic_write(STATE_PATH, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
