# -*- coding: utf-8 -*-
"""
rebuild_correct.py — 正确的重建流程
====================================
完全复用原始 pipeline 的时序逻辑：
  1. 测量每段音频实际时长
  2. 计算 timing（pre_buffer=0.5s, post_buffer=0.5s）
  3. 生成新的 SRT（时间戳精确对齐音频）
  4. 拼接视频段（用修复版或原版）
  5. 拼接音频（含 1s 间隔）
  6. 合并视频+音频
  7. 烧录 SRT 字幕
"""

import json, os, shutil, subprocess, wave
from pathlib import Path

BASE_DIR = Path(r"C:\Users\hymac\Desktop\临时python骨架穿透文件")
OUTPUTS = BASE_DIR / "outputs" / "approach1"
AUDIO_DIR = OUTPUTS / "audio"
VIDEO_DIR = OUTPUTS / "video"
SUBTITLE_DIR = OUTPUTS / "subtitles"
TEMP_DIR = OUTPUTS / "temp"
OUTPUT_FOLDER = Path(r"C:\Users\hymac\Desktop\已检测视频")
OUTPUT_FOLDER.mkdir(exist_ok=True)
FFMPEG = "ffmpeg"

PRE_BUFFER = 0.5
POST_BUFFER = 0.5


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


def generate_srt(timed_segments, audio_durs, srt_path):
    """复用 pipeline 的 SRT 生成逻辑"""
    lines = []
    cue_index = 1

    def fmt(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    for seg, audio_dur in zip(timed_segments, audio_durs):
        start_s = seg["start_time"] + seg["pre_buffer"]
        end_s = start_s + audio_dur
        total_dur = end_s - start_s

        narration = seg.get("narration", seg.get("subtitle", ""))
        # 简单拆分：每18字一条
        chunks = []
        text = narration
        while text:
            chunks.append(text[:18])
            text = text[18:]

        total_chars = sum(len(c) for c in chunks)
        t = start_s
        for chunk in chunks:
            ratio = len(chunk) / total_chars if total_chars > 0 else 1.0 / len(chunks)
            chunk_dur = total_dur * ratio
            chunk_end = min(t + chunk_dur, end_s)
            lines.append(f"{cue_index}")
            lines.append(f"{fmt(t)} --> {fmt(chunk_end)}")
            lines.append(chunk)
            lines.append("")
            cue_index += 1
            t = chunk_end

    srt_path.write_text("\n".join(lines), encoding="utf-8")


def concat_wav_with_gap(paths, out_path, gap_seconds=1.0):
    """拼接 WAV，段间插入静音"""
    if not paths:
        return 0
    # 用 ffmpeg concat with silence gap
    concat_list = TEMP_DIR / "audio_concat_gap.txt"
    silence = TEMP_DIR / "silence_1s.wav"
    
    # 生成 1s 静音
    subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i",
                     f"anullsrc=r=24000:cl=mono", "-t", str(gap_seconds),
                     str(silence)], capture_output=True, timeout=30)
    
    lines = []
    for i, p in enumerate(paths):
        lines.append(f"file '{p}'")
        if i < len(paths) - 1:
            lines.append(f"file '{silence}'")
    
    concat_list.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(concat_list), "-c", "copy", str(out_path)],
                    capture_output=True, timeout=300)
    
    concat_list.unlink(missing_ok=True)
    silence.unlink(missing_ok=True)
    
    return get_wav_dur(str(out_path))


def rebuild_one_correct(tid, video_name, fix_sids):
    """用 pipeline 的正确逻辑重建单个视频"""
    sb_path = OUTPUTS / f"{tid}_storyboard.json"
    with open(sb_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    segments = data.get("segments", [])
    
    # Step 1: 收集 segment 视频和音频，测量音频时长
    video_paths = []
    audio_paths = []
    audio_durs = []
    timed_segments = []
    current_time = 0.0
    
    for seg in segments:
        sid = seg["id"]
        template = seg["template"]
        is_custom = bool(seg.get("manim_code", "").strip())
        
        seg_video = find_seg_video(tid, sid, template, is_custom)
        af = AUDIO_DIR / f"{tid}_seg_{sid:02d}.wav"
        
        if not seg_video or not af.exists():
            continue
        
        audio_dur = get_wav_dur(str(af))
        segment_duration = PRE_BUFFER + audio_dur + POST_BUFFER
        
        # Timing（和 pipeline 完全一致）
        timed_seg = dict(seg)
        timed_seg["start_time"] = round(current_time, 3)
        timed_seg["duration"] = round(segment_duration, 3)
        timed_seg["audio_duration"] = round(audio_dur, 3)
        timed_seg["pre_buffer"] = PRE_BUFFER
        timed_seg["post_buffer"] = POST_BUFFER
        
        timed_segments.append(timed_seg)
        audio_durs.append(audio_dur)
        video_paths.append(seg_video)
        audio_paths.append(af)
        
        current_time += segment_duration
    
    if not video_paths:
        return False
    
    # Step 2: Pad 视频段到正确时长（audio_dur + 1.0s）
    padded_videos = []
    for vp, ad in zip(video_paths, audio_durs):
        target = ad + PRE_BUFFER + POST_BUFFER
        padded = TEMP_DIR / f"p_{vp.name}"
        src_dur = probe_dur(vp)
        
        if abs(src_dur - target) < 0.3:
            shutil.copy2(vp, padded)
        else:
            speed = src_dur / target
            if 0.3 < speed < 3.0:
                subprocess.run([FFMPEG, "-y", "-i", str(vp),
                                 "-filter:v", f"setpts={1/speed}*PTS", "-an",
                                 "-c:v", "libx264", "-crf", "23", str(padded)],
                                capture_output=True, timeout=120)
            else:
                shutil.copy2(vp, padded)
        padded_videos.append(padded)
    
    # Step 3: 拼接视频
    concat_v = TEMP_DIR / f"concat_{tid}.mp4"
    vlist = TEMP_DIR / "vlist.txt"
    vlist.write_text("\n".join(f"file '{v}'" for v in padded_videos), encoding="utf-8")
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(vlist), "-c", "copy", str(concat_v)],
                    capture_output=True, timeout=300)
    
    # Step 4: 拼接音频（含 1s 间隔）
    merged_audio = TEMP_DIR / f"audio_{tid}.wav"
    concat_wav_with_gap(audio_paths, merged_audio, gap_seconds=1.0)
    
    # Step 5: 生成新 SRT（时间戳精确对齐）
    srt_path = TEMP_DIR / f"{tid}.srt"
    generate_srt(timed_segments, audio_durs, srt_path)
    
    # Step 6: 合并视频+音频
    with_audio = TEMP_DIR / f"wa_{tid}.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(concat_v), "-i", str(merged_audio),
                     "-map", "0:v:0", "-map", "1:a:0",
                     "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                     "-shortest", str(with_audio)],
                    capture_output=True, timeout=120)
    
    # Step 7: 烧录字幕（用 pipeline 的原始样式）
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
    subtitle_style = (
        "FontName=Microsoft YaHei,"
        "FontSize=20,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H80000000,"
        "BorderStyle=3,"
        "Outline=2,"
        "Shadow=1,"
        "MarginV=15,"
        "Alignment=2"
    )
    final_out = TEMP_DIR / f"final_{tid}.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(with_audio),
                     "-vf", f"subtitles='{srt_escaped}':force_style='{subtitle_style}'",
                     "-c:v", "libx264", "-crf", "23", "-c:a", "copy", str(final_out)],
                    capture_output=True, timeout=300)
    
    # 输出
    out_path = OUTPUT_FOLDER / video_name
    shutil.copy2(final_out, out_path)
    
    # 清理
    for f in padded_videos + [vlist, concat_v, merged_audio, with_audio, final_out]:
        f.unlink(missing_ok=True)
    
    return True


def main():
    print("=" * 60)
    print("  正确的重建流程（pipeline 时序逻辑）")
    print("=" * 60)
    
    with open(BASE_DIR / "video_mapping.json", "r", encoding="utf-8") as f:
        mapping = json.load(f)
    
    # 定义所有修复
    all_fixes = {
        "a1_1781767916": {8},     # 01 机器学习
        "a1_1781768120": {6},     # 02 假设空间
        "a1_1781760566": {4},     # 03 经验风险
        "a1_1781758354": {4},     # 04 交叉验证
        "a1_1781758511": {1, 10}, # 05 误差
        "a1_1781765694": {1},     # 36 PAC学习
        "a1_1781766925": {2,3,4,5,6},  # 42 序列覆盖
    }
    
    videos = sorted(Path(r"C:\Users\hymac\Desktop\视频未检测").glob("*.mp4"))
    count = 0
    for vpath in videos:
        vname = vpath.name
        num = int(vname.split("_")[0])
        
        info = mapping.get(vname, {})
        tid = info.get("tid")
        if not tid:
            continue
        
        count += 1
        fix_sids = all_fixes.get(tid, set())
        marker = "✓FIX" if fix_sids else "    "
        
        print(f"\n  [{count:2d}/45] [{marker}] {vname}")
        
        ok = rebuild_one_correct(tid, vname, fix_sids)
        if ok:
            out = OUTPUT_FOLDER / vname
            dur = probe_dur(str(out))
            size = out.stat().st_size / 1024 / 1024
            print(f"           → {out.name} ({dur:.1f}s, {size:.1f}MB)")
        else:
            print(f"           → FAILED")
    
    print(f"\n{'='*60}")
    print(f"  完成！{count} 个视频已放入: {OUTPUT_FOLDER}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
