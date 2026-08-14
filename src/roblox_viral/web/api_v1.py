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

from roblox_viral.voice import DEFAULT_PITCH, DEFAULT_SPEED
from roblox_viral.web import library as library_mod
from roblox_viral.web.auth import require_api_key
from roblox_viral.web.jobs import BusyError, JobManager
from roblox_viral.web.voices import DEFAULT_VOICE

router = APIRouter(prefix="/api/v1", tags=["v1"])


def _mode_from_type(video_type: str) -> str:
    t = (video_type or "").strip().lower()
    if t == "roblox":
        return "roblox"
    if t == "leni":
        return "picture"
    raise ValueError("type must be 'roblox' or 'leni'")


@router.post("/videos")
async def create_video(
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
    voice: str = Form(""),
    story: str = Form(""),
    type: str = Form(""),
    source_name: str = Form(""),
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
    if has_media and name:
        raise HTTPException(
            status_code=400,
            detail="Provide either media file or source_name, not both",
        )
    if not has_media and not name:
        raise HTTPException(
            status_code=400,
            detail="Provide media file or source_name",
        )

    voice_s = (voice or "").strip() or DEFAULT_VOICE
    ephemeral = False
    input_bytes: bytes | None = None
    stored_name = name

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
            pitch=DEFAULT_PITCH,
            speed=DEFAULT_SPEED,
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
