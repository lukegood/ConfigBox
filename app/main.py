from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import AuthUser, authenticate, clear_session_cookie, default_password_warning, require_user, set_session_cookie
from .errors import APIError
from .registry import get_tool, public_tools
from .schemas import (
    OkResponse,
    LoginRequest,
    ProfileCreateRequest,
    ProfileSaveRequest,
    SaveActiveRequest,
)
from .storage import (
    activate_profile,
    create_profile,
    delete_profile,
    ensure_all,
    list_backups,
    list_profiles,
    read_active,
    read_backup,
    read_profile,
    restore_backup,
    save_active,
    save_profile,
)
from . import gateway


app = FastAPI(title="ConfigBox", version="0.3.0")


@app.on_event("startup")
def startup() -> None:
    ensure_all()
    gateway.ensure_gateway()
    gateway.startup_clear_logs()
    gateway.startup_recover_codex()


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    headers = {}
    if exc.status_code == 401:
        headers["WWW-Authenticate"] = "Basic"
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": {"code": "VALIDATION_ERROR", "message": "Invalid request body or parameters."},
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": {"code": "NOT_FOUND", "message": "Endpoint not found."}},
        )
    return await http_exception_handler(request, exc)


@app.get("/api/me")
def me(user: AuthUser = Depends(require_user)) -> dict:
    return {"username": user.username, "defaultPassword": default_password_warning()}


@app.post("/api/login")
def login(payload: LoginRequest, response: Response) -> dict:
    user = authenticate(payload.username, payload.password)
    set_session_cookie(response, user)
    return {"username": user.username, "defaultPassword": default_password_warning()}


@app.post("/api/logout", response_model=OkResponse)
def logout(response: Response) -> OkResponse:
    clear_session_cookie(response)
    return OkResponse()


@app.get("/api/tools")
def tools(user: AuthUser = Depends(require_user)) -> list[dict]:
    return public_tools()


@app.get("/api/configs/{tool}/active")
def get_active(tool: str, user: AuthUser = Depends(require_user)) -> dict:
    return read_active(get_tool(tool))


@app.put("/api/configs/{tool}/active")
def put_active(tool: str, payload: SaveActiveRequest, user: AuthUser = Depends(require_user)) -> dict:
    files = [file.model_dump(by_alias=True) for file in payload.files] if payload.files else None
    return save_active(get_tool(tool), payload.content, payload.last_known_mtime, files)


@app.get("/api/profiles/{tool}")
def get_profiles(tool: str, user: AuthUser = Depends(require_user)) -> list[dict]:
    return list_profiles(get_tool(tool))


@app.post("/api/profiles/{tool}")
def post_profile(tool: str, payload: ProfileCreateRequest, user: AuthUser = Depends(require_user)) -> dict:
    source = "content" if payload.content is not None and payload.source == "content" else payload.source
    files = [file.model_dump(by_alias=True) for file in payload.files] if payload.files else None
    if files and payload.source == "content":
        source = "content"
    return create_profile(get_tool(tool), payload.name, source, payload.content, files)


@app.get("/api/profiles/{tool}/{name}")
def get_profile(tool: str, name: str, user: AuthUser = Depends(require_user)) -> dict:
    return read_profile(get_tool(tool), name)


@app.put("/api/profiles/{tool}/{name}")
def put_profile(tool: str, name: str, payload: ProfileSaveRequest, user: AuthUser = Depends(require_user)) -> dict:
    files = [file.model_dump(by_alias=True) for file in payload.files] if payload.files else None
    return save_profile(get_tool(tool), name, payload.content, files)


@app.delete("/api/profiles/{tool}/{name}", response_model=OkResponse)
def remove_profile(tool: str, name: str, user: AuthUser = Depends(require_user)) -> OkResponse:
    delete_profile(get_tool(tool), name)
    return OkResponse()


@app.post("/api/profiles/{tool}/{name}/activate")
def activate(tool: str, name: str, user: AuthUser = Depends(require_user)) -> dict:
    return activate_profile(get_tool(tool), name)


@app.get("/api/backups/{tool}")
def get_backups(tool: str, user: AuthUser = Depends(require_user)) -> list[dict]:
    return list_backups(get_tool(tool))


@app.get("/api/backups/{tool}/{backup_name}")
def get_backup(tool: str, backup_name: str, user: AuthUser = Depends(require_user)) -> dict:
    return read_backup(get_tool(tool), backup_name)


@app.post("/api/backups/{tool}/{backup_name}/restore")
def restore(tool: str, backup_name: str, user: AuthUser = Depends(require_user)) -> dict:
    return restore_backup(get_tool(tool), backup_name)


@app.get("/api/gateway/config")
def gateway_config(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.public_config()


@app.put("/api/gateway/config")
def put_gateway_config(payload: dict, user: AuthUser = Depends(require_user)) -> dict:
    gateway.write_config(payload)
    return gateway.public_config()


@app.get("/api/gateway/status")
def gateway_status(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.gateway_status()


@app.post("/api/gateway/start")
def gateway_start(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.start_gateway()


@app.post("/api/gateway/stop")
def gateway_stop(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.stop_gateway()


@app.post("/api/gateway/restart")
def gateway_restart(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.restart_gateway()


@app.get("/api/gateway/logs")
def gateway_logs(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.read_logs()


@app.post("/api/gateway/logs/clear")
def gateway_clear_logs(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.clear_logs()


@app.get("/api/gateway/providers")
def gateway_providers(user: AuthUser = Depends(require_user)) -> list[dict]:
    return gateway.list_providers()


@app.post("/api/gateway/providers")
def gateway_add_provider(payload: dict, user: AuthUser = Depends(require_user)) -> dict:
    return gateway.add_provider(payload)


@app.put("/api/gateway/providers/{provider_id}")
def gateway_update_provider(provider_id: str, payload: dict, user: AuthUser = Depends(require_user)) -> dict:
    return gateway.update_provider(provider_id, payload)


@app.delete("/api/gateway/providers/{provider_id}", response_model=OkResponse)
def gateway_delete_provider(provider_id: str, user: AuthUser = Depends(require_user)) -> OkResponse:
    gateway.delete_provider(provider_id)
    return OkResponse()


@app.post("/api/gateway/providers/{provider_id}/activate")
def gateway_activate_provider(provider_id: str, user: AuthUser = Depends(require_user)) -> dict:
    return gateway.activate_provider(provider_id)


@app.post("/api/gateway/apply")
def gateway_apply(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.apply_codex()


@app.post("/api/gateway/restore")
def gateway_restore(user: AuthUser = Depends(require_user)) -> dict:
    return gateway.restore_codex()


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


def run() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8787")),
    )


if __name__ == "__main__":
    run()
