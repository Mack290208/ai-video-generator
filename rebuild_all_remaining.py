# -*- coding: utf-8 -*-
"""
rebuild_all_remaining.py — 批量重建剩余40个视频
================================================
对所有视频：用原始segment + 修复segment 重新合成 + 烧录字幕
输出到 桌面/已检测视频/
"""

import json, os, shutil, subprocess, wave
from pathlib import Path

BASE_DIR = Path(r"C:\Users\hymac\Desktop\临时python骨架穿透文件")
OUTPUTS = BASE_DIR / "outputs" / "approach1"
AUDIO_DIR = OUTPUTS / "audio"
VIDEO_DIR = OUTPUTS / "video"
SUBTITLE_DIR = OUTPUTS / "subtitles"
TEMP_DIR = OUTPUTS / "temp"
SRC_VIDEO_DIR = Path(r"C:\Users\hymac\Desktop\视频未检测")
OUTPUT_FOLDER = Path(r"C:\Users\hymac\Desktop\已检测视频")
OUTPUT_FOLDER.mkdir(exist_ok=True)
FFMPEG = "ffmpeg"

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

def find_seg_video(tid, sid, template, is_custom):
    """优先用修复版，否则原版"""
    fix = f"fix_{tid}_seg{sid:02d}.mp4"
    for f in VIDEO_DIR.rglob(fix):
        return f
    suffix = "custom" if is_custom else template
    orig = f"{tid}_seg_{sid:02d}_{suffix}.mp4"
    for f in VIDEO_DIR.rglob(orig):
        return f
    pattern = f"{tid}_seg_{sid:02d}"
    for f in VIDEO_DIR.rglob(f"*{pattern}*.mp4"):
        return f
    return None

def rebuild_one(tid, video_name, fix_sids):
    """重建单个视频"""
    sb_path = OUTPUTS / f"{tid}_storyboard.json"
    with open(sb_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    segments = data.get("segments", [])
    srt_path = SUBTITLE_DIR / f"{tid}.srt"
    if not srt_path.exists():
        print(f"  [SKIP] SRT not found")
        return False
    
    padded_videos = []
    audio_files = []
    
    for seg in segments:
        sid = seg["id"]
        template = seg["template"]
        is_custom = bool(seg.get("manim_code", "").strip())
        seg_video = find_seg_video(tid, sid, template, is_custom)
        af = AUDIO_DIR / f"{tid}_seg_{sid:02d}.wav"
        
        if not seg_video or not af.exists():
            continue
        
        audio_dur = get_wav_dur(str(af))
        is_fixed = sid in fix_sids
        
        # Pad video
        padded = TEMP_DIR / f"padded_{tid}_seg{sid:02d}.mp4"
        src_dur = probe_dur(seg_video)
        if abs(src_dur - audio_dur) < 0.3:
            shutil.copy2(seg_video, padded)
        else:
            speed = src_dur / audio_dur
            if 0.3 < speed < 3.0:
                subprocess.run([FFMPEG, "-y", "-i", str(seg_video),
                                 "-filter:v", f"setpts={1/speed}*PTS", "-an",
                                 "-c:v", "libx264", "-crf", "23", str(padded)],
                                capture_output=True, timeout=120)
            else:
                shutil.copy2(seg_video, padded)
        
        padded_videos.append(padded)
        audio_files.append(af)
    
    if not padded_videos:
        return False
    
    # Concat videos
    concat_list = TEMP_DIR / "concat_list.txt"
    concat_list.write_text("\n".join(f"file '{v}'" for v in padded_videos), encoding="utf-8")
    concat_out = TEMP_DIR / f"concat_{tid}.mp4"
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(concat_list), "-c", "copy", str(concat_out)],
                    capture_output=True, timeout=300)
    
    # Merge audio
    audio_concat = TEMP_DIR / "audio_concat.txt"
    audio_concat.write_text("\n".join(f"file '{a}'" for a in audio_files), encoding="utf-8")
    merged_audio = TEMP_DIR / "merged_audio.wav"
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(audio_concat), "-c", "copy", str(merged_audio)],
                    capture_output=True, timeout=120)
    
    with_audio = TEMP_DIR / f"with_audio_{tid}.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(concat_out), "-i", str(merged_audio),
                     "-map", "0:v:0", "-map", "1:a:0",
                     "-c:v", "copy", "-c:a", "aac", "-shortest", str(with_audio)],
                    capture_output=True, timeout=120)
    
    # Burn subtitles
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
    final_out = TEMP_DIR / f"final_{tid}.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(with_audio),
                     "-vf", f"subtitles='{srt_escaped}':force_style='{subtitle_style}'",
                     "-c:v", "libx264", "-crf", "23", "-c:a", "copy", str(final_out)],
                    capture_output=True, timeout=300)
    
    # Copy to output folder
    out_path = OUTPUT_FOLDER / video_name
    shutil.copy2(final_out, out_path)
    
    # Cleanup
    for f in padded_videos + [concat_list, concat_out, audio_concat, merged_audio, with_audio]:
        f.unlink(missing_ok=True)
    
    return True


def main():
    print("=" * 60)
    print("  批量重建剩余视频 → 桌面/已检测视频/")
    print("=" * 60)
    
    # Load mapping
    with open(BASE_DIR / "video_mapping.json", "r", encoding="utf-8") as f:
        mapping = json.load(f)
    
    # Define all fixes (segments that were re-rendered)
    all_fixes = {
        "a1_1781765694": {1},    # #36 PAC学习 intro
        "a1_1781766925": {5},    # #42 序列覆盖 custom
    }
    
    # Process videos 06-45
    videos = sorted(SRC_VIDEO_DIR.glob("*.mp4"))
    count = 0
    for vpath in videos:
        vname = vpath.name
        num = int(vname.split("_")[0])
        if num < 6:
            continue  # Skip 01-05 (already done)
        
        info = mapping.get(vname, {})
        tid = info.get("tid")
        if not tid:
            print(f"  [SKIP] {vname}: no matching storyboard")
            continue
        
        count += 1
        has_fix = tid in all_fixes
        fix_sids = all_fixes.get(tid, set())
        marker = "✓FIX" if has_fix else "    "
        
        print(f"\n  [{count}/40] [{marker}] {vname}")
        
        ok = rebuild_one(tid, vname, fix_sids)
        if ok:
            out = OUTPUT_FOLDER / vname
            dur = probe_dur(str(out))
            size = out.stat().st_size / 1024 / 1024
            print(f"         → {out.name} ({dur:.1f}s, {size:.1f}MB)")
        else:
            print(f"         → FAILED")
    
    print(f"\n{'='*60}")
    print(f"  完成！{count} 个视频已放入: {OUTPUT_FOLDER}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
