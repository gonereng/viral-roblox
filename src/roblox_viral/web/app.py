from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER

from roblox_viral.web.auth import require_login, set_authenticated
from roblox_viral.web.config import Settings, get_settings

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app. Tests should pass Settings.from_env() explicitly
    so get_settings()'s lru_cache does not leak env across cases.
    """
    settings = settings or get_settings()
    settings.ensure_media_dirs()

    app = FastAPI(title="Roblox Viral")
    app.state.settings = settings
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": None},
        )

    @app.post("/login", response_model=None)
    def login_submit(
        request: Request,
        password: str = Form(...),
    ) -> Response:
        expected = request.app.state.settings.app_password
        try:
            ok = secrets.compare_digest(password, expected)
        except ValueError:
            ok = False
        if ok:
            set_authenticated(request, True)
            return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid password"},
            status_code=401,
        )

    @app.post("/logout")
    @app.get("/logout")
    def logout(request: Request) -> RedirectResponse:
        set_authenticated(request, False)
        return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)

    @app.get("/", response_class=HTMLResponse)
    def generate_placeholder(
        request: Request,
        _: None = Depends(require_login),
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "base.html",
            {},
        )

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_app, factory=True, host="0.0.0.0", port=8000, reload=False)
