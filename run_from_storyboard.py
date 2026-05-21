"""
run_from_storyboard.py
----------------------
第四阶段最后一公里：吃 LLM 输出的 storyboard JSON 直接生成视频。

流程：
1. 读 storyboard JSON
2. 对每段 segment：
   - 调 TTS 生成旁白
3. 拼接所有旁白 + 写 SRT
4. 对每段：
   - 用 segment.template + params + audio_duration 调 manim_service
5. 合成最终 mp4

用法：
    python run_from_storyboard.py outputs/llm_storyboard_decision_tree.json [task_id]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from services.composition_service import compose_teaching_video, probe_duration
from services.manim_service import render_manim_scene
from services.subtitle_service import write_srt_file
from services.tts_service import GPTSoVITSTTSService, TTSConfig
from services.duration_estimator import (
    estimate_narration_seconds,
    estimate_storyboard_seconds,
)
from services.whisper_align_service import (
    WhisperAligner,
    align_segments,
    write_aligned_srt,
)


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OUT_DIR = BASE_DIR / "outputs"
AUDIO_DIR = OUT_DIR / "audio"
SUBTITLE_DIR = OUT_DIR / "subtitles"
FINAL_DIR = OUT_DIR / "video"
for d in (AUDIO_DIR, SUBTITLE_DIR, FINAL_DIR):
    d.mkdir(parents=True, exist_ok=True)


def concat_wav(paths: list[Path], out_path: Path) -> float:
    import contextlib
    import wave

    with contextlib.closing(wave.open(str(paths[0]), "rb")) as first:
        params = first.getparams()
        framerate = first.getframerate()

    total_frames = 0
    with contextlib.closing(wave.open(str(out_path), "wb")) as out:
        out.setparams(params)
        for p in paths:
            with contextlib.closing(wave.open(str(p), "rb")) as w:
                frames = w.readframes(w.getnframes())
                out.writeframes(frames)
                total_frames += w.getnframes()
    return total_frames / float(framerate) if framerate > 0 else 0.0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python run_from_storyboard.py <storyboard.json> [task_id] [--no-whisper]")
        return 1

    storyboard_path = Path(sys.argv[1])
    if not storyboard_path.is_absolute():
        storyboard_path = BASE_DIR / storyboard_path
    task_id = sys.argv[2] if (len(sys.argv) > 2 and not sys.argv[2].startswith("--")) else storyboard_path.stem

    # 默认开 whisper 对齐；传 --no-whisper 可关
    use_whisper = ("--no-whisper" not in sys.argv)

    sb = json.loads(storyboard_path.read_text(encoding="utf-8"))
    segments = sb["segments"]

    print(f"[storyboard] {storyboard_path.name}")
    print(f"  title    = {sb.get('video_title', 'unknown')}")
    print(f"  segments = {len(segments)}")
    print(f"  target   = {sb.get('duration_target_seconds', '?')}s")
    print(f"  flags    = {len(sb.get('missing_template_flags', []))}")
    if sb.get("missing_template_flags"):
        for f in sb["missing_template_flags"]:
            print(f"    [flag] wanted={f.get('wanted')} -> fallback={f.get('fallback_to')}")
    print()

    # ============ 0. 预估（A2 新增）============
    narrations = [seg["narration"] for seg in segments]
    pre_est = estimate_storyboard_seconds(narrations)
    target = sb.get("duration_target_seconds")
    print(">>> [0/4] 预估时长（中文 ÷ 5.5 字/秒 + 标点停顿）")
    for i, (seg, est) in enumerate(zip(segments, pre_est["per_segment"]), start=1):
        print(f"    seg {i:2d}  {seg.get('template'):<16s}  chars≈{len(seg['narration']):3d}  est={est:5.2f}s")
    print(f"    -- total estimate = {pre_est['total_seconds']:.2f}s"
          + (f" (target={target}s)" if target else ""))
    if target:
        delta = pre_est['total_seconds'] - float(target)
        ratio = delta / float(target) * 100 if float(target) else 0.0
        print(f"    -- vs target      = {delta:+.2f}s ({ratio:+.1f}%)")
    print()

    # ============ 1. TTS ============
    print(">>> [1/4] TTS")
    cfg = TTSConfig.from_env()
    tts = GPTSoVITSTTSService(cfg)

    audio_results = []
    audio_paths: list[Path] = []
    for i, seg in enumerate(segments, start=1):
        narration = seg["narration"]
        audio_path = AUDIO_DIR / f"{task_id}_seg_{i:02d}.wav"
        # 复用已存在的 wav（调试重跑用）
        if audio_path.exists() and audio_path.stat().st_size > 1024:
            import wave, contextlib
            with contextlib.closing(wave.open(str(audio_path), "rb")) as w:
                duration = w.getnframes() / float(w.getframerate())
            print(f"    - seg {i}: {seg.get('kind')} [REUSE existing] ({duration:.2f}s)")
        else:
            print(f"    - seg {i}: {seg.get('kind')} ({len(narration)} chars)")
            result = tts.synthesize_to_file(text=narration, output_path=audio_path)
            duration = result.get("duration_seconds")
            print(f"        -> {audio_path.name}  ({duration:.2f}s)")
        audio_results.append(
            {
                "segment_index": i,
                "segment_title": seg.get("kind", "seg"),
                "narration_text": narration,
                "subtitle_text": seg.get("subtitle") or narration,
                "audio_path": str(audio_path),
                "audio_file": audio_path.name,
                "audio_duration_seconds": duration,
            }
        )
        audio_paths.append(audio_path)

    # ============ 2. 拼接 + SRT ============
    print(">>> [2/4] merge audio + SRT")
    merged_audio = AUDIO_DIR / f"{task_id}_merged.wav"
    total_dur = concat_wav(audio_paths, merged_audio)
    print(f"    merged: {merged_audio.name}  ({total_dur:.2f}s)")

    srt_path = SUBTITLE_DIR / f"{task_id}.srt"
    if use_whisper:
        print("    [align] whisper word-level alignment ...")
        try:
            aligner = WhisperAligner(model_size="small", device="cpu", compute_type="int8")
            cues = align_segments(audio_results, aligner, language="zh", verbose=True)
            info = write_aligned_srt(cues, srt_path)
            print(
                f"    srt:    {srt_path.name}  (cues={info['cue_count']}, "
                f"aligned={info['aligned_cues']}, fallback={info['fallback_cues']})"
            )
        except Exception as e:
            print(f"    !! whisper align failed: {e}")
            print(f"    -> fallback to char-ratio SRT")
            info = write_srt_file(audio_results, srt_path)
            print(f"    srt:    {srt_path.name}  ({info.get('entry_count', info.get('cue_count'))} entries) [fallback]")
    else:
        info = write_srt_file(audio_results, srt_path)
        print(f"    srt:    {srt_path.name}  ({info.get('entry_count', info.get('cue_count'))} entries) [char-ratio]")

    # ============ 3. Manim 渲染 ============
    print(">>> [3/4] Manim renders")
    video_segments = []
    for i, (seg, audio_info) in enumerate(zip(segments, audio_results), start=1):
        target_dur = audio_info["audio_duration_seconds"]
        params = dict(seg.get("params", {}))
        params["duration"] = max(3.0, target_dur)

        template = seg["template"]
        print(f"    - seg {i}: {template:<16} target={target_dur:.2f}s")
        r = render_manim_scene(
            template=template,
            params=params,
            output_filename=f"{task_id}_seg_{i:02d}_{template}",
            quality="medium",
        )
        actual = probe_duration(r["video_path"])
        kind = r.get("template_kind", "?")
        print(
            f"        -> {Path(r['video_path']).name}  actual={actual:.2f}s  kind={kind}"
        )
        video_segments.append(
            {"video_path": r["video_path"], "target_duration": target_dur}
        )

    # ============ 4. 合成 ============
    print(">>> [4/4] composition")
    final_out = FINAL_DIR / f"{task_id}_final.mp4"
    r = compose_teaching_video(
        video_segments=video_segments,
        audio_path=merged_audio,
        srt_path=srt_path,
        output_path=final_out,
        bgm_path=None,
        fps=30,
        font_size=18,
        margin_v=25,
    )

    print()
    print("[OK] storyboard pipeline 通过！")
    print(f"   产物: {r['video_path']}")
    print(f"   大小: {r['file_size_bytes'] / 1024:.1f} KB")
    print(f"   段数: {r['segments_count']}")

    # ============ 估算 vs 实测对比（A2 新增）============
    print()
    print(">>> 估算 vs 实测")
    print(f"    {'#':>2}  {'template':<16s}  {'est':>7s}  {'actual':>7s}  {'Δ':>7s}  {'err%':>6s}")
    total_est = 0.0
    total_actual = 0.0
    for i, (seg, audio_info) in enumerate(zip(segments, audio_results), start=1):
        est = estimate_narration_seconds(seg["narration"])
        actual = float(audio_info["audio_duration_seconds"] or 0.0)
        delta = actual - est
        err_pct = (delta / actual * 100) if actual > 0 else 0.0
        total_est += est
        total_actual += actual
        flag = "" if abs(err_pct) < 20 else "  !"
        print(f"    {i:>2}  {seg['template']:<16s}  {est:>6.2f}s  {actual:>6.2f}s  {delta:>+6.2f}s  {err_pct:>+5.1f}%{flag}")
    total_delta = total_actual - total_est
    total_err = (total_delta / total_actual * 100) if total_actual > 0 else 0.0
    print(f"    {'TOTAL':>20s}  {total_est:>6.2f}s  {total_actual:>6.2f}s  {total_delta:>+6.2f}s  {total_err:>+5.1f}%")
    if target:
        print(f"    {'vs target':>20s}  {float(target):>6.2f}s  {total_actual:>6.2f}s  {total_actual - float(target):>+6.2f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
