"""
composition_service.py
----------------------
多段视频合成器：Manim 画面片段 + 旁白音频 + 硬字幕 + (可选) 背景音乐。

核心思路：
1. 画面层：多个 Manim 视频片段按"段落时长"对齐（过短就循环最后一帧、过长就加速或截断）。
   - 为了第一版简单起见：让每一段 Manim 视频"按旁白音频时长播放"——
     · 片段比音频短：尾部冻结最后一帧（tpad + freeze）补齐
     · 片段比音频长：截断到音频时长
2. 音频层：所有段落的旁白 wav 先拼起来（已由 server.py 的 concat_wav_files 做了）
3. BGM（可选）：低音量混入整条音轨
4. 字幕：用 ffmpeg subtitles filter 硬烧入最终视频

这一版只做单路画面轨（多段 Manim/静态图串联），不做画中画。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from services.video_service import find_ffmpeg, _escape_subtitles_path_for_ffmpeg


def _ffprobe_bin(ffmpeg_bin: str) -> str:
    """同目录下找 ffprobe。"""
    candidate = Path(ffmpeg_bin).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if candidate.exists():
        return str(candidate)
    which = shutil.which("ffprobe")
    if which:
        return which
    raise RuntimeError(f"找不到 ffprobe（同 ffmpeg 目录应该有）: {candidate}")


def probe_duration(path: str | Path, ffmpeg_bin: str | None = None) -> float:
    """返回媒体文件时长（秒）。"""
    ffm = ffmpeg_bin or find_ffmpeg()
    ffprobe = _ffprobe_bin(ffm)
    cmd = [
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {out.stderr[-500:]}")
    return float(out.stdout.strip())


def _pad_or_trim_video(
    src_video: Path,
    target_duration: float,
    output_path: Path,
    ffmpeg_bin: str,
    fps: int = 30,
) -> Path:
    """
    让视频时长对齐到 target_duration：
    策略（v2）：
    - 差距 < 0.3s: 直接复制（容忍轻微偏差）
    - 其他情况: 用 setpts 变速（不会丢帧，安全），限制在 0.5x~2x。
    ——原来用 tpad=stop_mode=clone 在某些 ffmpeg 版本会丢帧，改成 setpts 就没这问题了。
    产物不包含音频（原 manim 产物也没有）。
    """
    src_dur = probe_duration(src_video, ffmpeg_bin)

    if abs(src_dur - target_duration) < 0.3:
        # 时长已经足够接近，直接复制
        shutil.copyfile(src_video, output_path)
        return output_path

    # setpts 值 = target_duration / src_dur
    # （> 1 表示播放变慢，时长变长）
    speed_factor = target_duration / src_dur
    # 安全限制
    speed_factor = max(0.5, min(2.5, speed_factor))
    vf = f"setpts={speed_factor:.5f}*PTS"

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(src_video),
        "-vf", vf,
        "-r", str(fps),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-crf", "23",
        "-an",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg pad/trim 失败: {proc.stderr[-500:]}")
    return output_path


def _concat_videos(
    clips: list[Path],
    output_path: Path,
    ffmpeg_bin: str,
) -> Path:
    """把多个视频片段按 concat demuxer 拼起来。要求编码参数一致。"""
    if not clips:
        raise ValueError("clips 为空")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        list_file = Path(f.name)
        for clip in clips:
            # concat demuxer 要求单引号路径
            p = str(clip).replace("\\", "/")
            f.write(f"file '{p}'\n")

    try:
        # 直接重新编码——更稳，concat + copy 在某些 ffmpeg 版本上有丢帧 bug
        cmd_reencode = [
            ffmpeg_bin, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast", "-crf", "23",
            "-r", "30",
            str(output_path),
        ]
        proc2 = subprocess.run(cmd_reencode, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc2.returncode != 0:
            raise RuntimeError(f"ffmpeg concat re-encode 失败: {proc2.stderr[-800:]}")
    finally:
        try:
            list_file.unlink()
        except OSError:
            pass

    return output_path


def compose_teaching_video(
    video_segments: list[dict[str, Any]],
    audio_path: str | Path,
    srt_path: str | Path,
    output_path: str | Path,
    bgm_path: str | Path | None = None,
    bgm_volume_db: float = -22.0,
    fps: int = 30,
    font_size: int = 28,
    margin_v: int = 60,
    ffmpeg_bin: str | None = None,
) -> dict[str, Any]:
    """
    合成最终教学视频。

    Args:
        video_segments: 画面段落列表，每项形如：
            {
                "video_path": "outputs/manim/.../intro.mp4",   # 本段画面源
                "target_duration": 6.23                          # 本段应该持续的秒数（= 对应旁白音频时长）
            }
        audio_path:  已拼接好的旁白音频（wav）
        srt_path:    全片字幕 srt
        output_path: 输出 mp4
        bgm_path:    可选，背景音乐文件（mp3/wav）
        bgm_volume_db: BGM 衰减（负数 dB，默认 -22dB，低于旁白一档）
        fps:         视频帧率
        font_size / margin_v: 字幕样式
    """
    ffm = ffmpeg_bin or find_ffmpeg()

    audio_path = Path(audio_path)
    srt_path = Path(srt_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")
    if not srt_path.exists():
        raise FileNotFoundError(f"字幕文件不存在: {srt_path}")
    if not video_segments:
        raise ValueError("video_segments 不能为空")

    with tempfile.TemporaryDirectory(prefix="compose_") as tmp_dir:
        tmp = Path(tmp_dir)

        # Step 1: 每段画面对齐到目标时长
        aligned_clips: list[Path] = []
        for i, seg in enumerate(video_segments):
            src = Path(seg["video_path"])
            if not src.exists():
                raise FileNotFoundError(f"画面片段不存在 (segment {i}): {src}")
            target_dur = float(seg["target_duration"])
            out = tmp / f"aligned_{i:02d}.mp4"
            _pad_or_trim_video(src, target_dur, out, ffm, fps=fps)
            aligned_clips.append(out)

        # Step 2: 拼接所有画面
        concat_video = tmp / "concat_video.mp4"
        _concat_videos(aligned_clips, concat_video, ffm)

        # Step 3: 合成（旁白 + BGM + 字幕硬烧入）
        subs_path = _escape_subtitles_path_for_ffmpeg(srt_path)
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
        vf = f"subtitles='{subs_path}':force_style='{force_style}'"

        cmd = [
            ffm, "-y",
            "-i", str(concat_video),
            "-i", str(audio_path),
        ]
        if bgm_path:
            bgm_path = Path(bgm_path)
            if not bgm_path.exists():
                raise FileNotFoundError(f"BGM 文件不存在: {bgm_path}")
            cmd += ["-stream_loop", "-1", "-i", str(bgm_path)]  # BGM 循环直到旁白结束

        cmd += ["-vf", vf]

        if bgm_path:
            # 混音：旁白 0dB，BGM 衰减到 bgm_volume_db
            filter_complex = (
                f"[2:a]volume={bgm_volume_db}dB[bg];"
                f"[1:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            cmd += [
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[aout]",
            ]
        else:
            cmd += [
                "-map", "0:v",
                "-map", "1:a",
            ]

        cmd += [
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            tail = "\n".join(proc.stderr.splitlines()[-30:])
            raise RuntimeError(f"ffmpeg 最终合成失败 (exit={proc.returncode})\n{tail}")

    size = output_path.stat().st_size if output_path.exists() else 0

    return {
        "video_path": str(output_path),
        "segments_count": len(video_segments),
        "has_bgm": bool(bgm_path),
        "bgm_volume_db": bgm_volume_db if bgm_path else None,
        "file_size_bytes": size,
    }
