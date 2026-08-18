from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse

from roblox_viral.voice import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_VIDEO_SPEED,
    format_edge_pitch,
    format_edge_rate,
    validate_video_speed,
)
from roblox_viral.web import library as library_mod
from roblox_viral.web.auth import require_api_key
from roblox_viral.web.jobs import BusyError, JobManager
from roblox_viral.web.voices import DEFAULT_VOICE

router = APIRouter(prefix="/api/v1", tags=["v1"])


def _mode_from_type(video_type: str) -> str:
    t = (video_type or "").strip().lower()
    if t == "single":
        return "single"
    if t == "reddit":
        return "reddit"
    if t == "leni":
        return "picture"
    if t == "roblox":
        raise ValueError("type 'roblox' is removed; use 'single'")
    raise ValueError("type must be 'single', 'reddit', or 'leni'")


def _optional_int(raw: str | None, default: int, label: str) -> int:
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be an int") from exc


@router.post("/videos")
async def create_video(
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
    voice: str = Form(""),
    story: str = Form(""),
    type: str = Form(""),
    source_name: str = Form(""),
    pitch: str = Form(""),
    speed: str = Form(""),
    video_speed: str = Form(""),
    media: UploadFile | None = File(None),
) -> dict:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    try:
        mode = _mode_from_type(type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    has_media = media is not None and bool(getattr(media, "filename", None))
    name = (source_name or "").strip()
    if mode == "reddit":
        if has_media or name:
            raise HTTPException(
                status_code=400,
                detail="reddit type does not accept media or source_name",
            )
    elif has_media and name:
        raise HTTPException(
            status_code=400,
            detail="Provide either media file or source_name, not both",
        )
    elif not has_media and not name:
        raise HTTPException(
            status_code=400,
            detail="Provide media file or source_name",
        )

    voice_s = (voice or "").strip() or DEFAULT_VOICE
    try:
        pitch_i = _optional_int(pitch, DEFAULT_PITCH, "pitch")
        speed_i = _optional_int(speed, DEFAULT_SPEED, "speed")
        video_speed_i = _optional_int(
            video_speed, DEFAULT_VIDEO_SPEED, "video_speed"
        )
        format_edge_pitch(pitch_i)
        format_edge_rate(speed_i)
        validate_video_speed(video_speed_i)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ephemeral = False
    input_bytes: bytes | None = None
    stored_name = "" if mode == "reddit" else name

    if has_media:
        assert media is not None
        raw_name = Path(media.filename or "upload.bin").name
        data = await media.read()
        try:
            if mode == "picture":
                if len(data) > library_mod.MAX_IMAGE_UPLOAD_BYTES:
                    raise ValueError(
                        f"Upload exceeds maximum size of "
                        f"{library_mod.MAX_IMAGE_UPLOAD_BYTES} bytes"
                    )
                stored_name = library_mod.validate_image_filename(raw_name)
            else:
                if len(data) > library_mod.MAX_UPLOAD_BYTES:
                    raise ValueError(
                        f"Upload exceeds maximum size of "
                        f"{library_mod.MAX_UPLOAD_BYTES} bytes"
                    )
                stored_name = library_mod.validate_video_filename(raw_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        suffix = Path(stored_name).suffix.lower()
        stored_name = f"input{suffix}"
        ephemeral = True
        input_bytes = data

    try:
        record = mgr.create(
            settings,
            stored_name,
            story,
            voice_s,
            pitch=pitch_i,
            speed=speed_i,
            video_speed=video_speed_i,
            mode=mode,
            ken_burns=False,
            ephemeral=ephemeral,
        )
    except BusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if input_bytes is not None:
        dest = settings.jobs_dir / record.id / record.source_name
        dest.write_bytes(input_bytes)

    background_tasks.add_task(mgr.run_job, settings, record.id)
    return {"id": record.id}


@router.get("/videos/{video_id}")
def get_video(
    video_id: str,
    request: Request,
    _: None = Depends(require_api_key),
) -> dict:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    record = mgr.get(video_id, settings)
    if record is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return asdict(record)


@router.get("/videos/{video_id}/download")
def download_video(
    video_id: str,
    request: Request,
    _: None = Depends(require_api_key),
) -> FileResponse:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    record = mgr.get(video_id, settings)
    if record is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if record.status == "error":
        raise HTTPException(
            status_code=422, detail=record.error or "Render failed"
        )
    if record.status != "done" or not record.output_name:
        raise HTTPException(status_code=409, detail="Video not ready")
    safe = Path(record.output_name).name
    if safe != record.output_name:
        raise HTTPException(status_code=400, detail="Invalid output name")
    path = (settings.outputs_dir / safe).resolve()
    if not path.is_relative_to(settings.outputs_dir.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Output file missing")
    return FileResponse(path, media_type="video/mp4", filename=safe)


@router.get("/videos/{video_id}/cover")
def download_cover(
    video_id: str,
    request: Request,
    _: None = Depends(require_api_key),
) -> FileResponse:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    record = mgr.get(video_id, settings)
    if record is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if record.status == "error":
        raise HTTPException(
            status_code=422, detail=record.error or "Render failed"
        )
    if record.status != "done":
        raise HTTPException(status_code=409, detail="Video not ready")
    name = record.title_card_name
    if not name:
        raise HTTPException(status_code=404, detail="Cover not found")
    safe = Path(name).name
    if safe != name:
        raise HTTPException(status_code=400, detail="Invalid cover name")
    path = (settings.outputs_dir / safe).resolve()
    if not path.is_relative_to(settings.outputs_dir.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Cover file missing")
    return FileResponse(path, media_type="image/png", filename=safe)
