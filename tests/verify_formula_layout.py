"""模拟 5 步推导 + 6 步推导，打印每个 mobject 的最底端 y 坐标，验证字幕区是否被侵入。"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 把环境变量设上
def set_params(params):
    for k, v in params.items():
        os.environ["MANIM_PARAM_" + k.upper()] = str(v)

# 5 步
set_params({
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
})

# 用 manim 测出 mobject 的边界
from manim import MathTex, Text
from layouts.constants import FONT_ZH, FS_BODY, FS_FORMULA, SUBTITLE_TOP_Y
from templates.formula_evolve import _layout_y, _gather_steps

steps = _gather_steps()
n = len(steps)
print(f"步数: {n}")

if n <= 3:
    formula_size, caption_size = FS_FORMULA + 4, FS_BODY
elif n == 4:
    formula_size, caption_size = FS_FORMULA, FS_BODY - 2
else:
    formula_size, caption_size = FS_FORMULA - 4, FS_BODY - 4

top_y, gap = _layout_y(n)
print(f"top_y={top_y}, gap={gap}")
print(f"SUBTITLE_TOP_Y={SUBTITLE_TOP_Y}（不能低于这条线）")
print()

for i, (formula, caption) in enumerate(steps):
    y = top_y - i * gap
    f = MathTex(formula, font_size=formula_size)
    f.move_to([0, y, 0])
    f_bottom = f.get_bottom()[1]

    if caption.strip():
        c = Text(caption, font=FONT_ZH, font_size=caption_size)
        c.next_to(f, [0, -1, 0], buff=0.18)
        c_bottom = c.get_bottom()[1]
        marker = "!! BAD" if c_bottom < SUBTITLE_TOP_Y else "OK"
        print(f"  step {i+1}: formula y={y:.2f} bottom={f_bottom:.2f} | caption bottom={c_bottom:.2f}  {marker}")
    else:
        marker = "!! BAD" if f_bottom < SUBTITLE_TOP_Y else "OK"
        print(f"  step {i+1}: formula y={y:.2f} bottom={f_bottom:.2f}  {marker}")

print("\nsubtitle hard-burn position: margin_v=45px in 480p, y in [-3.4, -2.95]")
print(f"SUBTITLE_TOP_Y={SUBTITLE_TOP_Y}, content bottom must be > this")
