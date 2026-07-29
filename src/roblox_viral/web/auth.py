from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER, HTTP_401_UNAUTHORIZED


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
