from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from roblox_viral.voice import DEFAULT_PITCH, DEFAULT_SPEED
from roblox_viral.web.auth import require_api_key
from roblox_viral.web.jobs import BusyError, JobManager
from roblox_viral.web.voices import DEFAULT_VOICE

router = APIRouter(prefix="/api/v1", tags=["v1"])


class CreateVideoBody(BaseModel):
    voice: str = ""
    story: str = ""
    type: str = ""
    source_name: str = ""


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
    body: CreateVideoBody,
    _: None = Depends(require_api_key),
) -> dict:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    try:
        mode = _mode_from_type(body.type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    voice = (body.voice or "").strip() or DEFAULT_VOICE
    try:
        record = mgr.create(
            settings,
            body.source_name,
            body.story,
            voice,
            pitch=DEFAULT_PITCH,
            speed=DEFAULT_SPEED,
            mode=mode,
            ken_burns=False,
        )
    except BusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
