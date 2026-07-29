from __future__ import annotations

import secrets
from dataclasses import asdict
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER, HTTP_409_CONFLICT

from roblox_viral.web.auth import require_login, set_authenticated
from roblox_viral.web.config import Settings, get_settings
from roblox_viral.web.jobs import BusyError, JobManager
from roblox_viral.web.library import delete_source, list_outputs, list_sources, save_upload
from roblox_viral.web.voices import DEFAULT_VOICE, VoiceInfo, list_english_voices

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app. Tests should pass Settings.from_env() explicitly
    so get_settings()'s lru_cache does not leak env across cases.
    """
    settings = settings or get_settings()
    settings.ensure_media_dirs()

    app = FastAPI(title="Roblox Viral")
    app.state.settings = settings
    app.state.job_manager = JobManager()
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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
    async def generate_page(
        request: Request,
        _: None = Depends(require_login),
    ) -> HTMLResponse:
        settings = request.app.state.settings
        sources = list_sources(settings)
        try:
            voices = await list_english_voices()
        except Exception:
            voices = [VoiceInfo(DEFAULT_VOICE, "en-US", "Female")]
        return templates.TemplateResponse(
            request,
            "generate.html",
            {
                "sources": sources,
                "voices": voices,
                "default_voice": DEFAULT_VOICE,
                "recent_outputs": list_outputs(settings),
            },
        )

    @app.get("/library", response_class=HTMLResponse)
    def library_page(
        request: Request,
        _: None = Depends(require_login),
    ) -> HTMLResponse:
        settings = request.app.state.settings
        return templates.TemplateResponse(
            request,
            "library.html",
            {
                "sources": list_sources(settings),
                "error": None,
            },
        )

    @app.post("/library/upload", response_model=None)
    async def library_upload(
        request: Request,
        file: UploadFile = File(...),
        _: None = Depends(require_login),
    ) -> Response:
        settings = request.app.state.settings
        filename = file.filename or ""
        data = await file.read()
        try:
            save_upload(settings, filename, data)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "library.html",
                {
                    "sources": list_sources(settings),
                    "error": str(exc),
                },
                status_code=400,
            )
        return RedirectResponse("/library", status_code=HTTP_303_SEE_OTHER)

    @app.post("/library/delete", response_model=None)
    def library_delete(
        request: Request,
        name: str = Form(...),
        _: None = Depends(require_login),
    ) -> Response:
        settings = request.app.state.settings
        try:
            delete_source(settings, name)
        except (ValueError, FileNotFoundError) as exc:
            return templates.TemplateResponse(
                request,
                "library.html",
                {
                    "sources": list_sources(settings),
                    "error": str(exc),
                },
                status_code=400,
            )
        return RedirectResponse("/library", status_code=HTTP_303_SEE_OTHER)

    @app.post("/api/jobs")
    async def create_job(
        request: Request,
        background_tasks: BackgroundTasks,
        _: None = Depends(require_login),
    ) -> dict:
        settings = request.app.state.settings
        mgr: JobManager = request.app.state.job_manager
        body = await request.json()
        source_name = body.get("source_name", "")
        story = body.get("story", "")
        voice = body.get("voice") or DEFAULT_VOICE
        try:
            record = mgr.create(settings, source_name, story, voice)
        except BusyError as exc:
            raise HTTPException(
                status_code=HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        background_tasks.add_task(mgr.run_job, settings, record.id)
        return {"id": record.id, "status": record.status}

    @app.get("/api/jobs/{job_id}")
    def get_job(
        job_id: str,
        request: Request,
        _: None = Depends(require_login),
    ) -> dict:
        mgr: JobManager = request.app.state.job_manager
        record = mgr.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return asdict(record)

    @app.get("/media/outputs/{name}")
    def media_output(
        name: str,
        request: Request,
        _: None = Depends(require_login),
    ) -> FileResponse:
        settings = request.app.state.settings
        safe = Path(name).name
        if safe != name or not safe:
            raise HTTPException(status_code=400, detail="Invalid filename")
        path = (settings.outputs_dir / safe).resolve()
        if not str(path).startswith(str(settings.outputs_dir.resolve())):
            raise HTTPException(status_code=400, detail="Invalid path")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path, media_type="video/mp4", filename=safe)

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_app, factory=True, host="0.0.0.0", port=8000, reload=False)
