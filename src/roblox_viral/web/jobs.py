from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from roblox_viral.captions import write_ass
from roblox_viral.render import render_video
from roblox_viral.story import join_for_tts, split_sentences
from roblox_viral.voice import EdgeTTSProvider
from roblox_viral.web.config import Settings
from roblox_viral.web.library import resolve_source

JobStatus = Literal["queued", "synthesizing", "captioning", "rendering", "done", "error"]


class BusyError(Exception):
    """Raised when a job is already active (single-flight)."""


@dataclass
class JobRecord:
    id: str
    status: JobStatus
    error: str | None
    source_name: str
    voice: str
    output_name: str | None
    created_at: str


class JobManager:
    """In-memory job store with single-flight pipeline execution."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_id: str | None = None
        self._jobs: dict[str, JobRecord] = {}
        self._stories: dict[str, str] = {}

    def create(
        self, settings: Settings, source_name: str, story: str, voice: str
    ) -> JobRecord:
        resolve_source(settings, source_name)
        sentences = split_sentences(story)
        if not sentences:
            raise ValueError("Story is empty")

        with self._lock:
            if self._active_id is not None:
                raise BusyError("A render job is already in progress")
            job_id = uuid.uuid4().hex
            record = JobRecord(
                id=job_id,
                status="queued",
                error=None,
                source_name=source_name,
                voice=voice,
                output_name=None,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._jobs[job_id] = record
            self._stories[job_id] = story
            self._active_id = job_id

        job_dir = settings.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        self._persist(settings, record)
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def run_job(self, settings: Settings, job_id: str) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            raise KeyError(f"Unknown job: {job_id}")

        try:
            story = self._stories[job_id]
            sentences = split_sentences(story)
            if not sentences:
                raise ValueError("Story is empty")

            video_path = resolve_source(settings, record.source_name)
            job_dir = settings.jobs_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            narration_path = job_dir / "narration.mp3"
            ass_path = job_dir / "captions.ass"
            output_name = f"{job_id}.mp4"
            output_path = settings.outputs_dir / output_name

            self._set_status(settings, record, "synthesizing")
            words = EdgeTTSProvider(record.voice).synthesize(
                join_for_tts(sentences), narration_path
            )

            self._set_status(settings, record, "captioning")
            write_ass(words, ass_path, sentences=sentences)

            self._set_status(settings, record, "rendering")
            render_video(
                video_path=video_path,
                audio_path=narration_path,
                ass_path=ass_path,
                output_path=output_path,
                work_dir=job_dir,
            )

            record.output_name = output_name
            self._set_status(settings, record, "done")
        except Exception as exc:
            record.error = str(exc)
            self._set_status(settings, record, "error")
        finally:
            with self._lock:
                if self._active_id == job_id:
                    self._active_id = None

    def _set_status(
        self, settings: Settings, record: JobRecord, status: JobStatus
    ) -> None:
        record.status = status
        self._persist(settings, record)

    def _persist(self, settings: Settings, record: JobRecord) -> None:
        path = settings.jobs_dir / record.id / "status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")
