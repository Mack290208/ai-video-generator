# -*- coding: utf-8 -*-
"""
rebuild_videos_v2.py — 正确的修复流程
=====================================
用原始 segment 渲染 + 修复的 segment 重新合成视频，然后烧录 SRT 字幕。
"""

import json, os, re, shutil, subprocess, sys, wave
from pathlib import Path

BASE_DIR = Path(r"C:\Users\hymac\Desktop\临时python骨架穿透文件")
MANIM_VENV = BASE_DIR / ".venv_manim" / "Scripts" / "python.exe"
OUTPUTS = BASE_DIR / "outputs" / "approach1"
AUDIO_DIR = OUTPUTS / "audio"
VIDEO_DIR = OUTPUTS / "video"
SUBTITLE_DIR = OUTPUTS / "subtitles"
TEMP_DIR = OUTPUTS / "temp"
SRC_VIDEO_DIR = Path(r"C:\Users\hymac\Desktop\视频未检测")
DESKTOP = Path.home() / "Desktop"
FFMPEG = "ffmpeg"

TEMP_DIR.mkdir(parents=True, exist_ok=True)


def get_wav_dur(path):
    try:
        with wave.open(path, 'r') as wf:
            return wf.getnframes() / wf.getframerate()
    except:
        return 0

def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                        capture_output=True, text=True)
    return float(r.stdout.strip())


def find_segment_video(task_id: str, seg_id: int, template: str, is_custom: bool) -> Path | None:
    """查找 segment 的渲染视频（优先用修复版，否则用原始版）"""
    # 修复版
    fix_name = f"fix_{task_id}_seg{seg_id:02d}.mp4"
    for f in VIDEO_DIR.rglob(fix_name):
        return f
    
    # 原始版
    suffix = "custom" if is_custom else template
    orig_name = f"{task_id}_seg_{seg_id:02d}_{suffix}.mp4"
    for f in VIDEO_DIR.rglob(orig_name):
        return f
    
    # Fallback: 模糊匹配
    pattern = f"{task_id}_seg_{seg_id:02d}"
    for f in VIDEO_DIR.rglob(f"*{pattern}*.mp4"):
        return f
    
    return None


def pad_video_to_duration(src: Path, target_dur: float, output: Path):
    """让视频时长匹配 target_dur（变速或复制）"""
    src_dur = probe_dur(src)
    
    if abs(src_dur - target_dur) < 0.3:
        shutil.copy2(src, output)
        return
    
    speed = src_dur / target_dur
    if 0.3 < speed < 3.0:
        subprocess.run([
            FFMPEG, "-y", "-i", str(src),
            "-filter:v", f"setpts={1/speed}*PTS",
            "-an",
            "-c:v", "libx264", "-crf", "23",
            str(output)
        ], capture_output=True, timeout=120)
    else:
        # 无法合理变速，直接复制
        shutil.copy2(src, output)


def concat_videos(video_list: list[Path], output: Path):
    """拼接多个视频"""
    concat_file = TEMP_DIR / "concat_list.txt"
    lines = [f"file '{v}'" for v in video_list]
    concat_file.write_text("\n".join(lines), encoding="utf-8")
    
    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output)
    ], capture_output=True, timeout=300)
    
    concat_file.unlink(missing_ok=True)


def merge_audio(video: Path, audio_files: list[Path], output: Path):
    """合并视频和音频"""
    # 先拼接所有音频
    audio_concat = TEMP_DIR / "audio_concat.txt"
    lines = [f"file '{a}'" for a in audio_files]
    audio_concat.write_text("\n".join(lines), encoding="utf-8")
    
    merged_audio = TEMP_DIR / "merged_audio.wav"
    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", str(audio_concat),
        "-c", "copy",
        str(merged_audio)
    ], capture_output=True, timeout=120)
    
    # 合并
    subprocess.run([
        FFMPEG, "-y",
        "-i", str(video),
        "-i", str(merged_audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        str(output)
    ], capture_output=True, timeout=120)
    
    audio_concat.unlink(missing_ok=True)
    merged_audio.unlink(missing_ok=True)


def burn_subtitles(video: Path, srt_path: Path, output: Path):
    """烧录 SRT 字幕"""
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
    subtitle_style = (
        "FontName=Microsoft YaHei,"
        "FontSize=20,"
        "PrimaryColour=&H00FFFFFF,"
        "BackColour=&H80000000,"
        "BorderStyle=4,"
        "Outline=0,"
        "Shadow=0,"
        "MarginV=15"
    )
    
    subprocess.run([
        FFMPEG, "-y",
        "-i", str(video),
        "-vf", f"subtitles='{srt_escaped}':force_style='{subtitle_style}'",
        "-c:v", "libx264", "-crf", "23",
        "-c:a", "copy",
        str(output)
    ], capture_output=True, timeout=300)


def rebuild_video(task_id: str, video_name: str, seg_fixes: dict):
    """重建单个视频"""
    print(f"\n{'='*60}")
    print(f"  重建: {video_name}")
    print(f"{'='*60}")
    
    # 加载 storyboard
    sb_path = OUTPUTS / f"{task_id}_storyboard.json"
    with open(sb_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    segments = data.get("segments", [])
    srt_path = SUBTITLE_DIR / f"{task_id}.srt"
    
    if not srt_path.exists():
        print(f"  [ERROR] SRT not found: {srt_path}")
        return
    
    # Step 1: 收集所有 segment 视频（修复的用修复版，其他用原版）
    padded_videos = []
    audio_files = []
    
    for seg in segments:
        sid = seg["id"]
        template = seg["template"]
        is_custom = bool(seg.get("manim_code", "").strip())
        
        # 查找渲染视频
        seg_video = find_segment_video(task_id, sid, template, is_custom)
        if not seg_video:
            print(f"  [SKIP] Seg#{sid}: video not found")
            continue
        
        # 获取音频时长
        af = AUDIO_DIR / f"{task_id}_seg_{sid:02d}.wav"
        if not af.exists():
            print(f"  [SKIP] Seg#{sid}: audio not found")
            continue
        
        audio_dur = get_wav_dur(str(af))
        is_fixed = sid in seg_fixes
        marker = "✓" if is_fixed else " "
        
        print(f"  [{marker}] Seg#{sid:2d} | {template:20s} | audio={audio_dur:.1f}s | {'FIXED' if is_fixed else 'original'}")
        
        # Pad 视频到音频时长
        padded = TEMP_DIR / f"padded_{task_id}_seg{sid:02d}.mp4"
        pad_video_to_duration(seg_video, audio_dur, padded)
        padded_videos.append(padded)
        audio_files.append(af)
    
    if not padded_videos:
        print(f"  [ERROR] No segments found")
        return
    
    # Step 2: 拼接所有 segment 视频
    print(f"\n  拼接 {len(padded_videos)} 个 segments...")
    concat_out = TEMP_DIR / f"concat_{task_id}.mp4"
    concat_videos(padded_videos, concat_out)
    
    # Step 3: 合并音频
    print(f"  合并音频...")
    with_audio = TEMP_DIR / f"with_audio_{task_id}.mp4"
    merge_audio(concat_out, audio_files, with_audio)
    
    # Step 4: 烧录字幕
    print(f"  烧录字幕...")
    final_out = TEMP_DIR / f"final_{task_id}.mp4"
    burn_subtitles(with_audio, srt_path, final_out)
    
    # Step 5: 复制到桌面
    out_path = DESKTOP / video_name
    shutil.copy2(final_out, out_path)
    dur = probe_dur(out_path)
    size = out_path.stat().st_size / 1024 / 1024
    print(f"\n  ✓ 完成: {out_path.name} ({dur:.1f}s, {size:.1f}MB)")
    
    # 清理临时 padded 文件
    for f in padded_videos:
        f.unlink(missing_ok=True)
    concat_out.unlink(missing_ok=True)
    with_audio.unlink(missing_ok=True)


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  正确的修复流程：重新合成 + 烧录字幕")
    print("=" * 60)
    
    # 定义每个视频的修复 segments
    # key: task_id, value: dict of {seg_id: description}
    video_fixes = [
        ("a1_1781767916", "01_西瓜书_什么是机器学习_v2.mp4",
         {8: "归纳偏好 - 奥卡姆剃刀文字提高"}),
        ("a1_1781768120", "02_西瓜书_假设空间与归纳偏好_v2.mp4",
         {6: "多个假设 - 间距拉大"}),
        ("a1_1781760566", "03_西瓜书_经验风险与过拟合_v2.mp4",
         {4: "经验风险 - 流程图间距加大"}),
        ("a1_1781758354", "04_西瓜书_交叉验证与模型选择_v2.mp4",
         {4: "留出法 - 模型上移"}),
        ("a1_1781758511", "05_西瓜书_误差与过拟合与欠拟合_v2.mp4",
         {1: "intro字号缩小", 10: "正则化文字上移"}),
    ]
    
    for task_id, video_name, fixes in video_fixes:
        rebuild_video(task_id, video_name, fixes)
    
    print(f"\n{'='*60}")
    print("  全部完成！请检查桌面上的 _v2.mp4 文件")
    print("  这次字幕是完整烧录的，不会消失")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
