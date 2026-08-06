from pathlib import Path

import pytest

from roblox_viral.render import RenderError, render_video


def _touch(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_render_video_without_overlay_uses_vf(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    out = tmp_path / "out.mp4"
    seen = {}

    def fake_probe(_path):
        return 2.0

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", fake_probe)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    render_video(
        video_path=video,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
    )
    cmd = seen["cmd"]
    assert "-filter_complex" not in cmd
    assert "-vf" in cmd
    assert str(video) in cmd
    assert str(audio) in cmd


def test_render_video_with_overlay_uses_filter_complex(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    overlay = _touch(tmp_path / "overlay.mp4")
    out = tmp_path / "out.mp4"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 5.0)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    render_video(
        video_path=video,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        overlay_path=overlay,
    )
    cmd = " ".join(seen["cmd"])
    assert "-filter_complex" in seen["cmd"]
    assert "chromakey" in cmd
    assert "overlay=" in cmd
    assert "eof_action=pass" in cmd
    assert str(overlay) in seen["cmd"]
    idx = seen["cmd"].index(str(overlay))
    assert seen["cmd"][idx - 2 : idx] in (["-t", "3.5"], ["-t", "3.500"])
    assert "-map" in seen["cmd"]
    assert "[outv]" in seen["cmd"]
    assert "1:a:0" in seen["cmd"]


def test_render_video_missing_overlay_path_raises(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    out = tmp_path / "out.mp4"
    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 1.0)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
    with pytest.raises(RenderError, match="Overlay"):
        render_video(
            video_path=video,
            audio_path=audio,
            ass_path=ass,
            output_path=out,
            overlay_path=tmp_path / "missing.mp4",
        )
