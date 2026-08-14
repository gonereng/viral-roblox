from __future__ import annotations

import secrets

from fastapi import HTTPException, Request
from starlette.status import HTTP_303_SEE_OTHER, HTTP_401_UNAUTHORIZED, HTTP_503_SERVICE_UNAVAILABLE


SESSION_AUTH_KEY = "authenticated"


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get(SESSION_AUTH_KEY))


def set_authenticated(request: Request, value: bool = True) -> None:
    if value:
        request.session[SESSION_AUTH_KEY] = True
    else:
        request.session.pop(SESSION_AUTH_KEY, None)


def wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return True
    return request.url.path.startswith("/api/")


async def require_login(request: Request) -> None:
    if is_authenticated(request):
        return
    if wants_json(request):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    raise HTTPException(
        status_code=HTTP_303_SEE_OTHER,
        detail="Redirect to login",
        headers={"Location": "/login"},
    )


async def require_api_key(request: Request) -> None:
    settings = request.app.state.settings
    expected = (settings.api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured",
        )
    provided = request.headers.get("X-API-Key") or ""
    try:
        ok = secrets.compare_digest(provided, expected)
    except ValueError:
        ok = False
    if not ok:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
