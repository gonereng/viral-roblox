# Review package Task 1
BASE: d4976a12c614f7fa14effb9da198aef0caa1f4dc
HEAD: 7d3137f420b40a9bb253b2140f154d2ffa6c0e42

## Commits

7d3137f feat(render): tempo finished MP4 for Gemini video_speed

## Diff stat

 src/roblox_viral/render.py |  86 ++++++++++++++++++++++++++++++
 tests/test_render.py       | 129 +++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 215 insertions(+)

## Full diff

diff --git a/src/roblox_viral/render.py b/src/roblox_viral/render.py
index c8eebba..2a733f2 100644
--- a/src/roblox_viral/render.py
+++ b/src/roblox_viral/render.py
@@ -153,20 +153,106 @@ def _ass_filter_path(ass_path: Path) -> str:
     return p
 
 
 def _playback_setpts(video_speed: int, *, mode: str = "single") -> str | None:
     validate_video_speed(video_speed, mode=mode)
     if video_speed == 100:
         return None
     return f"setpts=100/{video_speed}*PTS"
 
 
+def build_atempo_filters(speed_percent: int) -> list[str]:
+    """Split playback factor into ffmpeg atempo values in [0.5, 2.0]."""
+    if not isinstance(speed_percent, int) or isinstance(speed_percent, bool):
+        raise ValueError("video_speed must be an int")
+    if speed_percent <= 0:
+        raise ValueError("video_speed must be positive")
+    factor = speed_percent / 100.0
+    if abs(factor - 1.0) < 1e-9:
+        return []
+    filters: list[str] = []
+    remaining = factor
+    while remaining > 2.0 + 1e-9:
+        filters.append("atempo=2.0")
+        remaining /= 2.0
+    while remaining < 0.5 - 1e-9:
+        filters.append("atempo=0.5")
+        remaining /= 0.5
+    # remaining now in [0.5, 2.0]
+    if abs(remaining - 1.0) > 1e-9:
+        if abs(remaining - 2.0) < 1e-9:
+            filters.append("atempo=2.0")
+        else:
+            filters.append(f"atempo={remaining:.10g}")
+    return filters
+
+
+def tempo_finished_video(
+    *,
+    input_path: Path | str,
+    output_path: Path | str,
+    video_speed: int,
+    mode: str = "single",
+) -> Path:
+    """Speed up/slow down a finished vertical MP4 (video + audio, pitch preserved)."""
+    validate_video_speed(video_speed, mode=mode)
+    src = Path(input_path)
+    out = Path(output_path)
+    if not src.is_file():
+        raise RenderError(f"Video not found: {src}")
+
+    if video_speed == 100:
+        if src.resolve() != out.resolve():
+            out.parent.mkdir(parents=True, exist_ok=True)
+            shutil.copyfile(src, out)
+        return out
+
+    ffmpeg = require_ffmpeg()
+    out.parent.mkdir(parents=True, exist_ok=True)
+    setpts = f"setpts=100/{video_speed}*PTS"
+    atempo = build_atempo_filters(video_speed)
+    audio_chain = ",".join(atempo) if atempo else "anull"
+    filter_complex = f"[0:v]{setpts}[v];[0:a]{audio_chain}[a]"
+    cmd = [
+        ffmpeg,
+        "-y",
+        "-i",
+        str(src),
+        "-filter_complex",
+        filter_complex,
+        "-map",
+        "[v]",
+        "-map",
+        "[a]",
+        "-c:v",
+        "libx264",
+        "-preset",
+        "medium",
+        "-crf",
+        "18",
+        "-c:a",
+        "aac",
+        "-b:a",
+        "192k",
+        "-movflags",
+        "+faststart",
+        str(out),
+    ]
+    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
+    if result.returncode != 0:
+        raise RenderError(
+            "ffmpeg tempo finished video failed:\n"
+            + (result.stderr or result.stdout or "")
+        )
+    return out
+
+
 def render_video(
     *,
     video_path: Path | str,
     audio_path: Path | str,
     ass_path: Path | str,
     output_path: Path | str,
     keep_temp: bool = False,
     work_dir: Path | str | None = None,
     overlay_path: Path | str | None = None,
     video_speed: int = 100,
diff --git a/tests/test_render.py b/tests/test_render.py
index ef58862..80640a0 100644
--- a/tests/test_render.py
+++ b/tests/test_render.py
@@ -1,21 +1,23 @@
 from pathlib import Path
 
 import pytest
 
 from roblox_viral.reddit_clips import ClipSegment
 from roblox_viral.render import (
     RenderError,
     _playback_setpts,
+    build_atempo_filters,
     build_reddit_background,
     render_still,
     render_video,
+    tempo_finished_video,
 )
 
 
 def _touch(path: Path, data: bytes = b"x") -> Path:
     path.parent.mkdir(parents=True, exist_ok=True)
     path.write_bytes(data)
     return path
 
 
 def test_render_video_without_overlay_uses_vf(tmp_path, monkeypatch):
@@ -526,20 +528,147 @@ def test_build_reddit_background_concats_trimmed_segments(tmp_path, monkeypatch)
         "crop=1080:1920,setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS"
     )
     assert f"[0:v]{normalize}[v0]" in filter_complex
     assert f"[1:v]{normalize}[v1]" in filter_complex
     assert "[v0][v1]concat=n=2:v=1:a=0[outv]" in filter_complex
     assert cmd[cmd.index("-map") + 1] == "[outv]"
     assert cmd[cmd.index("-c:v") + 1] == "libx264"
     assert "-an" in cmd
 
 
+def test_build_atempo_filters_100_empty():
+    assert build_atempo_filters(100) == []
+
+
+def test_build_atempo_filters_200_single():
+    assert build_atempo_filters(200) == ["atempo=2.0"]
+
+
+def test_build_atempo_filters_50_single():
+    assert build_atempo_filters(50) == ["atempo=0.5"]
+
+
+def test_build_atempo_filters_500_chained():
+    # 5.0 = 2.0 * 2.0 * 1.25
+    assert build_atempo_filters(500) == ["atempo=2.0", "atempo=2.0", "atempo=1.25"]
+
+
+def test_build_atempo_filters_150():
+    assert build_atempo_filters(150) == ["atempo=1.5"]
+
+
+def test_tempo_finished_video_100_copies_without_ffmpeg(tmp_path, monkeypatch):
+    src = _touch(tmp_path / "in.mp4", b"one-x")
+    out = tmp_path / "out.mp4"
+
+    def boom(*a, **k):
+        raise AssertionError("ffmpeg must not run at 100%")
+
+    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", boom)
+    monkeypatch.setattr("roblox_viral.render.subprocess.run", boom)
+
+    result = tempo_finished_video(
+        input_path=src, output_path=out, video_speed=100, mode="single"
+    )
+    assert result == out
+    assert out.read_bytes() == b"one-x"
+
+
+def test_tempo_finished_video_200_uses_setpts_and_atempo(tmp_path, monkeypatch):
+    src = _touch(tmp_path / "in.mp4", b"one-x")
+    out = tmp_path / "out.mp4"
+    seen = {}
+
+    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
+
+    def fake_run(cmd, check=False, capture_output=True, text=True):
+        seen["cmd"] = cmd
+        out.write_bytes(b"sped")
+
+        class R:
+            returncode = 0
+            stderr = ""
+
+        return R()
+
+    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)
+
+    tempo_finished_video(
+        input_path=src, output_path=out, video_speed=200, mode="single"
+    )
+    cmd = seen["cmd"]
+    assert cmd[0] == "ffmpeg"
+    assert "-filter_complex" in cmd
+    fc = cmd[cmd.index("-filter_complex") + 1]
+    assert "setpts=100/200*PTS" in fc
+    assert "atempo=2.0" in fc
+    assert "-c:v" in cmd and "libx264" in cmd
+    assert "-c:a" in cmd and "aac" in cmd
+    assert str(out) == cmd[-1]
+    assert out.read_bytes() == b"sped"
+
+
+def test_tempo_finished_video_reddit_500(tmp_path, monkeypatch):
+    src = _touch(tmp_path / "in.mp4", b"x")
+    out = tmp_path / "out.mp4"
+    seen = {}
+    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
+
+    def fake_run(cmd, check=False, capture_output=True, text=True):
+        seen["cmd"] = cmd
+        out.write_bytes(b"ok")
+
+        class R:
+            returncode = 0
+            stderr = ""
+
+        return R()
+
+    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)
+    tempo_finished_video(
+        input_path=src, output_path=out, video_speed=500, mode="reddit"
+    )
+    fc = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
+    assert "setpts=100/500*PTS" in fc
+    assert fc.count("atempo=") == 3
+
+
+def test_tempo_finished_video_rejects_bad_speed(tmp_path):
+    src = _touch(tmp_path / "in.mp4", b"x")
+    with pytest.raises(ValueError, match="video_speed"):
+        tempo_finished_video(
+            input_path=src,
+            output_path=tmp_path / "out.mp4",
+            video_speed=10,
+            mode="single",
+        )
+
+
+def test_tempo_finished_video_ffmpeg_failure_raises(tmp_path, monkeypatch):
+    src = _touch(tmp_path / "in.mp4", b"x")
+    out = tmp_path / "out.mp4"
+    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
+
+    def fake_run(cmd, check=False, capture_output=True, text=True):
+        class R:
+            returncode = 1
+            stderr = "boom"
+
+        return R()
+
+    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)
+    with pytest.raises(RenderError, match="tempo"):
+        tempo_finished_video(
+            input_path=src, output_path=out, video_speed=150, mode="single"
+        )
+
+
 def test_build_reddit_background_raises_render_error_on_ffmpeg_failure(
     tmp_path, monkeypatch
 ):
     source = _touch(tmp_path / "source.mp4")
     monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
 
     def fake_run(cmd, check=False, capture_output=True, text=True):
         class R:
             returncode = 1
             stderr = "concat exploded"
