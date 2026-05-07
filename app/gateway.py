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
from urllib.error import URLError
from urllib.request import urlopen

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
MANAGED_ROOT_KEYS = ("model_provider", "model", "openai_base_url")

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
    public["gatewayApiKey"] = mask_secret(config.get("gatewayApiKey", ""))
    public["providers"] = [public_provider(provider) for provider in config["providers"]]
    public["path"] = str(GATEWAY_CONFIG_PATH)
    public["logDir"] = str(GATEWAY_LOG_DIR)
    return public


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "******"
    return f"{value[:6]}******{value[-4:]}"


def public_provider(provider: dict[str, Any]) -> dict[str, Any]:
    result = dict(provider)
    api_key = str(result.pop("apiKey", "") or "")
    result["hasApiKey"] = bool(api_key)
    if "extraHeaders" in result:
        result["extraHeadersPresent"] = True
        result.pop("extraHeaders", None)
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
    return {
        "id": provider_id,
        "name": name,
        "baseUrl": base_url.rstrip("/"),
        "authScheme": str(payload.get("authScheme") or "bearer"),
        "apiFormat": normalize_api_format(str(payload.get("apiFormat") or "openai_chat")),
        "apiKey": str(payload.get("apiKey") or ""),
        "models": normalize_models(models),
        "extraHeaders": dict(payload.get("extraHeaders") or {}),
        "modelCapabilities": dict(payload.get("modelCapabilities") or {}),
        "requestOptions": dict(payload.get("requestOptions") or {}),
        "isBuiltin": bool(payload.get("isBuiltin", False)),
        "sortIndex": int(payload.get("sortIndex") or 0),
    }


def normalize_api_format(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"openai", "openai_chat", "chat_completions"}:
        return "openai_chat"
    return "responses"


def normalize_models(models: dict[str, Any]) -> dict[str, str]:
    slots = ("default", "gpt_5_5", "gpt_5_4", "gpt_5_4_mini", "gpt_5_3_codex", "gpt_5_2")
    return {slot: str(models.get(slot) or "").strip() for slot in slots}


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


def apply_codex() -> dict[str, Any]:
    config = read_config()
    provider = active_provider(config)
    if provider is None:
        raise APIError("NO_GATEWAY_PROVIDER", "Add a gateway provider before applying.", 400)
    ensure_snapshot()
    apply_auth(config)
    apply_toml(config, provider)
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
    }
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


def apply_toml(config: dict[str, Any], provider: dict[str, Any]) -> None:
    path = codex_config_path()
    doc = read_toml_doc(path)
    port = proxy_port(config)
    base_url = public_base_url(port)
    doc["model_provider"] = CONFIGBOX_GATEWAY_PROVIDER
    doc["model"] = preferred_model(provider)
    doc["openai_base_url"] = base_url
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
    for key, entry in dict(snapshot.get("config") or {}).items():
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
