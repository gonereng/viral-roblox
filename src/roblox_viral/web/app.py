from __future__ import annotations

import json
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
from pydantic import BaseModel, ValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER, HTTP_409_CONFLICT

from roblox_viral.voice import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_VIDEO_SPEED,
    format_edge_pitch,
    format_edge_rate,
    validate_video_speed,
)
from roblox_viral.web.api_v1 import router as api_v1_router
from roblox_viral.web.auth import require_login, set_authenticated
from roblox_viral.web.config import Settings, get_settings
from roblox_viral.web.gemini import generate_story
from roblox_viral.web.jobs import BusyError, JobManager, normalize_mode
from roblox_viral.web import library as library_mod
from roblox_viral.web.library import (
    delete_image,
    delete_source,
    delete_video,
    list_images,
    list_outputs,
    list_sources,
    list_videos,
    media_type_for_name,
    resolve_image,
    resolve_source,
    resolve_video,
    save_image,
    save_upload,
    save_video,
)
from roblox_viral.web.prompt import load_prompt, save_prompt
from roblox_viral.web.voices import DEFAULT_VOICE, VoiceInfo, list_english_voices

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_UPLOAD_CHUNK = 1024 * 1024  # 1 MiB


def _library_ctx(
    settings: Settings,
    *,
    error: str | None = None,
    message: str | None = None,
    tab: str = "slices",
) -> dict:
    return {
        "sources": list_sources(settings),
        "videos": list_videos(settings),
        "images": list_images(settings),
        "error": error,
        "message": message,
        "tab": tab,
    }


class CreateJobBody(BaseModel):
    source_name: str = ""
    story: str = ""
    voice: str | None = None
    pitch: int | None = None
    speed: int | None = None
    video_speed: int | None = None
    mode: str = "single"
    ken_burns: bool = False


async def _read_upload_capped(
    file: UploadFile, max_bytes: int | None = None
) -> bytes:
    limit = library_mod.MAX_UPLOAD_BYTES if max_bytes is None else max_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValueError(
                f"Upload exceeds maximum size of {limit} bytes"
            )
        chunks.append(chunk)
    return b"".join(chunks)


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
    app.include_router(api_v1_router)

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
        videos = list_videos(settings)
        try:
            voices = await list_english_voices()
        except Exception:
            voices = [VoiceInfo(DEFAULT_VOICE, "en-US", "Female")]
        return templates.TemplateResponse(
            request,
            "generate.html",
            {
                "sources": sources,
                "videos": videos,
                "has_videos": bool(videos),
                "voices": voices,
                "default_voice": DEFAULT_VOICE,
                "recent_outputs": list_outputs(settings),
                "images": list_images(settings),
            },
        )

    @app.get("/library", response_class=HTMLResponse)
    def library_page(
        request: Request,
        tab: str = "slices",
        _: None = Depends(require_login),
    ) -> HTMLResponse:
        settings = request.app.state.settings
        if tab not in {"slices", "videos", "images"}:
            tab = "slices"
        return templates.TemplateResponse(
            request,
            "library.html",
            _library_ctx(settings, tab=tab),
        )

    @app.post("/library/upload", response_model=None)
    async def library_upload(
        request: Request,
        file: UploadFile = File(...),
        _: None = Depends(require_login),
    ) -> Response:
        settings = request.app.state.settings
        filename = file.filename or ""
        try:
            data = await _read_upload_capped(file)
            slices = save_upload(settings, filename, data)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "library.html",
                _library_ctx(settings, error=str(exc), tab="slices"),
                status_code=400,
            )
        names = ", ".join(s.name for s in slices)
        return templates.TemplateResponse(
            request,
            "library.html",
            _library_ctx(
                settings,
                message=(
                    f"Created {len(slices)} one-minute slice(s): {names}. "
                    "A leftover under 1 minute was discarded if present."
                ),
                tab="slices",
            ),
        )

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
                _library_ctx(settings, error=str(exc), tab="slices"),
                status_code=400,
            )
        return RedirectResponse("/library", status_code=HTTP_303_SEE_OTHER)

    @app.post("/library/videos/upload", response_model=None)
    async def library_video_upload(
        request: Request,
        files: list[UploadFile] = File(...),
        _: None = Depends(require_login),
    ) -> Response:
        settings = request.app.state.settings
        if not files:
            return templates.TemplateResponse(
                request,
                "library.html",
                _library_ctx(
                    settings,
                    error="Select at least one video file",
                    tab="videos",
                ),
                status_code=400,
            )
        saved_names: list[str] = []
        errors: list[str] = []
        for file in files:
            name = file.filename or ""
            if not name:
                continue
            try:
                data = await _read_upload_capped(file)
                saved = save_video(settings, name, data)
                saved_names.append(saved.name)
            except (ValueError, FileNotFoundError) as exc:
                errors.append(f"{name}: {exc}")
        if not saved_names:
            detail = "; ".join(errors) if errors else "No video files uploaded"
            return templates.TemplateResponse(
                request,
                "library.html",
                _library_ctx(settings, error=detail, tab="videos"),
                status_code=400,
            )
        message = (
            f"Uploaded {len(saved_names)} video(s): {', '.join(saved_names)}."
        )
        if errors:
            message += f" Some failed: {'; '.join(errors)}."
        return templates.TemplateResponse(
            request,
            "library.html",
            _library_ctx(settings, message=message, tab="videos"),
        )

    @app.post("/library/videos/delete", response_model=None)
    def library_video_delete(
        request: Request,
        name: str = Form(...),
        _: None = Depends(require_login),
    ) -> Response:
        settings = request.app.state.settings
        try:
            delete_video(settings, name)
        except (ValueError, FileNotFoundError) as exc:
            return templates.TemplateResponse(
                request,
                "library.html",
                _library_ctx(settings, error=str(exc), tab="videos"),
                status_code=400,
            )
        return templates.TemplateResponse(
            request,
            "library.html",
            _library_ctx(
                settings,
                message=f"Deleted video: {name}.",
                tab="videos",
            ),
        )

    @app.get("/prompt", response_class=HTMLResponse)
    def prompt_page(
        request: Request,
        _: None = Depends(require_login),
    ) -> HTMLResponse:
        settings = request.app.state.settings
        return templates.TemplateResponse(
            request,
            "prompt.html",
            {
                "prompt": load_prompt(settings),
                "error": None,
                "message": None,
            },
        )

    @app.post("/prompt", response_model=None)
    async def prompt_save(
        request: Request,
        prompt: str = Form(...),
        _: None = Depends(require_login),
    ) -> Response:
        settings = request.app.state.settings
        try:
            save_prompt(settings, prompt)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "prompt.html",
                {
                    "prompt": prompt,
                    "error": str(exc),
                    "message": None,
                },
                status_code=400,
            )
        return templates.TemplateResponse(
            request,
            "prompt.html",
            {
                "prompt": load_prompt(settings),
                "error": None,
                "message": "Prompt saved.",
            },
        )

    @app.post("/api/generate-story")
    async def api_generate_story(
        request: Request,
        _: None = Depends(require_login),
    ) -> dict:
        settings = request.app.state.settings
        if not settings.gemini_api_key.strip():
            raise HTTPException(
                status_code=503,
                detail="GEMINI_API_KEY is not configured",
            )
        prompt = load_prompt(settings).strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        try:
            story = await generate_story(settings.gemini_api_key, prompt)
        except ValueError as exc:
            msg = str(exc)
            status = 503 if "GEMINI_API_KEY" in msg else 400
            raise HTTPException(status_code=status, detail=msg) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"story": story}

    @app.post("/api/jobs")
    async def create_job(
        request: Request,
        background_tasks: BackgroundTasks,
        _: None = Depends(require_login),
    ) -> dict:
        settings = request.app.state.settings
        mgr: JobManager = request.app.state.job_manager
        try:
            raw = await request.body()
            body = CreateJobBody.model_validate_json(raw)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=400, detail="Invalid JSON body"
            ) from exc
        source_name = body.source_name
        story = body.story
        voice = body.voice or DEFAULT_VOICE
        pitch = DEFAULT_PITCH if body.pitch is None else body.pitch
        speed = DEFAULT_SPEED if body.speed is None else body.speed
        video_speed = (
            DEFAULT_VIDEO_SPEED if body.video_speed is None else body.video_speed
        )
        try:
            format_edge_pitch(pitch)
            format_edge_rate(speed)
            validate_video_speed(video_speed)
            mode = normalize_mode(body.mode)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            record = mgr.create(
                settings,
                source_name,
                story,
                voice,
                pitch=pitch,
                speed=speed,
                video_speed=video_speed,
                mode=mode,
                ken_burns=body.ken_burns,
            )
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
        settings = request.app.state.settings
        mgr: JobManager = request.app.state.job_manager
        record = mgr.get(job_id, settings)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return asdict(record)

    @app.post("/api/images")
    async def upload_image(
        request: Request,
        file: UploadFile = File(...),
        _: None = Depends(require_login),
    ) -> dict:
        settings = request.app.state.settings
        filename = file.filename or ""
        try:
            data = await _read_upload_capped(
                file, library_mod.MAX_IMAGE_UPLOAD_BYTES
            )
            saved = save_image(settings, filename, data)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"name": saved.name}

    @app.delete("/api/images/{name}")
    def remove_image(
        name: str,
        request: Request,
        _: None = Depends(require_login),
    ) -> dict:
        settings = request.app.state.settings
        try:
            delete_image(settings, name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

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
        if not path.is_relative_to(settings.outputs_dir.resolve()):
            raise HTTPException(status_code=400, detail="Invalid path")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path, media_type="video/mp4", filename=safe)

    def _library_media_response(resolve, settings: Settings, name: str) -> FileResponse:
        try:
            path = resolve(settings, name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(
            path,
            media_type=media_type_for_name(path.name),
            filename=path.name,
        )

    @app.get("/media/sources/{name}")
    def media_source(
        name: str,
        request: Request,
        _: None = Depends(require_login),
    ) -> FileResponse:
        return _library_media_response(
            resolve_source, request.app.state.settings, name
        )

    @app.get("/media/videos/{name}")
    def media_video(
        name: str,
        request: Request,
        _: None = Depends(require_login),
    ) -> FileResponse:
        return _library_media_response(
            resolve_video, request.app.state.settings, name
        )

    @app.get("/media/images/{name}")
    def media_image(
        name: str,
        request: Request,
        _: None = Depends(require_login),
    ) -> FileResponse:
        return _library_media_response(
            resolve_image, request.app.state.settings, name
        )

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_app, factory=True, host="0.0.0.0", port=8000, reload=False)
