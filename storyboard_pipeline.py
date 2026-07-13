# -*- coding: utf-8 -*-
"""
storyboard_pipeline.py - 完整的 storyboard 视频生成流程
封装 run_from_storyboard.py 的逻辑，供 server.py 调用
"""
import os
import sys
import json
import uuid
from pathlib import Path

# 设置 HuggingFace 镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "outputs"
AUDIO_DIR = OUT_DIR / "audio"
SUBTITLE_DIR = OUT_DIR / "subtitles"
VIDEO_DIR = OUT_DIR / "video"
FINAL_DIR = VIDEO_DIR

# 确保目录存在
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# 导入服务
from services.tts_service import GPTSoVITSTTSService, TTSConfig
from services.subtitle_service import write_srt_file
from services.composition_service import compose_teaching_video, probe_duration
from services.manim_service import render_manim_scene
from llm_codegen_service import generate_manim_code, execute_manim_code


def concat_wav(paths: list[Path], out_path: Path) -> float:
    """拼接多个 WAV 文件"""
    import wave
    import contextlib

    if not paths:
        raise RuntimeError("没有音频文件可拼接")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with contextlib.closing(wave.open(str(paths[0]), "rb")) as first:
        params = first.getparams()
        nchannels = first.getnchannels()
        sampwidth = first.getsampwidth()
        framerate = first.getframerate()

    total_frames = 0
    with contextlib.closing(wave.open(str(out_path), "wb")) as out:
        out.setparams(params)
        for path in paths:
            with contextlib.closing(wave.open(str(path), "rb")) as w:
                if (w.getnchannels() != nchannels
                        or w.getsampwidth() != sampwidth
                        or w.getframerate() != framerate):
                    raise RuntimeError(f"wav 参数不一致: {path}")
                frames = w.readframes(w.getnframes())
                out.writeframes(frames)
                total_frames += w.getnframes()

    if framerate > 0:
        return round(total_frames / float(framerate), 3)
    return 0.0


def run_pipeline(storyboard: dict, task_id: str = None, use_whisper: bool = True) -> dict:
    """
    执行完整的 storyboard 视频生成流程
    
    Args:
        storyboard: storyboard JSON 字典，包含 segments 等
        task_id: 任务 ID，默认自动生成
        use_whisper: 是否使用 WhisperX 对齐字幕
    
    Returns:
        包含生成结果的字典
    """
    segments = storyboard.get("segments", [])
    if not segments:
        return {"error": "segments 不能为空", "status": "failed"}

    if not task_id:
        task_id = str(uuid.uuid4())

    print(f"[pipeline] task_id={task_id}, segments={len(segments)}")

    # ============ 1. TTS ============
    print(">>> [1/4] TTS")
    cfg = TTSConfig.from_env()
    tts = GPTSoVITSTTSService(cfg)

    audio_results = []
    audio_paths: list[Path] = []
    tts_errors = []

    for i, seg in enumerate(segments, start=1):
        narration = seg.get("narration", "")
        if not narration:
            tts_errors.append({"segment_index": i, "error": "narration 为空"})
            continue

        audio_path = AUDIO_DIR / f"{task_id}_seg_{i:02d}.wav"

        try:
            result = tts.synthesize_to_file(text=narration, output_path=audio_path)
            duration = result.get("duration_seconds")
            print(f"    - seg {i}: {audio_path.name}  ({duration:.2f}s)")
        except Exception as e:
            tts_errors.append({"segment_index": i, "error": str(e)})
            print(f"    - seg {i}: TTS 失败 - {e}")
            continue

        audio_results.append({
            "segment_index": i,
            "segment_title": seg.get("kind", "seg"),
            "narration_text": narration,
            "subtitle_text": seg.get("subtitle") or narration,
            "audio_path": str(audio_path),
            "audio_file": audio_path.name,
            "audio_duration_seconds": duration,
        })
        audio_paths.append(audio_path)

    if not audio_results:
        return {"error": "TTS 全部失败", "tts_errors": tts_errors, "status": "failed"}

    # ============ 2. 拼接 + SRT ============
    print(">>> [2/4] merge audio + SRT")
    merged_audio_path = AUDIO_DIR / f"{task_id}_merged.wav"
    total_dur = concat_wav(audio_paths, merged_audio_path)
    print(f"    merged: {merged_audio_path.name}  ({total_dur:.2f}s)")

    srt_path = SUBTITLE_DIR / f"{task_id}.srt"
    srt_info = None

    if use_whisper:
        try:
            from services.whisperx_align_service import WhisperXAligner, align_segments, write_aligned_srt
            print("    [align] WhisperX wav2vec2 forced alignment ...")
            aligner = WhisperXAligner(language="zh", device="cpu")
            cues = align_segments(audio_results, aligner, language="zh", verbose=True)
            srt_info = write_aligned_srt(cues, srt_path)
            print(f"    srt: {srt_path.name} (cues={srt_info['cue_count']})")
        except Exception as e:
            print(f"    !! WhisperX align failed: {e}, fallback to char-ratio")
            srt_info = write_srt_file(audio_results, srt_path)
    else:
        srt_info = write_srt_file(audio_results, srt_path)

    # ============ 3. Manim 渲染 ============
    print(">>> [3/4] Manim renders")
    video_segments = []
    manim_errors = []

    for i, (seg, audio_info) in enumerate(zip(segments, audio_results), start=1):
        template = seg.get("template") or "bullet_summary"
        target_dur = audio_info.get("audio_duration_seconds") or 5.0
        params = dict(seg.get("params", {}))
        # 动画最少 3 秒，避免太短看不清
        anim_dur = max(3.0, target_dur)
        params["duration"] = anim_dur

        video_path = None
        method = "template"

        # 尝试1: 使用模板
        try:
            r = render_manim_scene(
                template=template,
                params=params,
                output_filename=f"{task_id}_seg_{i:02d}_{template}",
                quality="medium",
            )
            video_path = r["video_path"]
            actual = probe_duration(video_path)
            print(f"    - seg {i}: {template} -> {actual:.2f}s (模板)")
        except Exception as e:
            manim_errors.append({"segment_index": i, "template": template, "error": str(e), "method": "template"})
            print(f"    - seg {i}: 模板 {template} 失败 - {e}")

            # 尝试2: 使用 LLM 生成代码（方案C）
            try:
                print(f"    - seg {i}: 尝试 LLM 生成代码...")
                narration = seg.get("narration", "")
                title = params.get("title", template)
                
                code_result = generate_manim_code(
                    title=title,
                    requirements=f"生成一个关于「{title}」的动画，旁白内容：{narration}"
                )
                
                if code_result["success"]:
                    exec_result = execute_manim_code(
                        code=code_result["code"],
                        quality="medium"
                    )
                    
                    if exec_result["success"]:
                        video_path = exec_result["video_path"]
                        method = "llm_codegen"
                        actual = probe_duration(video_path)
                        print(f"    - seg {i}: LLM 代码生成 -> {actual:.2f}s")
                    else:
                        print(f"    - seg {i}: LLM 代码执行失败 - {exec_result['error']}")
                else:
                    print(f"    - seg {i}: LLM 代码生成失败 - {code_result['error']}")
            except Exception as e2:
                print(f"    - seg {i}: LLM 代码生成异常 - {e2}")

        # 如果有视频，添加到结果
        if video_path:
            video_segments.append({
                "video_path": video_path,
                "target_duration": anim_dur,  # 用动画时长，不是纯音频时长
                "method": method,
            })

    if not video_segments:
        return {
            "error": "Manim 渲染全部失败",
            "tts_errors": tts_errors,
            "manim_errors": manim_errors,
            "status": "failed",
        }

    # ============ 4. 合成 ============
    print(">>> [4/4] composition")
    final_path = FINAL_DIR / f"{task_id}_final.mp4"

    try:
        r = compose_teaching_video(
            video_segments=video_segments,
            audio_path=merged_audio_path,
            srt_path=srt_path,
            output_path=final_path,
            bgm_path=None,
            fps=30,
            font_size=18,
            margin_v=25,
        )
        print(f"    final: {r['video_path']}  ({r['file_size_bytes'] / 1024:.1f} KB)")
    except Exception as e:
        return {
            "error": f"合成失败: {e}",
            "tts_errors": tts_errors,
            "manim_errors": manim_errors,
            "status": "failed",
        }

    # 只返回文件名，避免中文路径编码问题
    video_path = Path(r["video_path"])
    video_filename = video_path.name

    return {
        "status": "completed",
        "task_id": task_id,
        "output_video": video_filename,
        "output_video_dir": str(video_path.parent),
        "file_size_bytes": r["file_size_bytes"],
        "segments_count": r["segments_count"],
        "total_duration": total_dur,
        "audio_results": audio_results,
        "tts_errors": tts_errors,
        "manim_errors": manim_errors,
    }
