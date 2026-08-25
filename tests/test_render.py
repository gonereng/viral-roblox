from pathlib import Path

import pytest

from roblox_viral.reddit_clips import ClipSegment
from roblox_viral.render import (
    RenderError,
    _playback_setpts,
    build_atempo_filters,
    build_reddit_background,
    render_still,
    render_video,
    tempo_finished_video,
)


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


def test_render_video_title_card_overlay_enable(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    card = _touch(tmp_path / "card.png")
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
        title_card_path=card,
        title_card_until_s=1.25,
        overlay_path=None,
    )

    cmd = seen["cmd"]
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "[0:v]scale=1080:1920:force_original_aspect_ratio=increase" in fc
    assert "[base]ass=" in fc
    assert "[cap][2:v]overlay=(W-w)/2:(H/2-h):enable='lte(t,1.250)'[outv]" in fc
    assert cmd[cmd.index(str(card)) - 1] == "-i"
    assert cmd.index(str(card)) > cmd.index(str(audio))
    assert cmd[cmd.index("-map") + 1] == "[outv]"
    assert "1:a:0" in cmd


@pytest.mark.parametrize("until_s", [None, 0, -0.1])
def test_render_video_title_card_requires_positive_duration(
    tmp_path, monkeypatch, until_s
):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    card = _touch(tmp_path / "card.png")
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    with pytest.raises(RenderError, match="title_card_until_s"):
        render_video(
            video_path=video,
            audio_path=audio,
            ass_path=ass,
            output_path=tmp_path / "out.mp4",
            title_card_path=card,
            title_card_until_s=until_s,
        )


def test_render_video_missing_title_card_path_raises(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    with pytest.raises(RenderError, match="Title card"):
        render_video(
            video_path=video,
            audio_path=audio,
            ass_path=ass,
            output_path=tmp_path / "out.mp4",
            title_card_path=tmp_path / "missing.png",
            title_card_until_s=1,
        )


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


def test_playback_setpts_reddit_mode_accepts_500():
    assert _playback_setpts(500, mode="reddit") == "setpts=100/500*PTS"


def test_playback_setpts_single_mode_rejects_500():
    with pytest.raises(ValueError, match="video_speed must be between"):
        _playback_setpts(500, mode="single")


def test_render_video_reddit_speed_500_inserts_setpts(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
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
    render_video(
        video_path=video,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        video_speed=500,
        mode="reddit",
    )
    vf = seen["cmd"][seen["cmd"].index("-vf") + 1]
    assert "setpts=100/500*PTS" in vf


def test_render_video_default_speed_omits_setpts(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
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
    render_video(
        video_path=video, audio_path=audio, ass_path=ass, output_path=out
    )
    vf = seen["cmd"][seen["cmd"].index("-vf") + 1]
    assert "setpts" not in vf


def test_render_video_speed_200_inserts_setpts(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
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
    render_video(
        video_path=video,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        video_speed=200,
    )
    vf = seen["cmd"][seen["cmd"].index("-vf") + 1]
    assert "setpts=100/200*PTS" in vf


def test_render_video_overlay_includes_setpts_on_base(tmp_path, monkeypatch):
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
        video_speed=150,
    )
    fc = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
    assert "setpts=100/150*PTS" in fc
    assert "lte(t,3.5)" in fc


def test_render_video_overlay_fits_full_frame(tmp_path, monkeypatch):
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
    fc = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
    assert f"scale=1080:1920:force_original_aspect_ratio=decrease" in fc
    assert "scale=-2:" not in fc
    assert "lte(t,3.5)" in fc


def test_build_reddit_background_concats_trimmed_segments(tmp_path, monkeypatch):
    first = _touch(tmp_path / "first.mp4")
    second = _touch(tmp_path / "second.mp4")
    out = tmp_path / "nested" / "background.mp4"
    work_dir = tmp_path / "work"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    result = build_reddit_background(
        [
            ClipSegment(path=first, start_s=1.25, duration_s=2.5),
            ClipSegment(path=second, start_s=0.0, duration_s=3.75),
        ],
        out,
        work_dir=work_dir,
    )

    assert result == out
    assert out.is_file()
    assert work_dir.is_dir()
    cmd = seen["cmd"]
    assert cmd.count("-i") == 2
    assert str(first) in cmd
    assert str(second) in cmd
    assert cmd[cmd.index(str(first)) - 5 : cmd.index(str(first))] == [
        "-ss",
        "1.250",
        "-t",
        "2.500",
        "-i",
    ]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    normalize = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS"
    )
    assert f"[0:v]{normalize}[v0]" in filter_complex
    assert f"[1:v]{normalize}[v1]" in filter_complex
    assert "[v0][v1]concat=n=2:v=1:a=0[outv]" in filter_complex
    assert cmd[cmd.index("-map") + 1] == "[outv]"
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-an" in cmd


def test_build_atempo_filters_100_empty():
    assert build_atempo_filters(100) == []


def test_build_atempo_filters_200_single():
    assert build_atempo_filters(200) == ["atempo=2.0"]


def test_build_atempo_filters_50_single():
    assert build_atempo_filters(50) == ["atempo=0.5"]


def test_build_atempo_filters_500_chained():
    # 5.0 = 2.0 * 2.0 * 1.25
    assert build_atempo_filters(500) == ["atempo=2.0", "atempo=2.0", "atempo=1.25"]


def test_build_atempo_filters_150():
    assert build_atempo_filters(150) == ["atempo=1.5"]


def test_tempo_finished_video_100_copies_without_ffmpeg(tmp_path, monkeypatch):
    src = _touch(tmp_path / "in.mp4", b"one-x")
    out = tmp_path / "out.mp4"

    def boom(*a, **k):
        raise AssertionError("ffmpeg must not run at 100%")

    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", boom)
    monkeypatch.setattr("roblox_viral.render.subprocess.run", boom)

    result = tempo_finished_video(
        input_path=src, output_path=out, video_speed=100, mode="single"
    )
    assert result == out
    assert out.read_bytes() == b"one-x"


def test_tempo_finished_video_200_uses_setpts_and_atempo(tmp_path, monkeypatch):
    src = _touch(tmp_path / "in.mp4", b"one-x")
    out = tmp_path / "out.mp4"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"sped")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    tempo_finished_video(
        input_path=src, output_path=out, video_speed=200, mode="single"
    )
    cmd = seen["cmd"]
    assert cmd[0] == "ffmpeg"
    assert "-filter_complex" in cmd
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "setpts=100/200*PTS" in fc
    assert "atempo=2.0" in fc
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    assert str(out) == cmd[-1]
    assert out.read_bytes() == b"sped"


def test_tempo_finished_video_reddit_500(tmp_path, monkeypatch):
    src = _touch(tmp_path / "in.mp4", b"x")
    out = tmp_path / "out.mp4"
    seen = {}
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"ok")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)
    tempo_finished_video(
        input_path=src, output_path=out, video_speed=500, mode="reddit"
    )
    fc = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
    assert "setpts=100/500*PTS" in fc
    assert fc.count("atempo=") == 3


def test_tempo_finished_video_rejects_bad_speed(tmp_path):
    src = _touch(tmp_path / "in.mp4", b"x")
    with pytest.raises(ValueError, match="video_speed"):
        tempo_finished_video(
            input_path=src,
            output_path=tmp_path / "out.mp4",
            video_speed=10,
            mode="single",
        )


def test_tempo_finished_video_ffmpeg_failure_raises(tmp_path, monkeypatch):
    src = _touch(tmp_path / "in.mp4", b"x")
    out = tmp_path / "out.mp4"
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        class R:
            returncode = 1
            stderr = "boom"

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)
    with pytest.raises(RenderError, match="tempo"):
        tempo_finished_video(
            input_path=src, output_path=out, video_speed=150, mode="single"
        )


def test_build_reddit_background_raises_render_error_on_ffmpeg_failure(
    tmp_path, monkeypatch
):
    source = _touch(tmp_path / "source.mp4")
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        class R:
            returncode = 1
            stderr = "concat exploded"

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    with pytest.raises(RenderError, match="concat exploded"):
        build_reddit_background(
            [ClipSegment(path=source, start_s=0.0, duration_s=1.0)],
            tmp_path / "out.mp4",
        )
