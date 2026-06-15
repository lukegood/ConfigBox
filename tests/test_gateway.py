from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import tomlkit


def load_gateway(tmp_path: Path):
    data_dir = tmp_path / "data"
    codex_auth = tmp_path / "config" / "codex" / "auth.json"
    codex_toml = tmp_path / "config" / "codex" / "config.toml"
    gateway_dir = data_dir / "codex-gateway"
    codex_auth.parent.mkdir(parents=True)
    codex_auth.write_text('{"tokens": {"keep": true}}\n', encoding="utf-8")
    codex_toml.write_text('model = "gpt-5.5"\n', encoding="utf-8")

    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["CODEX_CONFIG_PATH"] = str(codex_auth)
    os.environ["CODEX_CONFIG_TOML_PATH"] = str(codex_toml)
    os.environ["CODEX_GATEWAY_DIR"] = str(gateway_dir)
    os.environ["CODEX_GATEWAY_CONFIG_PATH"] = str(gateway_dir / "config.json")
    os.environ.pop("CODEX_MODEL_CATALOG_CLIENT_PATH", None)

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name)

    gateway = importlib.import_module("app.gateway")
    gateway.ensure_gateway()
    gateway.write_config(
        {
            "activeProvider": "deepseek",
            "providers": [
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "baseUrl": "https://api.deepseek.com",
                    "authScheme": "bearer",
                    "apiFormat": "openai_chat",
                    "apiKey": "sk-test",
                    "models": {
                        "default": "deepseek-v4-pro",
                        "gpt_5_3_codex": "deepseek-v4-pro",
                    },
                    "modelCapabilities": {
                        "deepseek-v4-pro": {"context_window": 1_000_000}
                    },
                }
            ],
        }
    )
    return gateway, codex_auth, codex_toml, gateway_dir


def test_apply_codex_writes_catalog_and_context_window(tmp_path: Path):
    gateway, _auth_path, codex_toml, gateway_dir = load_gateway(tmp_path)

    gateway.apply_codex()

    doc = tomlkit.parse(codex_toml.read_text(encoding="utf-8"))
    catalog_path = Path(str(doc["model_catalog_json"]))
    assert doc["model_context_window"] == 1_000_000
    assert catalog_path == (gateway_dir / "codex-model-catalog.json").resolve()

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    gpt55 = next(item for item in catalog["models"] if item["slug"] == "gpt-5.5")
    assert gpt55["display_name"] == "DeepSeek / deepseek-v4-pro"
    assert gpt55["context_window"] == 1_000_000
    assert gpt55["auto_compact_token_limit"] == 800_000
    assert gpt55["base_instructions"] == gateway.CAS_BASE_INSTRUCTIONS
    snapshot = json.loads((gateway_dir / "codex-snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["runtimeContents"]["config"] == 'model = "gpt-5.5"\n'


def test_apply_codex_can_write_host_visible_catalog_path(tmp_path: Path):
    host_visible_path = tmp_path / "host" / "codex-model-catalog.json"
    gateway, _auth_path, codex_toml, gateway_dir = load_gateway(tmp_path)
    gateway.MODEL_CATALOG_CLIENT_PATH = str(host_visible_path)

    gateway.apply_codex()

    doc = tomlkit.parse(codex_toml.read_text(encoding="utf-8"))
    assert str(doc["model_catalog_json"]) == str(host_visible_path)
    assert (gateway_dir / "codex-model-catalog.json").exists()


def test_restore_preserves_user_model_changed_during_gateway_session(tmp_path: Path):
    gateway, _auth_path, codex_toml, _gateway_dir = load_gateway(tmp_path)
    gateway.apply_codex()

    doc = tomlkit.parse(codex_toml.read_text(encoding="utf-8"))
    doc["model"] = "gpt-5.4"
    codex_toml.write_text(tomlkit.dumps(doc), encoding="utf-8")

    gateway.restore_codex()

    restored = tomlkit.parse(codex_toml.read_text(encoding="utf-8"))
    assert restored["model"] == "gpt-5.4"
    assert "model_provider" not in restored
    assert "openai_base_url" not in restored
    assert "model_context_window" not in restored
    assert "model_catalog_json" not in restored


def test_restore_reverts_gateway_model_when_user_did_not_change_it(tmp_path: Path):
    gateway, _auth_path, codex_toml, gateway_dir = load_gateway(tmp_path)
    gateway.apply_codex()
    assert (gateway_dir / "codex-model-catalog.json").exists()

    gateway.restore_codex()

    restored = tomlkit.parse(codex_toml.read_text(encoding="utf-8"))
    assert restored["model"] == "gpt-5.5"
    assert "model_provider" not in restored
    assert "openai_base_url" not in restored
    assert "model_context_window" not in restored
    assert "model_catalog_json" not in restored
    assert not (gateway_dir / "codex-model-catalog.json").exists()


def test_gateway_normalization_keeps_new_forwarding_shapes(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    provider = gateway.normalize_provider(
        {
            "name": "Claude",
            "baseUrl": "https://api.anthropic.com/v1",
            "apiFormat": "claude",
            "models": {
                "default": "claude-sonnet-4",
                "gpt_5_5": "claude-opus-4",
                "gpt-4o": "claude-haiku-4",
            },
        }
    )

    assert provider["apiFormat"] == "anthropic_messages"
    assert provider["models"]["gpt-4o"] == "claude-haiku-4"


def test_gateway_normalization_keeps_antigravity_alias(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    provider = gateway.normalize_provider(
        {
            "name": "Antigravity",
            "baseUrl": "https://cloudcode-pa.googleapis.com",
            "apiFormat": "antigravity",
            "models": {"default": "gemini-3-flash"},
        }
    )

    assert provider["apiFormat"] == "antigravity_oauth"


def test_gateway_presets_use_configbox_schema(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    presets = gateway.list_presets()["presets"]
    antigravity = next(item for item in presets if item["id"] == "antigravity-oauth")

    assert antigravity["experimental"] is True
    assert antigravity["provider"]["apiFormat"] == "antigravity_oauth"
    assert antigravity["provider"]["models"]["default"] == "gemini-3-flash-agent"
    assert antigravity["baseUrls"]
    assert antigravity["messages"]


def test_minimax_preset_uses_m3_with_one_m_context(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    presets = gateway.list_presets()["presets"]
    minimax = next(item for item in presets if item["id"] == "minimax")
    provider = gateway.normalize_provider(minimax["provider"])
    catalog = gateway.build_catalog_models(provider)

    assert provider["models"]["default"] == "MiniMax-M3"
    assert provider["modelCapabilities"]["MiniMax-M3"]["context_window"] == 1_000_000
    assert catalog[0]["display_name"] == "MiniMax / MiniMax-M3"
    assert catalog[0]["context_window"] == 1_000_000


def test_zhipu_coding_preset_uses_configbox_schema(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    presets = gateway.list_presets()["presets"]
    zhipu = next(item for item in presets if item["id"] == "zhipu-coding")
    provider = gateway.normalize_provider(zhipu["provider"])

    assert provider["apiFormat"] == "openai_chat"
    assert provider["baseUrl"] == "https://open.bigmodel.cn/api/coding/paas/v4"
    assert provider["extraHeaders"]["User-Agent"] == "claude-cli/2.1.175 (external, cli)"
    assert provider["models"]["default"] == "glm-4.7"
    assert provider["models"]["gpt_5_3_codex"] == "glm-4.6"


def test_antigravity_models_fall_back_to_preset_seed_when_gateway_is_stopped(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    payload = gateway.antigravity_models()

    assert payload["success"] is True
    assert payload["models"][0]["id"] == "gemini-3-flash-agent"
    assert payload["models"][0]["recommended"] is True


def test_gateway_normalization_unknown_format_falls_back_to_openai_chat(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    provider = gateway.normalize_provider(
        {
            "name": "Legacy",
            "baseUrl": "https://example.com/v1",
            "apiFormat": "unknown-protocol",
            "models": {"default": "legacy-model"},
        }
    )

    assert provider["apiFormat"] == "openai_chat"


def test_gateway_provider_name_allows_chinese(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    provider = gateway.normalize_provider(
        {
            "name": "中文供应商",
            "baseUrl": "https://example.com/v1",
            "models": {"default": "model"},
        }
    )

    assert provider["name"] == "中文供应商"


def test_grok_web_requires_credentials_and_masks_public_payload(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    try:
        gateway.normalize_provider(
            {
                "name": "Grok",
                "baseUrl": "https://grok.com",
                "apiFormat": "grok_web",
                "models": {"default": "grok-4"},
            }
        )
    except gateway.APIError as exc:
        assert exc.code == "INVALID_PROVIDER"
    else:
        raise AssertionError("grok_web without credentials should fail")

    provider = gateway.normalize_provider(
        {
            "name": "Grok",
            "baseUrl": "https://grok.com",
            "apiFormat": "grok_web",
            "models": {"default": "grok-4"},
            "grokWeb": {"cookies": {"sso": "jwt-token"}},
        }
    )

    public = gateway.public_provider(provider)
    assert provider["authScheme"] == "grok_cookie"
    assert public["hasGrokWeb"] is True
    assert "grokWeb" not in public


def test_provider_advanced_fields_validate_and_survive_normalization(tmp_path: Path):
    gateway, *_ = load_gateway(tmp_path)

    provider = gateway.normalize_provider(
        {
            "name": "Advanced",
            "baseUrl": "https://example.com/v1",
            "apiFormat": "gemini_cli_oauth",
            "models": {"default": "gemini-3-flash"},
            "extraHeaders": {"x-client": "configbox"},
            "modelCapabilities": {"gemini-3-flash": {"supports1m": True}},
            "requestOptions": {"web_search_enabled": True},
        }
    )

    assert provider["authScheme"] == "google_oauth_cloud_code"
    assert provider["extraHeaders"] == {"x-client": "configbox"}
    assert provider["modelCapabilities"]["gemini-3-flash"]["supports1m"] is True
    assert provider["requestOptions"]["web_search_enabled"] is True
