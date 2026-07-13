"""
run_full_pipeline_smoke.py
--------------------------
端到端冒烟：开场(Manim) + 梯度下降(Manim) + 总结(Manim) + TTS旁白 + 字幕 + 合成。

现在直接用"静态文本对应的 TTS 时长"驱动画面段时长（后续对接 Dify 时，
每段的 target_duration = server.py 产出的 merged_audio 里各 segment 时长）。

跑之前确保：
- 骨架 venv 已装 requests / python-dotenv 等（原来就装了）
- 独立 venv .venv_manim 已装 manim
- GPT-SoVITS API 在 127.0.0.1:9880 跑着，权重已切到神里绫华
- MiKTeX 已装（Manim 需要）
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

from services.manim_service import render_manim_scene
from services.tts_service import GPTSoVITSTTSService, TTSConfig
from services.subtitle_service import write_srt_file
from services.composition_service import compose_teaching_video, probe_duration


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OUT_DIR = BASE_DIR / "outputs"
AUDIO_DIR = OUT_DIR / "audio"
SUBTITLE_DIR = OUT_DIR / "subtitles"
FINAL_DIR = OUT_DIR / "video"
for d in (AUDIO_DIR, SUBTITLE_DIR, FINAL_DIR):
    d.mkdir(parents=True, exist_ok=True)


def concat_wav(paths: list[Path], out_path: Path) -> float:
    """标准库 wave 拼接。"""
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
    task_id = "smoke_pipeline"

    # ============ 1. 设计三段脚本（模拟老师提示词展开后的结果） ============
    segments = [
        {
            "kind": "intro",
            "narration": "大家好，今天我们来学习机器学习里最基础、也最重要的优化算法——梯度下降。",
            "subtitle": "大家好，今天我们来学习机器学习里最基础、也最重要的优化算法——梯度下降。",
            "manim_template": "intro",
            "manim_params": {
                "title": "机器学习课堂",
                "subtitle": "今天我们来讲：梯度下降",
            },
        },
        {
            "kind": "main",
            # 旁白版（喂给 TTS）：希腊字母换拼音
            "narration": (
                "假设我们有一个损失函数：L 西塔等于 西塔 减二 的平方。"
                "我们从一个起始参数出发，沿着梯度的反方向一步一步更新，"
                "参数会逐渐逼近最优解，也就是 西塔 等于二 这个位置。"
                "学习率阿尔法决定了每一步走多远。"
            ),
            # 字幕版（显示给学生）：保留专业符号
            "subtitle": (
                "假设我们有一个损失函数：L(θ) = (θ - 2)²。"
                "我们从一个起始参数出发，沿着梯度的反方向一步一步更新，"
                "参数会逐渐逼近最优解，也就是 θ = 2 这个位置。"
                "学习率 α 决定了每一步走多远。"
            ),
            "manim_template": "gradient_descent",
            "manim_params": {
                "title": "梯度下降",
                "func_label": r"L(\theta) = (\theta - 2)^2",
                "start_x": -2.5,
                "lr": 0.25,
                "steps": 8,
            },
        },
        {
            "kind": "outro",
            # 旁白：阿尔法
            "narration": "我们回顾一下今天的重点：第一，梯度下降沿着负梯度方向更新参数；第二，学习率阿尔法决定每一步的幅度；第三，阿尔法太小收敛慢，太大会震荡发散。",
            # 字幕：α
            "subtitle": "我们回顾一下今天的重点：第一，梯度下降沿着负梯度方向更新参数；第二，学习率 α 决定每一步的幅度；第三，α 太小收敛慢，太大会震荡发散。",
            "manim_template": "outro",
            "manim_params": {
                "title": "本节回顾",
                "point_1": "梯度下降沿负梯度方向更新参数",
                "point_2": "学习率 α 控制每一步的更新幅度",
                "point_3": "α 太小收敛慢，太大会震荡发散",
            },
        },
    ]

    # ============ 2. 对每段：生成 TTS 旁白 ============
    print(">>> [1/4] 生成 TTS 旁白...")
    cfg = TTSConfig.from_env()
    tts = GPTSoVITSTTSService(cfg)

    audio_results = []
    audio_paths: list[Path] = []
    for i, seg in enumerate(segments, start=1):
        audio_path = AUDIO_DIR / f"{task_id}_seg_{i:02d}.wav"
        print(f"    - seg {i}: {seg['kind']}  ({len(seg['narration'])} 字)")
        result = tts.synthesize_to_file(text=seg["narration"], output_path=audio_path)
        duration = result.get("duration_seconds")
        print(f"        -> {audio_path.name}  ({duration:.2f}s)")
        audio_results.append({
            "segment_index": i,
            "segment_title": seg["kind"],
            "narration_text": seg["narration"],
            "subtitle_text": seg.get("subtitle") or seg["narration"],
            "audio_path": str(audio_path),
            "audio_file": audio_path.name,
            "audio_duration_seconds": duration,
        })
        audio_paths.append(audio_path)

    # ============ 3. 拼接音频 + 生成字幕 ============
    print(">>> [2/4] 拼接音频 + 生成字幕...")
    merged_audio = AUDIO_DIR / f"{task_id}_merged.wav"
    total_dur = concat_wav(audio_paths, merged_audio)
    print(f"    merged: {merged_audio.name}  ({total_dur:.2f}s)")

    srt_path = SUBTITLE_DIR / f"{task_id}.srt"
    subtitle_info = write_srt_file(audio_results, srt_path)
    print(f"    srt:    {srt_path.name}  ({subtitle_info.get('entry_count')} 条)")

    # ============ 4. 每段渲染 Manim 画面 ============
    print(">>> [3/4] 渲染 Manim 画面...")
    video_segments = []
    for i, (seg, audio_info) in enumerate(zip(segments, audio_results), start=1):
        target_dur = audio_info["audio_duration_seconds"]
        params = dict(seg["manim_params"])
        # 对 intro / outro / gradient_descent，把 duration 传进模板（让动画本身拉伸到旁白时长）
        if seg["manim_template"] in ("intro", "outro", "gradient_descent"):
            params["duration"] = max(3.0, target_dur)
        print(f"    - seg {i}: {seg['manim_template']}  (target={target_dur:.2f}s)")
        r = render_manim_scene(
            template=seg["manim_template"],
            params=params,
            output_filename=f"{task_id}_seg_{i:02d}_{seg['manim_template']}",
            quality="medium",
        )
        actual = probe_duration(r["video_path"])
        print(f"        -> {Path(r['video_path']).name}  (actual={actual:.2f}s)")
        video_segments.append({
            "video_path": r["video_path"],
            "target_duration": target_dur,
        })

    # ============ 5. 合成最终视频 ============
    print(">>> [4/4] 合成最终视频...")
    final_out = FINAL_DIR / f"{task_id}_final.mp4"
    r = compose_teaching_video(
        video_segments=video_segments,
        audio_path=merged_audio,
        srt_path=srt_path,
        output_path=final_out,
        bgm_path=None,  # 这次冒烟先不加 BGM
        fps=30,
        font_size=22,
        margin_v=45,
    )

    print("")
    print("✅ 全流程冒烟完成！")
    print(f"   产物: {r['video_path']}")
    print(f"   大小: {r['file_size_bytes'] / 1024:.1f} KB")
    print(f"   片段数: {r['segments_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
