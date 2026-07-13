"""
test_v2_manim_only.py
---------------------
不依赖 GPT-SoVITS 的 v2 pipeline 子集测试：
- 用伪造的 target_duration（模拟 TTS 已生成）
- 走完整的 manim 渲染 + composition_service 合成
- 验证 v2 模板（intro_v2 / curve_descent）+ legacy 模板（outro）能在同一 pipeline 里混用
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from __future__ import annotations

import sys
from pathlib import Path

from services.composition_service import probe_duration
from services.manim_service import render_manim_scene


BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "outputs"
FINAL_DIR = OUT_DIR / "video"
FINAL_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    task_id = "v2_manim_only"

    # 伪造的"TTS 已知时长"
    segments = [
        {
            "kind": "intro",
            "manim_template": "intro_v2",
            "target_duration": 8.5,
            "manim_params": {
                "title": "机器学习课堂",
                "subtitle": "今天我们来讲：梯度下降",
                "show_decoration": True,
            },
        },
        {
            "kind": "main",
            "manim_template": "curve_descent",
            "target_duration": 22.0,
            "manim_params": {
                "title": "梯度下降",
                "func_label": r"L(\theta) = (\theta - 2)^2",
                "rule_label": r"\theta_{t+1} = \theta_t - \alpha \cdot \nabla L(\theta_t)",
                "start_x": -2.5,
                "lr": 0.25,
                "steps": 8,
            },
        },
        {
            "kind": "outro",
            "manim_template": "outro",  # legacy
            "target_duration": 11.0,
            "manim_params": {
                "title": "本节回顾",
                "point_1": "梯度下降沿负梯度方向更新参数",
                "point_2": "学习率 α 控制每一步的更新幅度",
                "point_3": "α 太小收敛慢，太大会震荡发散",
            },
        },
    ]

    print(">>> 渲染 Manim 各段（v2 + legacy 混合）...")
    video_segments = []
    for i, seg in enumerate(segments, start=1):
        params = dict(seg["manim_params"])
        params["duration"] = seg["target_duration"]

        print(f"  - seg {i}: {seg['manim_template']:<16} target={seg['target_duration']:.2f}s")
        r = render_manim_scene(
            template=seg["manim_template"],
            params=params,
            output_filename=f"{task_id}_seg_{i:02d}_{seg['manim_template']}",
            quality="medium",
        )
        actual = probe_duration(r["video_path"])
        kind = r.get("template_kind", "?")
        print(
            f"      -> {Path(r['video_path']).name}  actual={actual:.2f}s  kind={kind}"
        )
        video_segments.append(
            {"video_path": r["video_path"], "target_duration": seg["target_duration"]}
        )

    print("")
    print(">>> ffmpeg concat 拼接三段画面（不加音频 / 不加字幕）...")
    final_out = FINAL_DIR / f"{task_id}_concat.mp4"
    concat_list = OUT_DIR / f"{task_id}_concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{Path(s['video_path']).resolve()}'" for s in video_segments),
        encoding="utf-8",
    )

    import shutil
    import subprocess

    ffm = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffm, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-an",
        str(final_out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print("FFMPEG FAILED:")
        print(proc.stderr[-1500:])
        return 1

    size_kb = final_out.stat().st_size / 1024
    actual = probe_duration(str(final_out))
    print("")
    print("[OK] v2 Manim-only pipeline 通过！")
    print(f"   产物: {final_out}")
    print(f"   大小: {size_kb:.1f} KB")
    print(f"   总时长: {actual:.2f}s")
    print(f"   段数: {len(video_segments)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
