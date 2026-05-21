"""
video_service.py
----------------
\u7528 ffmpeg \u5c06\u5df2\u6709\u7684 (\u5408\u6210\u97f3\u9891 + SRT \u5b57\u5e55) \u62fc\u4e3a\u5360\u4f4d\u6559\u5b66\u89c6\u9891\u3002

\u7b2c\u4e00\u7248\u7b56\u7565\uff1a
- \u8272\u5f69\u80cc\u666f (color source) + \u786c\u5b57\u5e55\u70e7\u5165 (subtitles filter) + \u97f3\u9891 (merged wav)
- \u8f93\u51fa 1280x720 \u4ee5\u4e0b\u6587\u4ef6\u540d\u683c\u5f0f\uff1a<task_id>.mp4

ffmpeg \u67e5\u627e\u9806\u5e8f\uff1a
1. \u73af\u5883\u53d8\u91cf FFMPEG_BIN
2. PATH \u4e2d\u7684 ffmpeg
3. \u5df2\u77e5\u7684 winget Gyan.FFmpeg \u5b89\u88c5\u8def\u5f84\uff08fallback\uff09
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


# \u5df2\u77e5\u7684\u56de\u843d\u8def\u5f84\uff08winget Gyan.FFmpeg\uff09
_FFMPEG_FALLBACKS = [
    r"C:\Users\hymac\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe",
]


def find_ffmpeg() -> str:
    """\u6309\u987a\u5e8f\u67e5\u627e ffmpeg \u53ef\u6267\u884c\u6587\u4ef6\u3002"""
    env_path = os.getenv("FFMPEG_BIN")
    if env_path and Path(env_path).exists():
        return env_path

    in_path = shutil.which("ffmpeg")
    if in_path:
        return in_path

    for candidate in _FFMPEG_FALLBACKS:
        if Path(candidate).exists():
            return candidate

    raise RuntimeError(
        "\u627e\u4e0d\u5230 ffmpeg\u3002\u8bf7\u5c06\u5b83\u52a0\u5165 PATH\uff0c\u6216\u8bbe\u7f6e\u73af\u5883\u53d8\u91cf FFMPEG_BIN \u6307\u5411 ffmpeg.exe\u3002"
    )


def _escape_subtitles_path_for_ffmpeg(srt_path: Path) -> str:
    r"""
    ffmpeg \u7684 subtitles filter \u5728 Windows \u4e0a\u5bf9\u8def\u5f84\u7279\u522b\u654f\u611f\uff1a
    - \u5192\u53f7 ":" \u9700\u8981\u8f6c\u4e49 -> "\\:"
    - \u53cd\u659c\u6760 "\\" \u9700\u8981\u8f6c\u4e49 -> "\\\\" (\u5728 filter \u53c2\u6570\u91cc\u8fd8\u8981\u518d\u8f6c\u4e49\u4e00\u6b21)
    \u7b80\u5355\u505a\u6cd5\uff1a\u5148\u53cd\u659c\u6760 -> /\uff0c\u518d\u5e26\u82f1\u6587\u5355\u5f15\u53f7\u5305\u88f9\u3002
    """
    posix_like = str(srt_path).replace("\\", "/")
    # \u5355\u5f15\u53f7\u5728 filter \u5185\u6bd4\u8f83\u5b89\u5168
    posix_like_escaped = posix_like.replace(":", r"\:")
    return posix_like_escaped


def render_placeholder_video(
    audio_path: str | Path,
    srt_path: str | Path,
    output_path: str | Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    bg_color: str = "black",
    font_size: int = 28,
    font_color: str = "white",
    margin_v: int = 60,
    ffmpeg_bin: str | None = None,
) -> dict[str, Any]:
    """
    \u5408\u6210\u4e00\u4e2a\u5360\u4f4d\u6559\u5b66\u89c6\u9891\uff1a\u7eaf\u8272\u80cc\u666f + \u786c\u5b57\u5e55 + \u97f3\u9891\u3002
    \u89c6\u9891\u957f\u5ea6 = \u97f3\u9891\u957f\u5ea6 (\u7528 -shortest)\u3002
    """
    audio_path = Path(audio_path)
    srt_path = Path(srt_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        raise FileNotFoundError(f"\u97f3\u9891\u6587\u4ef6\u4e0d\u5b58\u5728: {audio_path}")
    if not srt_path.exists():
        raise FileNotFoundError(f"\u5b57\u5e55\u6587\u4ef6\u4e0d\u5b58\u5728: {srt_path}")

    ffmpeg = ffmpeg_bin or find_ffmpeg()
    subs_path = _escape_subtitles_path_for_ffmpeg(srt_path)

    # \u5b57\u5e55\u6837\u5f0f\uff08ASS force_style\uff09\uff1a\u5b57\u53f7\u3001\u989c\u8272\uff08\u767d\u8272\uff09\u3001\u63cf\u8fb9\uff08\u9ed1\u8272\uff09
    force_style = (
        f"FontName=Microsoft YaHei,"
        f"FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,"
        f"BorderStyle=1,"
        f"Outline=2,"
        f"Shadow=1,"
        f"Alignment=2,"
        f"MarginV={margin_v}"
    )

    # \u89c6\u9891\u94fe\uff1a\u8272\u5f69\u6e90 -> subtitles filter
    vf = f"subtitles='{subs_path}':force_style='{force_style}'"

    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", f"color=c={bg_color}:s={width}x{height}:r={fps}",
        "-i", str(audio_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if proc.returncode != 0:
        # \u629b\u51fa\u65f6\u591a\u5e26\u4e00\u4e9b stderr\uff0c\u65b9\u4fbf\u6392\u67e5
        tail = "\n".join(proc.stderr.splitlines()[-30:])
        raise RuntimeError(f"ffmpeg \u5931\u8d25 (exit={proc.returncode})\n{tail}")

    size = output_path.stat().st_size if output_path.exists() else 0
    return {
        "video_path": str(output_path),
        "ffmpeg_bin": ffmpeg,
        "width": width,
        "height": height,
        "fps": fps,
        "file_size_bytes": size,
        "ffmpeg_tail": "\n".join(proc.stderr.splitlines()[-5:]),
    }
