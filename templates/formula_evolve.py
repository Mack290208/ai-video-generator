"""
templates/formula_evolve.py
---------------------------
公式推导链路模板（水平版）：标题 + 一行水平排列的公式步骤，箭头连接。

布局：
- 标题在顶部
- 公式步骤水平排列在画面中央：step_1 → step_2 → step_3 → ...
- 每个公式上方有 caption（说明文字）
- 箭头连接相邻步骤
- 当前步高亮（YELLOW），最终结果用 GREEN 强调

⚠ 重要约束：
- step_X 只能是纯 LaTeX 数学表达式，不能包含中文（LaTeX 编译会失败）
- 中文说明请全部放在 caption_X 里
- 步数最多 4 步（水平排列空间有限，太多会拥挤）

参数：
    title            - 主标题（必填）
    step_1..4        - 步骤 1~4 LaTeX 公式（至少 step_1 必填）
    caption_1..4     - 步骤 1~4 说明文字（中文，可选）
    final_emphasis   - 是否把最后一步染成 GREEN 表示"最终结论"（默认 true）
    duration         - 期望总时长（秒）
"""

from __future__ import annotations

from manim import (
    Arrow,
    BLUE,
    Create,
    DOWN,
    FadeIn,
    GREEN,
    Indicate,
    MathTex,
    RIGHT,
    Scene,
    SurroundingRectangle,
    Text,
    UP,
    WHITE,
    Write,
    YELLOW,
)

from components import TitleBar
from layouts.constants import (
    FONT_ZH,
    FS_BODY,
    FS_FORMULA,
)
from templates._param import param_bool, param_float, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "step_1": {"type": "str", "required": True},
    "step_2": {"type": "str", "required": False, "default": ""},
    "step_3": {"type": "str", "required": False, "default": ""},
    "step_4": {"type": "str", "required": False, "default": ""},
    "caption_1": {"type": "str", "required": False, "default": ""},
    "caption_2": {"type": "str", "required": False, "default": ""},
    "caption_3": {"type": "str", "required": False, "default": ""},
    "caption_4": {"type": "str", "required": False, "default": ""},
    "final_emphasis": {"type": "bool", "required": False, "default": True},
    "duration": {"type": "float", "required": False, "default": 0.0},
}


TEMPLATE_META = {
    "summary": "公式逐步推导链路（水平版）：标题在顶部，1~4 步 LaTeX 公式水平排列、用箭头连接、依次淡入。当前步高亮，最终结果绿色强调。⚠ step_X 只能是纯 LaTeX 数学表达式（不能含中文），中文说明全部放在 caption_X 里。",
    "use_cases": [
        "MSE 求最优解 θ* = (XᵀX)⁻¹ Xᵀy 的推导",
        "Sigmoid 求导 σ'(x) = σ(x)(1-σ(x))",
        "贝叶斯定理 P(A|B) 展开",
        "短链推导（4 步以内）",
    ],
    "not_for": [
        "纯文字概念对比（用 concept_compare）",
        "需要画图 / 坐标系的场景（用 curve_descent）",
        "超过 4 步的超长推导（建议拆成两个模板段）",
        "step 里写中文（LaTeX 编译会报 Unicode error，请把中文挪到 caption）",
    ],
    "example_params": {
        "title": "最小二乘法推导",
        "step_1": r"\sum_i (y_i - x_i^T \theta)^2",
        "step_2": r"X^T X \theta = X^T y",
        "step_3": r"\theta^* = (X^T X)^{-1} X^T y",
        "caption_1": "残差平方和",
        "caption_2": "正规方程",
        "caption_3": "最优解",
        "duration": 16.0,
    },
}


def _gather_steps() -> list[tuple[str, str]]:
    """收集非空的 (formula, caption) 对，最多 4 步。"""
    out: list[tuple[str, str]] = []
    for i in range(1, 5):
        formula = param_str(f"step_{i}", "")
        if not formula.strip():
            continue
        caption = param_str(f"caption_{i}", "")
        out.append((formula, caption))
    return out


# 画面布局常量
# 4 步水平排列在 x ∈ [-4.5, +4.5]，留出足够边距防止溢出
CONTENT_Y = 0.0          # 公式中心 y
CAPTION_OFFSET_Y = 1.1   # caption 在公式上方多少
ARROW_BUFF = 0.85        # 箭头与公式之间的间距


class FormulaEvolveScene(Scene):
    """公式推导链路（水平箭头版）。"""

    def construct(self):
        title_text = param_str("title", "公式推导")
        final_emphasis = param_bool("final_emphasis", True)
        duration = param_float("duration", 0.0)

        steps = _gather_steps()
        if not steps:
            steps = [(r"L(\theta) = (\theta - 2)^2", "默认示例")]

        n = len(steps)

        # 字号根据步数自适应
        if n <= 2:
            formula_size = FS_FORMULA + 6
            caption_size = FS_BODY + 2
        elif n == 3:
            formula_size = FS_FORMULA + 2
            caption_size = FS_BODY
        else:  # n == 4
            formula_size = FS_FORMULA - 2
            caption_size = FS_BODY - 2

        scene_ran = 0.0

        def play_t(*anims, run_time: float = 1.0):
            nonlocal scene_ran
            self.play(*anims, run_time=run_time)
            scene_ran += run_time

        def wait_t(seconds: float):
            nonlocal scene_ran
            if seconds <= 0:
                return
            self.wait(seconds)
            scene_ran += seconds

        # ---------- 1. 主标题 ----------
        bar = TitleBar(title=title_text)
        play_t(*bar.write_anims(), run_time=1.0)

        # ---------- 2. 计算每步的 x 坐标 ----------
        # 水平区间 [-4.5, +4.5]，n 步均匀分布
        if n == 1:
            xs = [0.0]
        else:
            x_left = -4.5
            x_right = +4.5
            x_step = (x_right - x_left) / (n - 1)
            xs = [x_left + i * x_step for i in range(n)]

        # ---------- 3. 预先构造所有公式 + caption mobjects ----------
        # 计算每步可用宽度（防止 caption 文字溢出重叠）
        avail_width = (x_right - x_left) / n - 0.3 if n > 1 else 8.0

        formula_objs: list[MathTex] = []
        caption_objs: list = []
        for i, (formula, caption) in enumerate(steps):
            x = xs[i]
            f = MathTex(formula, font_size=formula_size, color=WHITE)
            f.move_to([x, CONTENT_Y, 0])
            # 如果公式太宽，缩放到可用宽度
            if f.width > avail_width:
                f.scale_to_fit_width(avail_width)
            formula_objs.append(f)

            if caption.strip():
                c = Text(
                    caption,
                    font=FONT_ZH,
                    font_size=caption_size,
                    color=BLUE,
                ).move_to([x, CONTENT_Y + CAPTION_OFFSET_Y, 0])
                # 如果 caption 太宽，自动缩小字号或截断
                if c.width > avail_width:
                    c.scale_to_fit_width(avail_width)
                caption_objs.append(c)
            else:
                caption_objs.append(None)

        # ---------- 4. 逐步淡入 + 箭头 ----------
        per_step_dur = 1.4
        prev_formula = None
        last_formula = None
        for i, (f, c) in enumerate(zip(formula_objs, caption_objs)):
            is_last = (i == len(formula_objs) - 1)
            # 当前步颜色
            if is_last and final_emphasis:
                f.set_color(GREEN)
            else:
                f.set_color(YELLOW)

            anims = []

            # 上一步淡化为 WHITE
            if prev_formula is not None:
                anims.append(prev_formula.animate.set_color(WHITE))

            # 当前公式 Write
            anims.append(Write(f))

            # 箭头：从上一个公式指向当前公式
            arrow = None
            if i > 0:
                prev_x = xs[i - 1]
                cur_x = xs[i]
                # 箭头从 prev 右沿到 cur 左沿
                arrow = Arrow(
                    start=[prev_x + ARROW_BUFF, CONTENT_Y, 0],
                    end=[cur_x - ARROW_BUFF, CONTENT_Y, 0],
                    color=WHITE,
                    stroke_width=3,
                    buff=0.4,
                    max_tip_length_to_length_ratio=0.18,
                )
                anims.append(Create(arrow))

            play_t(*anims, run_time=per_step_dur * 0.8)

            if c is not None:
                play_t(FadeIn(c, shift=DOWN * 0.1), run_time=per_step_dur * 0.4)

            prev_formula = f
            if is_last:
                last_formula = f

        # ---------- 4.5 最终步强化：一次仪式感的「形成最优解」动作 ----------
        # 如果最后一步已经有 caption（如「最优解」）就不重复加“✓ 最优解” badge，
        # 只保留高亮框 + Indicate 两个视觉强化。
        if final_emphasis and last_formula is not None and n > 1:
            last_caption_text = steps[-1][1] if steps else ""
            # caption 里出现「最优」「最小」「最大」「最终」这类词 → 不加 badge
            already_says_optimal = any(
                kw in last_caption_text
                for kw in ("最优解", "最优", "结果", "最终", "最小", "最大")
            )

            # 在最后一步周围画一个高亮框
            box = SurroundingRectangle(
                last_formula,
                color=GREEN,
                stroke_width=4,
                buff=0.25,
            )

            if already_says_optimal:
                # 只画框 + Indicate，不重复文字
                play_t(Create(box), run_time=0.7)
                play_t(Indicate(last_formula, color=GREEN, scale_factor=1.15), run_time=0.8)
            else:
                # 「✓ 最优解」标签贴在框上方
                badge = Text(
                    "✓ 最优解",
                    font=FONT_ZH,
                    font_size=caption_size,
                    color=GREEN,
                )
                badge.next_to(box, UP, buff=0.18)
                play_t(Create(box), FadeIn(badge, shift=DOWN * 0.15), run_time=0.9)
                play_t(Indicate(last_formula, color=GREEN, scale_factor=1.15), run_time=0.8)

        # ---------- 5. 收尾保持 ----------
        wait_t(1.5)

        # ---------- 6. 时长对齐 ----------
        if duration and duration > 0:
            remaining = duration - scene_ran
            if remaining > 0.1:
                self.wait(remaining)
