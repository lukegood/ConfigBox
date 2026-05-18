from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import subprocess
import time
from collections.abc import MutableMapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import tomlkit

from .errors import APIError
from .registry import DATA_DIR
from .storage import atomic_write
from .validators import validate_content


GATEWAY_DIR = Path(os.getenv("CODEX_GATEWAY_DIR", str(DATA_DIR / "codex-gateway")))
GATEWAY_CONFIG_PATH = Path(
    os.getenv("CODEX_GATEWAY_CONFIG_PATH", str(GATEWAY_DIR / "config.json"))
)
GATEWAY_LOG_DIR = Path(os.getenv("CODEX_GATEWAY_LOG_DIR", str(GATEWAY_DIR / "logs")))
GATEWAY_BIN = os.getenv("CODEX_GATEWAY_BIN", "/usr/local/bin/codex-gateway")
GATEWAY_HOST = os.getenv("CODEX_GATEWAY_HOST", "0.0.0.0")
CODEX_GATEWAY_PUBLIC_HOST = os.getenv("CODEX_GATEWAY_PUBLIC_HOST", "127.0.0.1")
DEFAULT_PROXY_PORT = int(os.getenv("CODEX_GATEWAY_PORT", "18080"))
GATEWAY_LOG_MAX_MB = int(os.getenv("GATEWAY_LOG_MAX_MB", "50"))
CONFIGBOX_GATEWAY_PROVIDER = "configbox_gateway"
MANAGED_AUTH_KEYS = ("auth_mode", "OPENAI_API_KEY")
MANAGED_ROOT_KEYS = (
    "model_provider",
    "model",
    "openai_base_url",
    "model_context_window",
    "model_catalog_json",
)
MODEL_CATALOG_FILENAME = "codex-model-catalog.json"
MODEL_CATALOG_CLIENT_PATH = os.getenv("CODEX_MODEL_CATALOG_CLIENT_PATH", "").strip()
DEFAULT_CONTEXT_WINDOW = 258_400
ONE_M_CONTEXT_WINDOW = 1_000_000
AUTO_COMPACT_TRIGGER_PERCENT = 80
DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT = 95
MODEL_SLOT_TO_CODEX_ID = {
    "gpt_5_5": "gpt-5.5",
    "gpt_5_4": "gpt-5.4",
    "gpt_5_4_mini": "gpt-5.4-mini",
    "gpt_5_3_codex": "gpt-5.3-codex",
    "gpt_5_2": "gpt-5.2",
}
DOCUMENTED_CONTEXT_WINDOWS = {
    "deepseek-v4-pro": ONE_M_CONTEXT_WINDOW,
    "deepseek-v4-flash": ONE_M_CONTEXT_WINDOW,
    "kimi-for-coding": 262_144,
    "kimi-k2.5": 262_144,
    "kimi-k2.6": 262_144,
    "kimi-2.6": 262_144,
    "moonshot-v1-8k": 8_192,
    "moonshot-v1-8k-vision-preview": 8_192,
    "moonshot-v1-32k": 32_768,
    "moonshot-v1-32k-vision-preview": 32_768,
    "moonshot-v1-128k": 131_072,
    "moonshot-v1-auto": 131_072,
    "moonshot-v1-128k-vision-preview": 131_072,
    "mimo-v2-pro": ONE_M_CONTEXT_WINDOW,
    "mimo-v2.5": ONE_M_CONTEXT_WINDOW,
    "mimo-v2.5-pro": ONE_M_CONTEXT_WINDOW,
    "mimo-v2-flash": 262_144,
    "mimo-v2-omni": 262_144,
    "glm-5.1": 200_000,
    "glm-4.7": 200_000,
    "qwen3.6-plus": ONE_M_CONTEXT_WINDOW,
    "qwen3.6-flash": ONE_M_CONTEXT_WINDOW,
    "minimax-m2.7": 204_800,
    "gemini-3.1-flash-lite": ONE_M_CONTEXT_WINDOW,
    "gemini-2.5-flash": ONE_M_CONTEXT_WINDOW,
    "gemini-3-flash": ONE_M_CONTEXT_WINDOW,
}

_process: subprocess.Popen[str] | None = None


def default_config() -> dict[str, Any]:
    return {
        "version": "1.0.4",
        "activeProvider": None,
        "gatewayApiKey": f"cas_{secrets.token_urlsafe(24)}",
        "providers": [],
        "settings": {
            "theme": "default",
            "language": "zh",
            "proxyPort": DEFAULT_PROXY_PORT,
            "adminPort": 18081,
            "autoStart": False,
            "autoApplyOnStart": True,
            "exposeAllProviderModels": False,
            "restoreCodexOnExit": False,
            "updateUrl": "",
        },
    }


def ensure_gateway() -> None:
    GATEWAY_DIR.mkdir(parents=True, exist_ok=True)
    GATEWAY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not GATEWAY_CONFIG_PATH.exists():
        write_config(default_config())
    prune_logs()


def startup_recover_codex() -> bool:
    ensure_gateway()
    if not snapshot_path().exists():
        return False
    if is_port_healthy(proxy_port()):
        return False
    return restore_codex_if_snapshot()


def startup_clear_logs() -> None:
    clear_logs()


def read_config() -> dict[str, Any]:
    ensure_gateway()
    try:
        data = json.loads(GATEWAY_CONFIG_PATH.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise APIError("INVALID_GATEWAY_CONFIG", f"Invalid gateway config JSON: {exc}", 500) from exc
    return normalize_config(data)


def write_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_config(config)
    atomic_write(
        GATEWAY_CONFIG_PATH,
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
    )
    return normalized


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    base = default_config()
    merged = {**base, **config}
    settings = {**base["settings"], **dict(config.get("settings") or {})}
    merged["settings"] = settings
    merged["providers"] = list(config.get("providers") or [])
    if not merged.get("gatewayApiKey"):
        merged["gatewayApiKey"] = base["gatewayApiKey"]
    provider_ids = {str(provider.get("id", "")) for provider in merged["providers"]}
    if merged.get("activeProvider") not in provider_ids:
        merged["activeProvider"] = next(iter(provider_ids), None)
    return merged


def public_config() -> dict[str, Any]:
    config = read_config()
    public = dict(config)
    public["gatewayApiKeyPresent"] = bool(config.get("gatewayApiKey"))
    public["gatewayApiKey"] = str(config.get("gatewayApiKey") or "")
    public["providers"] = [public_provider(provider) for provider in config["providers"]]
    public["path"] = str(GATEWAY_CONFIG_PATH)
    public["logDir"] = str(GATEWAY_LOG_DIR)
    return public


def public_provider(provider: dict[str, Any]) -> dict[str, Any]:
    result = dict(provider)
    api_key = str(result.get("apiKey") or "")
    result["apiKey"] = api_key
    result["hasApiKey"] = bool(api_key)
    if "extraHeaders" in result:
        result["extraHeadersPresent"] = True
    grok_web = result.pop("grokWeb", None)
    result["hasGrokWeb"] = has_grok_web_credentials(grok_web)
    return result


def list_providers() -> list[dict[str, Any]]:
    return [public_provider(provider) for provider in read_config()["providers"]]


def provider_index(config: dict[str, Any], provider_id: str) -> int | None:
    for index, provider in enumerate(config["providers"]):
        if provider.get("id") == provider_id:
            return index
    return None


def normalize_provider(payload: dict[str, Any], existing_id: str | None = None) -> dict[str, Any]:
    provider_id = existing_id or str(payload.get("id") or fresh_provider_id())
    name = str(payload.get("name") or provider_id).strip()
    base_url = str(payload.get("baseUrl") or payload.get("base_url") or "").strip()
    if not name:
        raise APIError("INVALID_PROVIDER", "Provider name is required.", 400)
    if not base_url:
        raise APIError("INVALID_PROVIDER", "Provider baseUrl is required.", 400)
    models = payload.get("models") if isinstance(payload.get("models"), dict) else {}
    default_model = str(models.get("default") or payload.get("defaultModel") or "").strip()
    if default_model and not models.get("default"):
        models = {**models, "default": default_model}
    extra_headers = normalize_string_map(payload.get("extraHeaders"), "extraHeaders")
    model_capabilities = normalize_object_map(payload.get("modelCapabilities"), "modelCapabilities")
    request_options = normalize_object_map(payload.get("requestOptions"), "requestOptions")
    api_format = normalize_api_format(str(payload.get("apiFormat") or "openai_chat"))
    grok_web = normalize_grok_web(payload.get("grokWeb"))
    if api_format == "grok_web" and not has_grok_web_credentials(grok_web):
        raise APIError(
            "INVALID_PROVIDER",
            "grok_web requires grokWeb.cookies.sso.",
            400,
        )
    normalized = {
        "id": provider_id,
        "name": name,
        "baseUrl": base_url.rstrip("/"),
        "authScheme": str(payload.get("authScheme") or recommended_auth_scheme(api_format)),
        "apiFormat": api_format,
        "apiKey": str(payload.get("apiKey") or ""),
        "models": normalize_models(models),
        "extraHeaders": extra_headers,
        "modelCapabilities": model_capabilities,
        "requestOptions": request_options,
        "isBuiltin": bool(payload.get("isBuiltin", False)),
        "sortIndex": int(payload.get("sortIndex") or 0),
    }
    if grok_web is not None:
        normalized["grokWeb"] = grok_web
    return normalized


def normalize_api_format(value: str) -> str:
    lowered = value.strip().lower().replace("-", "_")
    if lowered in {"openai", "openai_chat", "chat_completions"}:
        return "openai_chat"
    if lowered in {"responses", "openai_responses"}:
        return "responses"
    if lowered in {
        "anthropic_messages",
        "anthropic",
        "claude",
        "messages",
        "claude_messages",
    }:
        return "anthropic_messages"
    if lowered in {"gemini_native", "google_ai_studio", "gemini"}:
        return "gemini_native"
    if lowered in {"gemini_cli_oauth", "gemini_cli", "google_oauth_cloud_code"}:
        return "gemini_cli_oauth"
    if lowered in {"antigravity_oauth", "antigravity", "google_oauth_antigravity"}:
        return "antigravity_oauth"
    if lowered in {"grok_web", "grok"}:
        return "grok_web"
    return "openai_chat"


def normalize_models(models: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in models.items():
        key = str(raw_key).strip()
        value = str(raw_value or "").strip()
        if key:
            normalized[key] = value
    for slot in ("default", *MODEL_SLOT_TO_CODEX_ID.keys()):
        normalized.setdefault(slot, "")
    return normalized


def recommended_auth_scheme(api_format: str) -> str:
    if api_format == "gemini_native":
        return "google_api_key"
    if api_format == "gemini_cli_oauth":
        return "google_oauth_cloud_code"
    if api_format == "antigravity_oauth":
        return "google_oauth_antigravity"
    if api_format == "grok_web":
        return "grok_cookie"
    return "bearer"


def normalize_string_map(value: Any, field: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise APIError("INVALID_PROVIDER", f"{field} must be an object.", 400)
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            continue
        if not isinstance(raw_value, str):
            raise APIError("INVALID_PROVIDER", f"{field}.{key} must be a string.", 400)
        if any(ch in key for ch in "\r\n:") or any(ch in raw_value for ch in "\r\n"):
            raise APIError("INVALID_PROVIDER", f"{field}.{key} contains invalid header characters.", 400)
        normalized[key] = raw_value
    return normalized


def normalize_object_map(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise APIError("INVALID_PROVIDER", f"{field} must be an object.", 400)
    return dict(value)


def normalize_grok_web(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise APIError("INVALID_PROVIDER", "grokWeb must be an object.", 400)
    cookies = value.get("cookies")
    if cookies is not None and not isinstance(cookies, dict):
        raise APIError("INVALID_PROVIDER", "grokWeb.cookies must be an object.", 400)
    normalized: dict[str, Any] = {}
    if isinstance(cookies, dict):
        normalized_cookies: dict[str, str] = {}
        for raw_key, raw_value in cookies.items():
            key = str(raw_key).strip()
            if not key:
                continue
            if not isinstance(raw_value, str):
                raise APIError("INVALID_PROVIDER", f"grokWeb.cookies.{key} must be a string.", 400)
            normalized_cookies[key] = raw_value
        if normalized_cookies:
            normalized["cookies"] = normalized_cookies
    for field in ("statsigId", "userAgent"):
        if field not in value:
            continue
        raw = value[field]
        if not isinstance(raw, str):
            raise APIError("INVALID_PROVIDER", f"grokWeb.{field} must be a string.", 400)
        if raw:
            normalized[field] = raw
    return normalized


def has_grok_web_credentials(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    cookies = value.get("cookies")
    if not isinstance(cookies, dict):
        return False
    return bool(str(cookies.get("sso") or "").strip())


def fresh_provider_id() -> str:
    return secrets.token_hex(4)


def add_provider(payload: dict[str, Any]) -> dict[str, Any]:
    config = read_config()
    provider = normalize_provider(payload)
    existing = {provider.get("id") for provider in config["providers"]}
    while provider["id"] in existing:
        provider["id"] = fresh_provider_id()
    provider["sortIndex"] = len(config["providers"])
    config["providers"].append(provider)
    if not config.get("activeProvider"):
        config["activeProvider"] = provider["id"]
    write_config(config)
    return public_provider(provider)


def update_provider(provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    config = read_config()
    index = provider_index(config, provider_id)
    if index is None:
        raise APIError("PROVIDER_NOT_FOUND", "Provider not found.", 404)
    current = config["providers"][index]
    merged = {**current, **payload}
    provider = normalize_provider(merged, existing_id=provider_id)
    provider["sortIndex"] = int(current.get("sortIndex") or index)
    config["providers"][index] = provider
    write_config(config)
    return public_provider(provider)


def delete_provider(provider_id: str) -> None:
    config = read_config()
    index = provider_index(config, provider_id)
    if index is None:
        raise APIError("PROVIDER_NOT_FOUND", "Provider not found.", 404)
    config["providers"].pop(index)
    if config.get("activeProvider") == provider_id:
        config["activeProvider"] = config["providers"][0]["id"] if config["providers"] else None
    write_config(config)


def activate_provider(provider_id: str) -> dict[str, Any]:
    config = read_config()
    index = provider_index(config, provider_id)
    if index is None:
        raise APIError("PROVIDER_NOT_FOUND", "Provider not found.", 404)
    config["activeProvider"] = provider_id
    write_config(config)
    return public_provider(config["providers"][index])


def active_provider(config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    config = config or read_config()
    active_id = config.get("activeProvider")
    for provider in config["providers"]:
        if provider.get("id") == active_id:
            return provider
    return config["providers"][0] if config["providers"] else None


def proxy_port(config: dict[str, Any] | None = None) -> int:
    config = config or read_config()
    try:
        return int(config.get("settings", {}).get("proxyPort") or DEFAULT_PROXY_PORT)
    except (TypeError, ValueError):
        return DEFAULT_PROXY_PORT


def start_gateway() -> dict[str, Any]:
    global _process
    ensure_gateway()
    clear_logs()
    config = read_config()
    if not config["providers"]:
        raise APIError("NO_GATEWAY_PROVIDER", "Add a gateway provider before starting.", 400)
    if is_process_alive(_process):
        apply_codex()
        status = gateway_status()
        status["codexApplied"] = True
        return status
    if is_port_healthy(proxy_port(config)):
        apply_codex()
        status = gateway_status()
        status["codexApplied"] = True
        return status
    bin_path = Path(GATEWAY_BIN)
    if not bin_path.exists():
        raise APIError(
            "GATEWAY_BINARY_MISSING",
            f"codex-gateway binary not found: {bin_path}",
            500,
        )
    cmd = [
        str(bin_path),
        "--config",
        str(GATEWAY_CONFIG_PATH),
        "--host",
        GATEWAY_HOST,
        "--port",
        str(proxy_port(config)),
        "--log-dir",
        str(GATEWAY_LOG_DIR),
    ]
    log_file = GATEWAY_LOG_DIR / "sidecar.log"
    log_handle = open(log_file, "a", encoding="utf-8")
    _process = subprocess.Popen(
        cmd,
        stdout=log_handle,
        stderr=log_handle,
        text=True,
        start_new_session=True,
    )
    deadline = time.time() + 8
    while time.time() < deadline:
        if _process.poll() is not None:
            raise APIError("GATEWAY_START_FAILED", "codex-gateway exited during startup.", 500)
        if is_port_healthy(proxy_port(config)):
            apply_codex()
            status = gateway_status()
            status["codexApplied"] = True
            return status
        time.sleep(0.2)
    raise APIError("GATEWAY_START_TIMEOUT", "Timed out waiting for codex-gateway.", 504)


def stop_gateway(restore_codex_config: bool = True) -> dict[str, Any]:
    global _process
    process = _process
    if process and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.time() + 5
        while time.time() < deadline and process.poll() is None:
            time.sleep(0.1)
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    _process = None
    restored = restore_codex_if_snapshot() if restore_codex_config else False
    status = gateway_status()
    status["codexRestored"] = restored
    return status


def restart_gateway() -> dict[str, Any]:
    stop_gateway(restore_codex_config=False)
    return start_gateway()


def gateway_status() -> dict[str, Any]:
    config = read_config()
    port = proxy_port(config)
    process_running = is_process_alive(_process)
    healthy = is_port_healthy(port)
    return {
        "running": process_running or healthy,
        "managedProcess": process_running,
        "pid": _process.pid if process_running and _process else None,
        "healthy": healthy,
        "host": GATEWAY_HOST,
        "publicBaseUrl": public_base_url(port),
        "port": port,
        "configPath": str(GATEWAY_CONFIG_PATH),
        "logDir": str(GATEWAY_LOG_DIR),
        "activeProvider": config.get("activeProvider"),
        "providerCount": len(config["providers"]),
    }


def is_process_alive(process: subprocess.Popen[str] | None) -> bool:
    return bool(process and process.poll() is None)


def is_port_healthy(port: int) -> bool:
    url = f"http://127.0.0.1:{port}/__health"
    try:
        with urlopen(url, timeout=1.0) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def oauth_admin_request(path: str, method: str = "GET") -> dict[str, Any]:
    port = proxy_port()
    if not is_port_healthy(port):
        raise APIError("GATEWAY_NOT_RUNNING", "Start Gateway before using OAuth login.", 409)
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=305) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        message = payload.get("error") or payload.get("message") or str(exc)
        raise APIError("OAUTH_FAILED", str(message), exc.code) from exc
    except (OSError, URLError) as exc:
        raise APIError("OAUTH_FAILED", f"OAuth admin request failed: {exc}", 502) from exc
    return payload if isinstance(payload, dict) else {}


def oauth_status(kind: str) -> dict[str, Any]:
    return oauth_admin_request(oauth_path(kind, "status"))


def oauth_login(kind: str) -> dict[str, Any]:
    return oauth_admin_request(oauth_path(kind, "login"), "POST")


def oauth_logout(kind: str) -> dict[str, Any]:
    return oauth_admin_request(oauth_path(kind, "logout"), "DELETE")


def oauth_path(kind: str, action: str) -> str:
    if kind not in {"gemini", "antigravity"}:
        raise APIError("INVALID_OAUTH_KIND", "Unsupported OAuth provider.", 404)
    return f"/__admin/{kind}-oauth/{action}"


def public_base_url(port: int) -> str:
    return f"http://{CODEX_GATEWAY_PUBLIC_HOST}:{port}"


def codex_auth_path() -> Path:
    return Path(os.getenv("CODEX_CONFIG_PATH", "/config/codex/auth.json"))


def codex_config_path() -> Path:
    return Path(
        os.getenv(
            "CODEX_CONFIG_TOML_PATH",
            str(codex_auth_path().with_name("config.toml")),
        )
    )


def snapshot_path() -> Path:
    return GATEWAY_DIR / "codex-snapshot.json"


def model_catalog_path() -> Path:
    return GATEWAY_DIR / MODEL_CATALOG_FILENAME


def apply_codex() -> dict[str, Any]:
    config = read_config()
    provider = active_provider(config)
    if provider is None:
        raise APIError("NO_GATEWAY_PROVIDER", "Add a gateway provider before applying.", 400)
    applied_model = preferred_model(provider)
    ensure_snapshot()
    apply_auth(config)
    apply_toml(config, provider, applied_model)
    record_applied_state(applied_model)
    return {
        "success": True,
        "authJsonPath": str(codex_auth_path()),
        "configTomlPath": str(codex_config_path()),
        "baseUrl": public_base_url(proxy_port(config)),
        "gatewayApiKeyPresent": bool(config.get("gatewayApiKey")),
    }


def ensure_snapshot() -> None:
    path = snapshot_path()
    if path.exists():
        return
    auth = read_json_file(codex_auth_path())
    config_doc = read_toml_doc(codex_config_path())
    snapshot = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "auth": {
            key: {"exists": key in auth, "value": auth.get(key)}
            for key in MANAGED_AUTH_KEYS
        },
        "config": {
            key: {"exists": key in config_doc, "value": plain_value(config_doc.get(key))}
            for key in MANAGED_ROOT_KEYS
        },
        "gatewayProvider": table_snapshot(config_doc),
        "applied": {},
    }
    atomic_write(path, json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")


def record_applied_state(applied_model: str) -> None:
    path = snapshot_path()
    if not path.exists():
        return
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["applied"] = {"model": applied_model}
    atomic_write(path, json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise APIError("INVALID_CODEX_AUTH", f"Invalid Codex auth.json: {exc}", 422) from exc
    return value if isinstance(value, dict) else {}


def read_toml_doc(path: Path) -> tomlkit.TOMLDocument:
    if not path.exists():
        return tomlkit.document()
    content = path.read_text(encoding="utf-8")
    validate_content("toml", content)
    return tomlkit.parse(content)


def table_snapshot(doc: tomlkit.TOMLDocument) -> dict[str, Any]:
    providers = doc.get("model_providers")
    if not isinstance(providers, MutableMapping) or CONFIGBOX_GATEWAY_PROVIDER not in providers:
        return {"exists": False, "value": None}
    fragment = tomlkit.document()
    model_providers = tomlkit.table()
    model_providers[CONFIGBOX_GATEWAY_PROVIDER] = providers[CONFIGBOX_GATEWAY_PROVIDER]
    fragment["model_providers"] = model_providers
    return {"exists": True, "toml": tomlkit.dumps(fragment)}


def plain_value(value: Any) -> Any:
    if hasattr(value, "unwrap"):
        return value.unwrap()
    return value


def apply_auth(config: dict[str, Any]) -> None:
    path = codex_auth_path()
    auth = read_json_file(path)
    auth["auth_mode"] = "apikey"
    auth["OPENAI_API_KEY"] = str(config.get("gatewayApiKey") or "")
    atomic_write(path, json.dumps(auth, indent=2, ensure_ascii=False) + "\n")


def apply_toml(config: dict[str, Any], provider: dict[str, Any], applied_model: str) -> None:
    path = codex_config_path()
    doc = read_toml_doc(path)
    port = proxy_port(config)
    base_url = public_base_url(port)
    doc["model_provider"] = CONFIGBOX_GATEWAY_PROVIDER
    doc["model"] = applied_model
    doc["openai_base_url"] = base_url
    catalog_models = build_catalog_models(provider)
    write_model_catalog(catalog_models)
    doc["model_catalog_json"] = model_catalog_client_path()
    if default_model_context_window(provider) >= ONE_M_CONTEXT_WINDOW:
        doc["model_context_window"] = ONE_M_CONTEXT_WINDOW
    else:
        doc.pop("model_context_window", None)
    providers = doc.get("model_providers")
    if not isinstance(providers, MutableMapping):
        providers = tomlkit.table()
        doc["model_providers"] = providers
    gateway = tomlkit.table()
    gateway["name"] = "ConfigBox Gateway"
    gateway["base_url"] = f"{base_url}/v1"
    gateway["wire_api"] = "responses"
    gateway["requires_openai_auth"] = True
    providers[CONFIGBOX_GATEWAY_PROVIDER] = gateway
    atomic_write(path, tomlkit.dumps(doc))


def preferred_model(provider: dict[str, Any]) -> str:
    models = provider.get("models") if isinstance(provider.get("models"), dict) else {}
    slot_to_model = {
        "gpt_5_5": "gpt-5.5",
        "gpt_5_4": "gpt-5.4",
        "gpt_5_4_mini": "gpt-5.4-mini",
        "gpt_5_3_codex": "gpt-5.3-codex",
        "gpt_5_2": "gpt-5.2",
    }
    for key in ("gpt_5_3_codex", "gpt_5_5", "gpt_5_4", "gpt_5_4_mini", "gpt_5_2"):
        value = str(models.get(key) or "").strip()
        if value:
            return slot_to_model[key]
    if str(models.get("default") or "").strip():
        return "gpt-5.3-codex"
    return "gpt-5.3-codex"


def restore_codex() -> dict[str, Any]:
    path = snapshot_path()
    if not path.exists():
        raise APIError("SNAPSHOT_NOT_FOUND", "No Codex gateway snapshot found.", 404)
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    restore_auth(snapshot)
    restore_toml(snapshot)
    model_catalog_path().unlink(missing_ok=True)
    path.unlink(missing_ok=True)
    return {
        "success": True,
        "authJsonPath": str(codex_auth_path()),
        "configTomlPath": str(codex_config_path()),
    }


def restore_codex_if_snapshot() -> bool:
    if not snapshot_path().exists():
        return False
    restore_codex()
    return True


def restore_auth(snapshot: dict[str, Any]) -> None:
    path = codex_auth_path()
    auth = read_json_file(path)
    for key, entry in dict(snapshot.get("auth") or {}).items():
        if entry.get("exists"):
            auth[key] = entry.get("value")
        else:
            auth.pop(key, None)
    atomic_write(path, json.dumps(auth, indent=2, ensure_ascii=False) + "\n")


def restore_toml(snapshot: dict[str, Any]) -> None:
    path = codex_config_path()
    doc = read_toml_doc(path)
    applied_model = dict(snapshot.get("applied") or {}).get("model")
    for key, entry in dict(snapshot.get("config") or {}).items():
        if key == "model" and applied_model is not None:
            current_model = plain_value(doc.get("model"))
            if current_model != applied_model:
                continue
        if entry.get("exists"):
            doc[key] = entry.get("value")
        else:
            doc.pop(key, None)
    providers = doc.get("model_providers")
    if isinstance(providers, MutableMapping):
        gateway_snapshot = snapshot.get("gatewayProvider") or {}
        if gateway_snapshot.get("exists"):
            fragment = tomlkit.parse(str(gateway_snapshot.get("toml") or ""))
            providers[CONFIGBOX_GATEWAY_PROVIDER] = fragment["model_providers"][CONFIGBOX_GATEWAY_PROVIDER]
        else:
            providers.pop(CONFIGBOX_GATEWAY_PROVIDER, None)
        if not providers:
            doc.pop("model_providers", None)
    atomic_write(path, tomlkit.dumps(doc))


def write_model_catalog(models: list[dict[str, Any]]) -> None:
    path = model_catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps({"models": models}, indent=2, ensure_ascii=False) + "\n")


def model_catalog_client_path() -> str:
    if MODEL_CATALOG_CLIENT_PATH:
        return MODEL_CATALOG_CLIENT_PATH
    return str(model_catalog_path().resolve())


def build_catalog_models(provider: dict[str, Any]) -> list[dict[str, Any]]:
    models = provider.get("models") if isinstance(provider.get("models"), dict) else {}
    default_model = clean_model_id(str(models.get("default") or ""))
    entries: list[dict[str, Any]] = []
    for slot, codex_id in MODEL_SLOT_TO_CODEX_ID.items():
        target = clean_model_id(str(models.get(slot) or default_model))
        entries.append(
            catalog_model(
                codex_id,
                str(provider.get("name") or provider.get("id") or "Gateway"),
                target or codex_id,
                context_window_for_model(provider, target or default_model),
            )
        )
    if default_model and not any(entry["slug"] == default_model for entry in entries):
        entries.append(
            catalog_model(
                default_model,
                str(provider.get("name") or provider.get("id") or "Gateway"),
                default_model,
                context_window_for_model(provider, default_model),
            )
        )
    return entries


def default_model_context_window(provider: dict[str, Any]) -> int:
    models = provider.get("models") if isinstance(provider.get("models"), dict) else {}
    return context_window_for_model(provider, clean_model_id(str(models.get("default") or "")))


def context_window_for_model(provider: dict[str, Any], model: str) -> int:
    clean = clean_model_id(model)
    explicit = explicit_context_window(provider, clean)
    if explicit is not None:
        return explicit
    documented = DOCUMENTED_CONTEXT_WINDOWS.get(clean.lower())
    if documented is not None:
        return documented
    if model_supports_1m(provider, clean):
        return ONE_M_CONTEXT_WINDOW
    return DEFAULT_CONTEXT_WINDOW


def explicit_context_window(provider: dict[str, Any], model: str) -> int | None:
    caps = provider.get("modelCapabilities")
    if not isinstance(caps, dict):
        return None
    for key, value in caps.items():
        if str(key).strip().lower() != model.lower() or not isinstance(value, dict):
            continue
        raw = value.get("context_window")
        if isinstance(raw, int) and raw >= 1024:
            return raw
    return None


def model_supports_1m(provider: dict[str, Any], model: str) -> bool:
    if has_internal_one_m_suffix(model):
        return True
    caps = provider.get("modelCapabilities")
    if not isinstance(caps, dict):
        return False
    for key, value in caps.items():
        if str(key).strip().lower() != clean_model_id(model).lower() or not isinstance(value, dict):
            continue
        if value.get("supports1m") is True:
            return True
        raw = value.get("context_window")
        if isinstance(raw, int) and raw >= ONE_M_CONTEXT_WINDOW:
            return True
    return False


def has_internal_one_m_suffix(model: str) -> bool:
    return model.strip().lower().endswith("[1m]")


def clean_model_id(model: str) -> str:
    stripped = model.strip()
    if has_internal_one_m_suffix(stripped):
        return stripped[: stripped.lower().rfind("[1m]")].rstrip()
    return stripped


def catalog_model(slug: str, provider_name: str, target_model: str, context_window: int) -> dict[str, Any]:
    entry = builtin_catalog_template(slug) or generic_catalog_template()
    entry.update(
        {
            "slug": slug,
            "display_name": f"{provider_name} / {target_model}",
            "description": f"Routed through ConfigBox Gateway as {provider_name} / {target_model}.",
            "context_window": context_window,
            "max_context_window": context_window,
            "effective_context_window_percent": DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT,
            "auto_compact_token_limit": context_window * AUTO_COMPACT_TRIGGER_PERCENT // 100,
        }
    )
    return entry


def builtin_catalog_template(slug: str) -> dict[str, Any] | None:
    templates = {
        "gpt-5.5": {
            "display_name": "GPT-5.5",
            "default_reasoning_level": "medium",
            "priority": 0,
            "web_search_tool_type": "text_and_image",
            "supports_image_detail_original": True,
        },
        "gpt-5.4": {
            "display_name": "gpt-5.4",
            "default_reasoning_level": "xhigh",
            "priority": 2,
            "web_search_tool_type": "text_and_image",
            "supports_image_detail_original": True,
        },
        "gpt-5.4-mini": {
            "display_name": "GPT-5.4-Mini",
            "default_reasoning_level": "medium",
            "priority": 4,
            "web_search_tool_type": "text_and_image",
            "supports_image_detail_original": True,
        },
        "gpt-5.3-codex": {
            "display_name": "gpt-5.3-codex",
            "default_reasoning_level": "medium",
            "priority": 6,
            "web_search_tool_type": "text",
            "supports_image_detail_original": True,
        },
        "gpt-5.2": {
            "display_name": "gpt-5.2",
            "default_reasoning_level": "medium",
            "priority": 10,
            "web_search_tool_type": "text",
            "supports_image_detail_original": False,
        },
    }
    template = templates.get(slug)
    if template is None:
        return None
    return {
        "slug": slug,
        "display_name": template["display_name"],
        "description": "",
        "default_reasoning_level": template["default_reasoning_level"],
        "supported_reasoning_levels": reasoning_levels(),
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "priority": template["priority"],
        "additional_speed_tiers": [],
        "availability_nux": None,
        "upgrade": None,
        "base_instructions": "",
        "supports_reasoning_summaries": True,
        "default_reasoning_summary": "none",
        "support_verbosity": True,
        "default_verbosity": "low",
        "apply_patch_tool_type": "freeform",
        "web_search_tool_type": template["web_search_tool_type"],
        "truncation_policy": {"mode": "tokens", "limit": 10_000},
        "supports_parallel_tool_calls": True,
        "supports_image_detail_original": template["supports_image_detail_original"],
        "context_window": 272_000,
        "max_context_window": 272_000,
        "effective_context_window_percent": DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT,
        "experimental_supported_tools": [],
        "input_modalities": ["text", "image"],
        "supports_search_tool": True,
    }


def generic_catalog_template() -> dict[str, Any]:
    return {
        "slug": "",
        "display_name": "",
        "description": "",
        "default_reasoning_level": "high",
        "supported_reasoning_levels": reasoning_levels()[:3],
        "shell_type": "default",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 10,
        "additional_speed_tiers": [],
        "availability_nux": None,
        "upgrade": None,
        "base_instructions": "",
        "supports_reasoning_summaries": False,
        "default_reasoning_summary": "auto",
        "support_verbosity": False,
        "default_verbosity": None,
        "apply_patch_tool_type": None,
        "web_search_tool_type": "text",
        "truncation_policy": {"mode": "bytes", "limit": 4_000_000},
        "supports_parallel_tool_calls": False,
        "supports_image_detail_original": False,
        "context_window": DEFAULT_CONTEXT_WINDOW,
        "max_context_window": DEFAULT_CONTEXT_WINDOW,
        "effective_context_window_percent": DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT,
        "experimental_supported_tools": [],
        "input_modalities": ["text", "image"],
        "supports_search_tool": False,
    }


def reasoning_levels() -> list[dict[str, str]]:
    return [
        {"effort": "low", "description": "Fast responses with lighter reasoning"},
        {"effort": "medium", "description": "Balanced speed and reasoning depth"},
        {"effort": "high", "description": "Greater reasoning depth for complex tasks"},
        {"effort": "xhigh", "description": "Extra high reasoning depth for complex tasks"},
    ]


def read_logs(limit: int = 300) -> dict[str, Any]:
    ensure_gateway()
    files = sorted(GATEWAY_LOG_DIR.glob("*.log"), key=lambda item: item.stat().st_mtime)
    lines: list[str] = []
    for path in files[-5:]:
        try:
            lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
    return {
        "lines": lines[-limit:],
        "logDir": str(GATEWAY_LOG_DIR),
        "maxBytes": log_max_bytes(),
        "currentBytes": log_total_size(),
    }


def clear_logs() -> dict[str, Any]:
    ensure_gateway()
    removed = 0
    for path in log_files():
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return {"success": True, "removed": removed, "logDir": str(GATEWAY_LOG_DIR)}


def prune_logs() -> None:
    max_bytes = log_max_bytes()
    files = sorted(log_files(), key=lambda item: item.stat().st_mtime)
    total = sum(safe_file_size(path) for path in files)
    for path in files:
        if total <= max_bytes:
            break
        size = safe_file_size(path)
        try:
            path.unlink()
            total -= size
        except OSError:
            continue


def log_files() -> list[Path]:
    if not GATEWAY_LOG_DIR.exists():
        return []
    return [path for path in GATEWAY_LOG_DIR.glob("*.log") if path.is_file()]


def log_total_size() -> int:
    return sum(safe_file_size(path) for path in log_files())


def log_max_bytes() -> int:
    return max(1, GATEWAY_LOG_MAX_MB) * 1024 * 1024


def safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0
