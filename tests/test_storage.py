from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


def load_modules(tmp_path: Path):
    data_dir = tmp_path / "data"
    claude_path = tmp_path / "config" / "claude" / "settings.json"
    codex_path = tmp_path / "config" / "codex" / "auth.json"
    claude_path.parent.mkdir(parents=True)
    codex_path.parent.mkdir(parents=True)
    claude_path.write_text('{"model": "sonnet"}\n', encoding="utf-8")
    codex_path.write_text('{"OPENAI_API_KEY": "test"}\n', encoding="utf-8")

    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["CLAUDE_CONFIG_PATH"] = str(claude_path)
    os.environ["CODEX_CONFIG_PATH"] = str(codex_path)
    os.environ["BACKUP_RETENTION"] = "50"

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name)

    registry = importlib.import_module("app.registry")
    storage = importlib.import_module("app.storage")
    errors = importlib.import_module("app.errors")
    storage.ensure_all()
    return registry, storage, errors, claude_path, codex_path, data_dir


def test_invalid_tool_rejected(tmp_path: Path):
    registry, _, errors, *_ = load_modules(tmp_path)
    with pytest.raises(errors.InvalidToolError):
        registry.get_tool("evil")


def test_invalid_profile_name_rejected(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    with pytest.raises(errors.APIError) as exc:
        storage.create_profile(registry.get_tool("claude"), "../evil", "active")
    assert exc.value.code == "INVALID_PROFILE_NAME"


def test_invalid_json_rejected(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    mtime = storage.file_mtime(tool.active_path)
    with pytest.raises(errors.APIError) as exc:
        storage.save_active(tool, "{bad", mtime)
    assert exc.value.code == "INVALID_JSON"


def test_invalid_codex_json_rejected(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    tool = registry.get_tool("codex")
    mtime = storage.file_mtime(tool.active_path)
    with pytest.raises(errors.APIError) as exc:
        storage.save_active(tool, "{bad", mtime)
    assert exc.value.code == "INVALID_JSON"


def test_save_active_creates_backup(tmp_path: Path):
    registry, storage, _, claude_path, _, data_dir = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    storage.save_active(tool, '{"model": "opus"}\n', storage.file_mtime(tool.active_path))

    assert claude_path.read_text(encoding="utf-8") == '{"model": "opus"}\n'
    backups = list((data_dir / "backups" / "claude").glob("*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == '{"model": "sonnet"}\n'


def test_activate_profile_overwrites_active(tmp_path: Path):
    registry, storage, _, claude_path, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    storage.create_profile(tool, "proxy", "empty")
    storage.save_profile(tool, "proxy", '{"env": {"HTTPS_PROXY": "http://127.0.0.1:7890"}}\n')
    storage.activate_profile(tool, "proxy")

    assert "HTTPS_PROXY" in claude_path.read_text(encoding="utf-8")


def test_external_mtime_conflict(tmp_path: Path):
    registry, storage, errors, claude_path, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    old_mtime = storage.file_mtime(tool.active_path)
    claude_path.write_text('{"external": true}\n', encoding="utf-8")

    with pytest.raises(errors.APIError) as exc:
        storage.save_active(tool, '{"model": "opus"}\n', old_mtime)
    assert exc.value.code == "CONFLICT_MODIFIED_EXTERNALLY"


def test_password_hash_verification(tmp_path: Path):
    load_modules(tmp_path)
    auth = importlib.import_module("app.auth")
    password_hash = auth.generate_password_hash("secret")
    os.environ["APP_PASSWORD"] = ""
    os.environ["APP_PASSWORD_HASH"] = password_hash

    assert auth.verify_password("secret")
    assert not auth.verify_password("wrong")
