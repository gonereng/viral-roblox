from pathlib import Path

import pytest

from roblox_viral.render import RenderError, render_still, render_video


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
    assert seen["cmd"][idx - 1] == "-i"
    assert seen["cmd"][idx - 3 : idx - 1] in (["-t", "3.5"], ["-t", "3.500"])
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


def test_render_still_static_loops_image_no_overlay(tmp_path, monkeypatch):
    image = _touch(tmp_path / "still.jpg")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    out = tmp_path / "out.mp4"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 2.5)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    render_still(
        image_path=image,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        ken_burns=False,
    )
    cmd = seen["cmd"]
    assert cmd.count("-i") == 2
    assert "-loop" in cmd
    assert cmd[cmd.index("-loop") + 1] == "1"
    assert "-framerate" in cmd
    assert str(image) in cmd
    assert str(audio) in cmd
    assert "-vf" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in vf
    assert "crop=1080:1920" in vf
    assert "ass='" in vf
    assert "zoompan" not in vf
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert "-filter_complex" not in cmd
    assert "chromakey" not in " ".join(cmd)
    assert "0:v:0" in cmd
    assert "1:a:0" in cmd
    assert "-t" in cmd


def test_render_still_ken_burns_uses_zoompan(tmp_path, monkeypatch):
    image = _touch(tmp_path / "still.png")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    out = tmp_path / "out.mp4"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 2.0)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    render_still(
        image_path=image,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        ken_burns=True,
    )
    cmd = seen["cmd"]
    vf = cmd[cmd.index("-vf") + 1]
    assert "zoompan" in vf
    assert "1.20" in vf or "1.2" in vf
    assert "s=1080x1920" in vf
    assert "fps=30" in vf
    assert "crop=1296:2304" in vf
    assert "ass='" in vf
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert cmd.count("-i") == 2


def test_render_still_missing_image_raises(tmp_path, monkeypatch):
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 1.0)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
    with pytest.raises(RenderError, match="Image"):
        render_still(
            image_path=tmp_path / "missing.jpg",
            audio_path=audio,
            ass_path=ass,
            output_path=tmp_path / "out.mp4",
        )
