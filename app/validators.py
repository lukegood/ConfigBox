from __future__ import annotations

import json
import re

import tomlkit

from .errors import APIError


MAX_PROFILE_NAME_LENGTH = 64
HISTORY_ENTRY_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,180}$")


def validate_profile_name(name: str) -> None:
    invalid = (
        not name
        or len(name) > MAX_PROFILE_NAME_LENGTH
        or name.strip() != name
        or name.startswith(".")
        or ".." in name
        or "/" in name
        or "\\" in name
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    )
    if invalid:
        raise APIError(
            "INVALID_PROFILE_NAME",
            "Invalid profile name. Chinese, letters, numbers, spaces, _ and - are supported, max length 64.",
            400,
        )


def validate_history_entry_name(name: str) -> None:
    if not HISTORY_ENTRY_RE.fullmatch(name):
        raise APIError("INVALID_HISTORY_ENTRY", "Invalid history entry name.", 400)
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise APIError("INVALID_HISTORY_ENTRY", "Invalid history entry name.", 400)


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
