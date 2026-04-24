from __future__ import annotations

import json
import re

import tomlkit

from .errors import APIError


PROFILE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
BACKUP_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,180}$")


def validate_profile_name(name: str) -> None:
    if not PROFILE_NAME_RE.fullmatch(name):
        raise APIError(
            "INVALID_PROFILE_NAME",
            "Invalid profile name. Use only a-z, A-Z, 0-9, _ and -, max length 64.",
            400,
        )


def validate_backup_name(name: str) -> None:
    if not BACKUP_NAME_RE.fullmatch(name):
        raise APIError("INVALID_BACKUP_NAME", "Invalid backup name.", 400)
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise APIError("INVALID_BACKUP_NAME", "Invalid backup name.", 400)


def validate_content(fmt: str, content: str) -> None:
    try:
        if fmt == "json":
            json.loads(content or "{}")
            return
        if fmt == "toml":
            tomlkit.parse(content or "")
            return
    except json.JSONDecodeError as exc:
        raise APIError(
            "INVALID_JSON",
            f"Invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}",
            422,
        ) from exc
    except tomlkit.exceptions.TOMLKitError as exc:
        raise APIError("INVALID_TOML", f"Invalid TOML: {exc}", 422) from exc

    raise APIError("UNSUPPORTED_FORMAT", "Unsupported config format.", 500)
