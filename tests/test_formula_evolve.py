import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

1|"""test_formula_evolve.py - 第 2 个新模板烟雾测试"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.manim_service import list_templates, render_manim_scene

print("=" * 60)
print("[1] 模板列表")
print("=" * 60)
for tid, meta in list_templates().items():
    print(f"  - [{meta['kind']:6}] {tid}")
print()

print("=" * 60)
print("[2] 渲染：最小二乘法推导（5 步）")
print("=" * 60)
r = render_manim_scene(
    "formula_evolve",
    params={
        "title": "最小二乘法推导",
        "step_1": r"L(\theta) = \sum_i (y_i - x_i^T \theta)^2",
        "step_2": r"\nabla_\theta L = -2 X^T (y - X\theta)",
        "step_3": r"\nabla_\theta L = 0",
        "step_4": r"X^T X \theta = X^T y",
        "step_5": r"\theta^* = (X^T X)^{-1} X^T y",
        "caption_1": "定义损失函数（残差平方和）",
        "caption_2": "对 θ 求梯度",
        "caption_3": "令梯度等于零",
        "caption_4": "整理为正规方程",
        "caption_5": "解出最优解 θ*",
        "duration": 22.0,
    },
    quality="low",
    output_filename="formula_evolve_smoke",
)
print(f"  [OK] {r['video_path']}")
print(f"  size = {r['file_size_bytes']} bytes")
print()
print("[DONE] formula_evolve 通过！")
