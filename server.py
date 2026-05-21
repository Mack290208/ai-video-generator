from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any
from pathlib import Path
import uuid
import json
import time
import wave
import contextlib
import uvicorn
from dotenv import load_dotenv

from services.tts_service import GPTSoVITSTTSService, TTSConfig
from services.subtitle_service import write_srt_file
from services.video_service import render_placeholder_video

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
OUTPUT_DIR = BASE_DIR / "outputs"
AUDIO_DIR = OUTPUT_DIR / "audio"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"
VIDEO_DIR = OUTPUT_DIR / "video"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ML Teaching Video Generator - TTS v1")


class GenerateVideoRequest(BaseModel):
    video_task: str | None = None
    request_id: str | None = None
    topic: str | None = None
    title: str | None = None
    global_style: dict[str, Any] | None = None
    segments: list[dict[str, Any]] = Field(default_factory=list)


@app.get("/")
def root():
    return {
        "ok": True,
        "service": "ml_teaching_video_generator",
        "version": "tts-v1"
    }


@app.get("/health")
def health():
    cfg = TTSConfig.from_env()
    return {
        "ok": True,
        "tts_provider": cfg.provider,
        "tts_base_url": cfg.base_url,
        "default_ref_audio": cfg.ref_audio_path,
        "default_prompt_text": cfg.prompt_text,
        "audio_output_dir": str(AUDIO_DIR)
    }


@app.post("/generate-video")
def generate_video(payload: GenerateVideoRequest):
    task = normalize_request(payload)
    task_id = task.get("request_id") or str(uuid.uuid4())
    segments = task.get("segments", [])

    if not segments:
        raise HTTPException(status_code=400, detail="segments 不能为空")

    tts_config = TTSConfig.from_env()
    tts_service = GPTSoVITSTTSService(tts_config)
    audio_results = []
    tts_errors = []

    # 全局默认参考音频/文本（task 级别可覆盖 env）
    global_ref_audio = task.get("ref_audio_path") or tts_config.ref_audio_path
    global_prompt_text = task.get("prompt_text") if task.get("prompt_text") is not None else tts_config.prompt_text

    for index, segment in enumerate(segments, start=1):
        narration = extract_narration_text(segment)
        if not narration:
            continue

        audio_filename = f"{task_id}_seg_{index:02d}.wav"
        audio_path = AUDIO_DIR / audio_filename

        try:
            result = tts_service.synthesize_to_file(
                text=narration,
                output_path=audio_path,
                speaker=segment.get("speaker") or task.get("speaker"),
                speed=segment.get("speed") or task.get("speed"),
                ref_audio_path=segment.get("ref_audio_path") or global_ref_audio,
                prompt_text=segment.get("prompt_text") if segment.get("prompt_text") is not None else global_prompt_text,
                prompt_lang=segment.get("prompt_lang"),
                text_lang=segment.get("text_lang"),
                text_split_method=segment.get("text_split_method") or task.get("text_split_method"),
            )
        except Exception as e:
            tts_errors.append({"segment_index": index, "error": str(e)})
            continue

        audio_results.append({
            "segment_index": index,
            "segment_title": segment.get("title") or segment.get("subtitle") or f"segment_{index}",
            "narration_text": narration,
            "audio_path": str(audio_path),
            "audio_file": audio_filename,
            "audio_duration_seconds": result.get("duration_seconds"),
            "tts_meta": result.get("meta", {})
        })

    status = "tts_completed" if not tts_errors else ("tts_partial" if audio_results else "tts_failed")

    # 拼接所有成功的段落为完整音频（只在全部成功时拼，缺段拼了没意义）
    merged_audio = None
    if audio_results and not tts_errors:
        try:
            merged_filename = f"{task_id}_merged.wav"
            merged_path = AUDIO_DIR / merged_filename
            segment_paths = [item["audio_path"] for item in audio_results]
            total_duration = concat_wav_files(segment_paths, merged_path)
            merged_audio = {
                "audio_path": str(merged_path),
                "audio_file": merged_filename,
                "duration_seconds": total_duration,
                "segment_count": len(segment_paths),
            }
        except Exception as e:
            merged_audio = {"error": f"拼接失败: {e}"}

    # 生成字幕 SRT（有成功段就生成，时间戳按顺序累加）
    subtitle_info = None
    if audio_results:
        try:
            srt_path = SUBTITLE_DIR / f"{task_id}.srt"
            subtitle_info = write_srt_file(audio_results, srt_path)
        except Exception as e:
            subtitle_info = {"error": f"字幕生成失败: {e}"}

    return {
        "task_id": task_id,
        "status": status,
        "title": task.get("title") or "未命名机器学习教学视频",
        "topic": task.get("topic") or "未指定主题",
        "segments_received": len(segments),
        "segments_tts_generated": len(audio_results),
        "audio_results": audio_results,
        "merged_audio": merged_audio,
        "subtitle": subtitle_info,
        "tts_errors": tts_errors,
        "tts_backend": {"provider": tts_config.provider, "base_url": tts_config.base_url},
        "note": "已完成脚本→旁白生成→拼接→字幕，下一步可以接画面/合成"
    }


class RenderVideoRequest(BaseModel):
    audio_path: str
    subtitle_path: str
    output_filename: str | None = None
    width: int | None = 1280
    height: int | None = 720
    fps: int | None = 30
    bg_color: str | None = "black"
    font_size: int | None = 28
    margin_v: int | None = 60


@app.post("/render-video")
def render_video(payload: RenderVideoRequest):
    audio_path = Path(payload.audio_path)
    srt_path = Path(payload.subtitle_path)
    if not audio_path.exists():
        raise HTTPException(status_code=400, detail=f"音频文件不存在: {audio_path}")
    if not srt_path.exists():
        raise HTTPException(status_code=400, detail=f"字幕文件不存在: {srt_path}")

    filename = payload.output_filename or f"render_{int(time.time())}.mp4"
    if not filename.lower().endswith(".mp4"):
        filename += ".mp4"
    output_path = VIDEO_DIR / filename

    try:
        result = render_placeholder_video(
            audio_path=audio_path,
            srt_path=srt_path,
            output_path=output_path,
            width=payload.width or 1280,
            height=payload.height or 720,
            fps=payload.fps or 30,
            bg_color=payload.bg_color or "black",
            font_size=payload.font_size or 28,
            margin_v=payload.margin_v or 60,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "ok": True,
        "video": result,
    }


@app.post("/debug/parse-task")
def debug_parse_task(payload: GenerateVideoRequest):
    task = normalize_request(payload)
    return {
        "ok": True,
        "parsed_task": task
    }


def normalize_request(payload: GenerateVideoRequest) -> dict[str, Any]:
    if payload.video_task:
        try:
            task = json.loads(payload.video_task)
            if not isinstance(task, dict):
                raise HTTPException(status_code=400, detail="video_task 必须是 JSON object 字符串")
            if not task.get("request_id"):
                task["request_id"] = payload.request_id or str(uuid.uuid4())
            return task
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"video_task 不是合法 JSON: {e}")

    return {
        "request_id": payload.request_id or str(uuid.uuid4()),
        "topic": payload.topic,
        "title": payload.title,
        "global_style": payload.global_style,
        "segments": payload.segments,
    }


def concat_wav_files(input_paths: list[str], output_path: Path) -> float | None:
    """
    把多个 wav 按顺序拼接成一个，返回总时长（秒）。
    要求：所有 wav 的声道数/采样率/采样宽度一致（GPT-SoVITS 输出满足）。
    用标准库 wave，不依赖 ffmpeg。
    """
    if not input_paths:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 用第一个文件的参数作为基准
    with contextlib.closing(wave.open(input_paths[0], "rb")) as first:
        params = first.getparams()
        nchannels = first.getnchannels()
        sampwidth = first.getsampwidth()
        framerate = first.getframerate()

    total_frames = 0
    with contextlib.closing(wave.open(str(output_path), "wb")) as out:
        out.setparams(params)
        for path in input_paths:
            with contextlib.closing(wave.open(path, "rb")) as w:
                if (w.getnchannels() != nchannels
                        or w.getsampwidth() != sampwidth
                        or w.getframerate() != framerate):
                    raise RuntimeError(
                        f"wav 参数不一致: {path} "
                        f"ch={w.getnchannels()} rate={w.getframerate()} sw={w.getsampwidth()}"
                    )
                frames = w.readframes(w.getnframes())
                out.writeframes(frames)
                total_frames += w.getnframes()

    if framerate > 0:
        return round(total_frames / float(framerate), 3)
    return None


def extract_narration_text(segment: dict[str, Any]) -> str:
    candidates = [
        segment.get("narration"),
        segment.get("voiceover"),
        segment.get("script"),
        segment.get("text"),
        segment.get("content"),
    ]
    for item in candidates:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return ""


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)