from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .errors import APIError


security = HTTPBasic(auto_error=False)
SESSION_COOKIE = "configbox_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class AuthUser:
    username: str


def configured_username() -> str:
    return os.getenv("APP_USERNAME", "admin")


def configured_password() -> str:
    return os.getenv("APP_PASSWORD", "change_this_password")


def configured_password_hash() -> str:
    return os.getenv("APP_PASSWORD_HASH", "")


def session_secret() -> str:
    return os.getenv("SESSION_SECRET") or configured_password_hash() or configured_password()


def cookie_secure() -> bool:
    return os.getenv("APP_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}


def default_password_warning() -> bool:
    return not configured_password_hash() and configured_password() in {"change_this_password", "please_change_me", "admin", ""}


def generate_password_hash(password: str, iterations: int = 260_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )


def verify_password(password: str) -> bool:
    password_hash = configured_password_hash()
    if not password_hash:
        if not configured_password():
            return False
        return hmac.compare_digest(password, configured_password())
    try:
        scheme, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _b64decode(salt_raw)
        expected = _b64decode(digest_raw)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def authenticate(username: str, password: str) -> AuthUser:
    expected_user = configured_username()
    ok = hmac.compare_digest(username, expected_user) and verify_password(password)
    if not ok:
        raise APIError("UNAUTHORIZED", "Invalid username or password.", 401)
    return AuthUser(username=username)


def set_session_cookie(response: Response, user: AuthUser) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.username),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def create_session_token(username: str) -> str:
    payload = {
        "u": username,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    payload_raw = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(payload_raw)
    return f"{payload_raw}.{signature}"


def user_from_session(token: str | None) -> AuthUser | None:
    if not token or "." not in token:
        return None
    payload_raw, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload_raw), signature):
        return None
    try:
        payload = json.loads(_b64decode(payload_raw))
    except (ValueError, json.JSONDecodeError):
        return None
    username = payload.get("u")
    expires_at = int(payload.get("exp", 0))
    if username != configured_username() or expires_at < int(time.time()):
        return None
    return AuthUser(username=username)


def _sign(payload_raw: str) -> str:
    digest = hmac.new(session_secret().encode("utf-8"), payload_raw.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(raw: str) -> bytes:
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def require_user(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> AuthUser:
    session_user = user_from_session(request.cookies.get(SESSION_COOKIE))
    if session_user:
        return session_user
    if credentials is not None:
        return authenticate(credentials.username, credentials.password)
    raise APIError("UNAUTHORIZED", "Authentication required.", 401)
