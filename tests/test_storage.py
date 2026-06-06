from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest


def load_modules(tmp_path: Path):
    data_dir = tmp_path / "data"
    claude_path = tmp_path / "config" / "claude" / "settings.json"
    codex_path = tmp_path / "config" / "codex" / "auth.json"
    codex_toml_path = tmp_path / "config" / "codex" / "config.toml"
    opencode_path = tmp_path / "config" / "opencode" / "config.json"
    claude_path.parent.mkdir(parents=True)
    codex_path.parent.mkdir(parents=True)
    opencode_path.parent.mkdir(parents=True)
    claude_path.write_text('{"model": "sonnet"}\n', encoding="utf-8")
    codex_path.write_text('{"OPENAI_API_KEY": "test"}\n', encoding="utf-8")
    codex_toml_path.write_text('model = "gpt-5"\n', encoding="utf-8")
    opencode_path.write_text('{"provider": {}}\n', encoding="utf-8")

    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["CLAUDE_CONFIG_PATH"] = str(claude_path)
    os.environ["CODEX_CONFIG_PATH"] = str(codex_path)
    os.environ["CODEX_CONFIG_TOML_PATH"] = str(codex_toml_path)
    os.environ["CODEX_GATEWAY_DIR"] = str(data_dir / "codex-gateway")
    os.environ["OPENCODE_CONFIG_PATH"] = str(opencode_path)
    os.environ["HISTORY_RETENTION"] = "50"

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name)

    registry = importlib.import_module("app.registry")
    storage = importlib.import_module("app.storage")
    errors = importlib.import_module("app.errors")
    storage.ensure_all()
    return registry, storage, errors, claude_path, codex_path, codex_toml_path, data_dir


def test_invalid_tool_rejected(tmp_path: Path):
    registry, _, errors, *_ = load_modules(tmp_path)
    with pytest.raises(errors.InvalidToolError):
        registry.get_tool("evil")


def test_default_profile_is_created_and_active(tmp_path: Path):
    registry, storage, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")

    profiles = storage.list_profiles(tool)

    assert profiles == [{"name": "default", "mtime": profiles[0]["mtime"], "active": True}]
    assert storage.read_profile(tool, "default")["content"] == '{"model": "sonnet"}\n'


def test_invalid_profile_name_rejected(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    with pytest.raises(errors.APIError) as exc:
        storage.create_profile(registry.get_tool("claude"), "../evil", "active")
    assert exc.value.code == "INVALID_PROFILE_NAME"


def test_profile_name_allows_chinese(tmp_path: Path):
    registry, storage, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")

    created = storage.create_profile(tool, "中文供应商", "active")
    storage.save_profile(tool, "中文供应商", '{"model": "opus"}\n')
    profiles = storage.list_profiles(tool)

    assert created["name"] == "中文供应商"
    assert storage.read_profile(tool, "中文供应商")["content"] == '{"model": "opus"}\n'
    assert "中文供应商" in {profile["name"] for profile in profiles}


def test_invalid_profile_json_rejected(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    with pytest.raises(errors.APIError) as exc:
        storage.save_profile(tool, "default", "{bad")
    assert exc.value.code == "INVALID_JSON"


def test_save_active_profile_creates_history_and_syncs_runtime(tmp_path: Path):
    registry, storage, _, claude_path, *_, data_dir = load_modules(tmp_path)
    tool = registry.get_tool("claude")

    storage.save_profile(tool, "default", '{"model": "opus"}\n')

    assert claude_path.read_text(encoding="utf-8") == '{"model": "opus"}\n'
    history = storage.list_history(tool)
    assert len(history) == 1
    assert history[0]["profileName"] == "default"
    restored_old = storage.read_history(tool, "default", history[0]["name"])
    assert restored_old["content"] == '{"model": "sonnet"}\n'
    assert (data_dir / "history" / "claude" / "default" / history[0]["name"]).is_dir()


def test_activate_profile_overwrites_runtime_without_history(tmp_path: Path):
    registry, storage, _, claude_path, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    storage.create_profile(tool, "proxy", "empty")
    storage.save_profile(tool, "proxy", '{"env": {"HTTPS_PROXY": "http://127.0.0.1:7890"}}\n')

    history_before_activate = len(storage.list_history(tool))
    storage.activate_profile(tool, "proxy")

    assert "HTTPS_PROXY" in claude_path.read_text(encoding="utf-8")
    assert storage.active_profile_name(tool) == "proxy"
    assert len(storage.list_history(tool)) == history_before_activate


def test_delete_active_profile_switches_to_fallback(tmp_path: Path):
    registry, storage, _, claude_path, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    storage.create_profile(tool, "中文供应商", "empty")
    storage.save_profile(tool, "中文供应商", '{"model": "opus"}\n')
    storage.activate_profile(tool, "中文供应商")

    storage.delete_profile(tool, "中文供应商")

    assert storage.active_profile_name(tool) == "default"
    assert claude_path.read_text(encoding="utf-8") == '{"model": "sonnet"}\n'
    assert "中文供应商" not in {profile["name"] for profile in storage.list_profiles(tool)}


def test_active_profile_reports_runtime_change(tmp_path: Path):
    registry, storage, _, claude_path, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    storage.create_profile(tool, "other", "active")

    claude_path.write_text('{"model": "manual"}\n', encoding="utf-8")

    active_doc = storage.read_profile(tool, "default")
    other_doc = storage.read_profile(tool, "other")
    assert active_doc["active"] is True
    assert active_doc["runtimeChanged"] is True
    assert other_doc["active"] is False
    assert other_doc["runtimeChanged"] is False


def test_codex_profile_ignores_gateway_managed_runtime_overlay(tmp_path: Path):
    registry, storage, _, _claude_path, codex_auth, codex_toml, data_dir = load_modules(tmp_path)
    tool = registry.get_tool("codex")
    original = storage.read_profile(tool, "default")
    snapshot_path = data_dir / "codex-gateway" / "codex-snapshot.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "runtimeContents": {
                    "auth": original["files"][0]["content"],
                    "config": original["files"][1]["content"],
                }
            }
        ),
        encoding="utf-8",
    )
    codex_auth.write_text('{"auth_mode": "apikey", "OPENAI_API_KEY": "gateway"}\n', encoding="utf-8")
    codex_toml.write_text(
        'model_provider = "configbox_gateway"\nmodel = "gpt-5.3-codex"\n',
        encoding="utf-8",
    )

    doc = storage.read_profile(tool, "default")

    assert doc["runtimeChanged"] is False


def test_codex_profile_ignores_legacy_gateway_snapshot_without_raw_contents(tmp_path: Path):
    registry, storage, _, _claude_path, codex_auth, codex_toml, data_dir = load_modules(tmp_path)
    tool = registry.get_tool("codex")
    snapshot_path = data_dir / "codex-gateway" / "codex-snapshot.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text('{"applied": {"model": "gpt-5.3-codex"}}\n', encoding="utf-8")
    codex_auth.write_text('{"auth_mode": "apikey", "OPENAI_API_KEY": "gateway"}\n', encoding="utf-8")
    codex_toml.write_text(
        'model_provider = "configbox_gateway"\nmodel = "gpt-5.3-codex"\n',
        encoding="utf-8",
    )

    doc = storage.read_profile(tool, "default")

    assert doc["runtimeChanged"] is False


def test_import_runtime_to_active_profile_creates_history(tmp_path: Path):
    registry, storage, _, claude_path, *_, data_dir = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    claude_path.write_text('{"model": "manual"}\n', encoding="utf-8")

    imported = storage.import_runtime_to_profile(tool, "default")

    assert imported["content"] == '{"model": "manual"}\n'
    assert imported["runtimeChanged"] is False
    history = storage.list_history(tool)
    assert len(history) == 1
    assert history[0]["reason"] == "import-runtime"
    assert storage.read_history(tool, "default", history[0]["name"])["content"] == '{"model": "sonnet"}\n'
    assert (data_dir / "profiles" / "claude" / "default.json").read_text(encoding="utf-8") == '{"model": "manual"}\n'


def test_import_runtime_rejects_inactive_profile(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    storage.create_profile(tool, "other", "active")

    with pytest.raises(errors.APIError) as exc:
        storage.import_runtime_to_profile(tool, "other")
    assert exc.value.code == "PROFILE_NOT_ACTIVE"


def test_profile_mtime_conflict(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    doc = storage.read_profile(tool, "default")
    profile_file = storage.profile_file_path(tool, "default", tool.primary_file)
    old_mtime = doc["files"][0]["mtime"]
    profile_file.write_text('{"external": true}\n', encoding="utf-8")

    with pytest.raises(errors.APIError) as exc:
        storage.save_profile(
            tool,
            "default",
            None,
            [{"id": "settings", "content": '{"model": "opus"}\n', "lastKnownMtime": old_mtime}],
        )
    assert exc.value.code == "CONFLICT_MODIFIED_EXTERNALLY"


def test_codex_profile_pairs_auth_json_and_config_toml(tmp_path: Path):
    registry, storage, _, _, codex_path, codex_toml_path, data_dir = load_modules(tmp_path)
    tool = registry.get_tool("codex")

    storage.create_profile(tool, "deepseek", "active")
    storage.save_profile(
        tool,
        "deepseek",
        None,
        [
            {"id": "auth", "content": '{"OPENAI_API_KEY": "deepseek"}\n'},
            {"id": "config", "content": 'model = "deepseek-chat"\n'},
        ],
    )
    storage.activate_profile(tool, "deepseek")

    assert codex_path.read_text(encoding="utf-8") == '{"OPENAI_API_KEY": "deepseek"}\n'
    assert codex_toml_path.read_text(encoding="utf-8") == 'model = "deepseek-chat"\n'
    assert (data_dir / "profiles" / "codex" / "deepseek" / "auth.json").exists()
    assert (data_dir / "profiles" / "codex" / "deepseek" / "config.toml").exists()
    assert any(path.is_dir() for path in (data_dir / "history" / "codex" / "deepseek").iterdir())


def test_invalid_codex_toml_rejected(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    tool = registry.get_tool("codex")
    with pytest.raises(errors.APIError) as exc:
        storage.save_profile(tool, "default", None, [{"id": "config", "content": "bad = ["}])
    assert exc.value.code == "INVALID_TOML"


def test_profile_can_have_multiple_history_entries_and_restore_keeps_current_version(tmp_path: Path):
    registry, storage, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    storage.save_profile(tool, "default", '{"model": "opus"}\n')
    storage.save_profile(tool, "default", '{"model": "haiku"}\n')
    history = storage.list_history(tool)

    assert len(history) == 2

    oldest = history[-1]
    restored = storage.restore_history(tool, "default", oldest["name"])
    next_history = storage.list_history(tool)

    assert restored["content"] == '{"model": "sonnet"}\n'
    assert len(next_history) == 3
    assert storage.read_history(tool, "default", next_history[0]["name"])["content"] == '{"model": "haiku"}\n'


def test_delete_history_removes_single_entry(tmp_path: Path):
    registry, storage, errors, *_ = load_modules(tmp_path)
    tool = registry.get_tool("claude")
    storage.save_profile(tool, "default", '{"model": "opus"}\n')
    entry = storage.list_history(tool)[0]

    storage.delete_history(tool, "default", entry["name"])

    assert storage.list_history(tool) == []
    with pytest.raises(errors.APIError) as exc:
        storage.read_history(tool, "default", entry["name"])
    assert exc.value.code == "HISTORY_NOT_FOUND"


def test_clear_history_removes_all_profile_histories(tmp_path: Path):
    registry, storage, *_ = load_modules(tmp_path)
    claude = registry.get_tool("claude")
    codex = registry.get_tool("codex")
    storage.save_profile(claude, "default", '{"model": "opus"}\n')
    storage.save_profile(
        codex,
        "default",
        None,
        [
            {"id": "auth", "content": '{"OPENAI_API_KEY": "next"}\n'},
            {"id": "config", "content": 'model = "next"\n'},
        ],
    )

    assert storage.clear_history(claude) == 1
    assert storage.clear_history(codex) == 1
    assert storage.list_history(claude) == []
    assert storage.list_history(codex) == []


def test_opencode_profile_is_json_tool(tmp_path: Path):
    registry, storage, _errors, *_ = load_modules(tmp_path)
    opencode_path = tmp_path / "config" / "opencode" / "config.json"
    tool = registry.get_tool("opencode")

    storage.save_profile(
        tool,
        "default",
        '{"$schema": "https://opencode.ai/config.json", "provider": {"zhipu": {"models": {}}}}\n',
    )

    assert tool.name == "OpenCode"
    assert tool.path_label == "~/.config/opencode/config.json"
    assert '"zhipu"' in opencode_path.read_text(encoding="utf-8")

def test_password_hash_verification(tmp_path: Path):
    load_modules(tmp_path)
    auth = importlib.import_module("app.auth")
    password_hash = auth.generate_password_hash("secret")
    os.environ["APP_PASSWORD"] = ""
    os.environ["APP_PASSWORD_HASH"] = password_hash

    assert auth.verify_password("secret")
    assert not auth.verify_password("wrong")


def test_password_hash_verification_accepts_compose_escaped_dollars(tmp_path: Path):
    load_modules(tmp_path)
    auth = importlib.import_module("app.auth")
    password_hash = auth.generate_password_hash("secret")
    os.environ["APP_PASSWORD"] = ""
    os.environ["APP_PASSWORD_HASH"] = auth.compose_env_escape(password_hash)

    assert "$$" in os.environ["APP_PASSWORD_HASH"]
    assert auth.verify_password("secret")
    assert not auth.verify_password("wrong")


def test_password_hash_tool_updates_env_text(tmp_path: Path):
    load_modules(tmp_path)
    password_hash = importlib.import_module("app.password_hash")

    updated = password_hash.update_env_text(
        "# keep me\n"
        "UID=1000\n"
        "APP_PASSWORD=old\n"
        "APP_PASSWORD_HASH=old-hash\n"
        "SESSION_SECRET=old-secret\n"
        "TZ=Asia/Shanghai\n",
        {
            "APP_PASSWORD": "",
            "APP_PASSWORD_HASH": "pbkdf2_sha256$$260000$$salt$$digest",
            "SESSION_SECRET": "new-secret",
        },
    )

    assert "# keep me\n" in updated
    assert "UID=1000\n" in updated
    assert "APP_PASSWORD=\n" in updated
    assert "APP_PASSWORD_HASH=pbkdf2_sha256$$260000$$salt$$digest\n" in updated
    assert "SESSION_SECRET=new-secret\n" in updated
    assert "TZ=Asia/Shanghai\n" in updated
    assert "old-hash" not in updated


def test_password_hash_tool_prints_manual_values_on_write_failure(tmp_path: Path, capsys, monkeypatch):
    load_modules(tmp_path)
    password_hash = importlib.import_module("app.password_hash")

    monkeypatch.setattr("sys.argv", ["password_hash", "--env-file", str(tmp_path)])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "secret")

    with pytest.raises(SystemExit) as exc:
        password_hash.main()

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "Failed to update" in captured.err
    assert "Please manually write these lines to your .env file:" in captured.err
    assert "APP_PASSWORD=\n" in captured.out
    assert "APP_PASSWORD_HASH=pbkdf2_sha256$$" in captured.out
    assert "SESSION_SECRET=" in captured.out
