"""
run_manim_smoke.py
------------------
冒烟测试：用独立 Manim venv 渲染一段梯度下降教学动画。

用前提条件：
- 独立 venv 已装好 manim（见 .venv_manim/）
- 可选：在 .env 或环境变量里设 MANIM_PYTHON

直接运行（用骨架 venv / 系统 python 都行，它只是个调度脚本）：
    python run_manim_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from services.manim_service import render_manim_scene


def main() -> int:
    print(">>> 开始渲染梯度下降冒烟测试...")
    try:
        result = render_manim_scene(
            template="gradient_descent",
            params={
                "title": "梯度下降 · 冒烟测试",
                "func_label": r"L(\theta) = (\theta - 2)^2",
                "start_x": -2.5,
                "lr": 0.25,
                "steps": 8,
            },
            output_filename="gd_smoke",
            quality="medium",  # 720p30
        )
    except Exception as e:
        print(f"❌ 渲染失败: {e}")
        return 1

    print("✅ 渲染成功！")
    print(f"   产物: {result['video_path']}")
    print(f"   大小: {result['file_size_bytes']} bytes")
    print(f"   模板: {result['template']} / Scene: {result['scene']}")
    print(f"   画质: {result['quality']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
