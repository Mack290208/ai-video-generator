"""
templates/lr_comparison.py
--------------------------
学习率对比模板：左右分屏，同一损失函数下两个不同 α 的下降轨迹同时跑。

教学价值（Mack 5-12 备注："最有教学价值"）：
- 左：α 太小，收敛慢，步子小
- 右：α 较大（甚至太大），步子大或震荡

复用：
- TitleBar
- CoordPlot × 2（用 center_offset 把两个坐标系一左一右放）
- InfoPanel × 0（这个模板没有右侧栏，参数标在每个坐标系上方）

参数：
    title          - 主标题
    func_label     - 主公式 LaTeX
    func_kind      - 函数族（quadratic_centered_at_2 / _at_0）
    x_min/x_max    - x 范围
    y_min/y_max    - y 范围
    start_x        - 共同起点
    lr_left        - 左侧学习率（推荐小一点，如 0.05）
    lr_left_label  - 左侧标签文本（如 "α=0.05 (太小)"）
    lr_right       - 右侧学习率（推荐大一点，如 0.7）
    lr_right_label - 右侧标签文本（如 "α=0.7  (合适)"）
    steps          - 每边迭代步数
    var            - 参数名（默认 \\theta）
    duration       - 期望总时长

注：这个模板不用 layouts.MAIN_CENTER_X，自己计算左右两侧位置。
"""

from __future__ import annotations

from typing import Callable, Tuple

from manim import (
    BLUE,
    Dot,
    FadeIn,
    GREEN,
    LEFT,
    ORANGE,
    RIGHT,
    Scene,
    Text,
    WHITE,
    Write,
    YELLOW,
    Axes,
    MathTex,
    Create,
    UP,
    DOWN,
)

from components import TitleBar
from layouts.constants import (
    AXES_X_LENGTH,
    AXES_Y_LENGTH,
    FONT_ZH,
    FS_AXIS,
    FS_BODY,
    FS_PARAM,
    SUBTITLE_TOP_Y,
)
from templates._param import param_float, param_int, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "func_label": {"type": "str", "required": True},
    "func_kind": {
        "type": "str",
        "required": False,
        "default": "quadratic_centered_at_2",
        "allowed": ["quadratic_centered_at_2", "quadratic_centered_at_0"],
    },
    "x_min": {"type": "float", "required": False, "default": -3.0},
    "x_max": {"type": "float", "required": False, "default": 5.0},
    "y_min": {"type": "float", "required": False, "default": 0.0},
    "y_max": {"type": "float", "required": False, "default": 12.0},
    "start_x": {"type": "float", "required": False, "default": -2.5},
    "lr_left": {"type": "float", "required": False, "default": 0.05},
    "lr_left_label": {"type": "str", "required": False, "default": "α=0.05 (太小)"},
    "lr_right": {"type": "float", "required": False, "default": 0.7},
    "lr_right_label": {"type": "str", "required": False, "default": "α=0.7  (合适)"},
    "steps": {"type": "int", "required": False, "default": 8},
    "var": {"type": "str", "required": False, "default": r"\theta"},
    "pre_wait": {"type": "float", "required": False, "default": 0.0},
    "duration": {"type": "float", "required": False, "default": 0.0},
}

TEMPLATE_META = {
    "summary": "左右分屏，同一损失函数下两个不同超参数的下降轨迹同时跑，直接看出差异。",
    "use_cases": [
        "学习率 α 太小 vs 合适 vs 太大",
        "有/无动量 vs 有动量的收敛差异",
        "不同初始点导致不同汇量的对比",
        "任何“使用超参数 A vs B 看下降效果”的对比演示",
    ],
    "not_for": [
        "需要右侧信息栏变量详情的场景（请用 curve_descent）",
        "超过两种变体的对比（暂不支持）",
    ],
    "example_params": {
        "title": "学习率的影响",
        "func_label": r"L(\theta) = (\theta - 2)^2",
        "lr_left": 0.05,
        "lr_left_label": "α=0.05 (太小)",
        "lr_right": 0.7,
        "lr_right_label": "α=0.7  (合适)",
        "steps": 8,
    },
}


def _build_func(kind: str) -> Tuple[Callable[[float], float], Callable[[float], float]]:
    if kind == "quadratic_centered_at_0":
        return (lambda x: x ** 2), (lambda x: 2.0 * x)
    return (lambda x: (x - 2.0) ** 2), (lambda x: 2.0 * (x - 2.0))


def _make_panel(
    func: Callable[[float], float],
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    var: str,
    center_x: float,
    color,
) -> Tuple[Axes, MathTex, MathTex]:
    """构造单侧的（坐标系, x_label, y_label, curve）。"""
    axes = Axes(
        x_range=[x_range[0], x_range[1], 1],
        y_range=[y_range[0], y_range[1], 2],
        x_length=AXES_X_LENGTH * 0.45,   # 一边只占 45% 宽度
        y_length=AXES_Y_LENGTH * 0.85,
        axis_config={
            "color": WHITE,
            "include_numbers": True,
            "font_size": FS_AXIS - 4,    # 小一些避免拥挤
        },
        tips=False,
    )
    axes.move_to([center_x, -0.1, 0])
    x_label = MathTex(var, font_size=FS_BODY + 4).next_to(axes.x_axis, RIGHT, buff=0.15)
    y_label = MathTex("L", font_size=FS_BODY + 4).next_to(axes.y_axis, UP, buff=0.15)
    curve = axes.plot(func, x_range=[x_range[0], x_range[1]], color=color)
    return axes, x_label, y_label, curve


class LrComparisonScene(Scene):
    """学习率对比：左右两个坐标系并行跑梯度下降。"""

    def construct(self):
        title_text = param_str("title", "学习率的影响")
        func_label = param_str("func_label", r"L(\theta) = (\theta - 2)^2")
        func_kind = param_str("func_kind", "quadratic_centered_at_2")
        x_min = param_float("x_min", -3.0)
        x_max = param_float("x_max", 5.0)
        y_min = param_float("y_min", 0.0)
        y_max = param_float("y_max", 12.0)
        start_x = param_float("start_x", -2.5)
        lr_left = param_float("lr_left", 0.05)
        lr_right = param_float("lr_right", 0.7)
        lr_left_label = param_str("lr_left_label", "α=0.05 (太小)")
        lr_right_label = param_str("lr_right_label", "α=0.7  (合适)")
        steps = param_int("steps", 8)
        var = param_str("var", r"\theta")
        pre_wait = param_float("pre_wait", 0.0)
        duration = param_float("duration", 0.0)

        f, grad = _build_func(func_kind)

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

        # 1. 标题
        bar = TitleBar(title=title_text)
        play_t(*bar.write_anims(), run_time=1.0)

        # 2. 主公式（标题下方居中）
        formula = MathTex(func_label, font_size=FS_PARAM, color=BLUE)
        formula.move_to([0, 2.45, 0])
        play_t(Write(formula), run_time=0.8)

        # 3. 左右两套坐标系（左 x≈-3.6，右 x≈+3.6）
        left_axes, lx_label, ly_label, left_curve = _make_panel(
            f, (x_min, x_max), (y_min, y_max), var, center_x=-3.6, color=BLUE
        )
        right_axes, rx_label, ry_label, right_curve = _make_panel(
            f, (x_min, x_max), (y_min, y_max), var, center_x=+3.6, color=BLUE
        )

        # 各侧标签（坐标系下方，绝不低于字幕区）
        left_lr_text = Text(
            lr_left_label, font=FONT_ZH, font_size=FS_PARAM - 4, color=ORANGE
        )
        left_lr_text.move_to([-3.6, SUBTITLE_TOP_Y + 0.25, 0])

        right_lr_text = Text(
            lr_right_label, font=FONT_ZH, font_size=FS_PARAM - 4, color=YELLOW
        )
        right_lr_text.move_to([+3.6, SUBTITLE_TOP_Y + 0.25, 0])

        play_t(
            Create(left_axes), Create(right_axes),
            FadeIn(lx_label), FadeIn(ly_label),
            FadeIn(rx_label), FadeIn(ry_label),
            run_time=1.2,
        )
        play_t(
            Create(left_curve), Create(right_curve),
            FadeIn(left_lr_text), FadeIn(right_lr_text),
            run_time=1.2,
        )

        # 4. 起点 dot
        left_x = start_x
        right_x = start_x
        left_dot = Dot(point=left_axes.c2p(left_x, f(left_x)), color=ORANGE, radius=0.10)
        right_dot = Dot(point=right_axes.c2p(right_x, f(right_x)), color=YELLOW, radius=0.10)
        play_t(FadeIn(left_dot), FadeIn(right_dot), run_time=0.4)

        # 4.5 pre_wait：为 narration 里说到“两者作比较”之前的导词部分预留时间
        # driver 会根据 narration 关键词位置估算该值，driver 传入 pre_wait。
        if pre_wait > 0:
            wait_t(pre_wait)

        # 5. 同步迭代（左右一起跑）
        for step in range(1, steps + 1):
            # 左：α 小
            gl = grad(left_x)
            new_left_x = left_x - lr_left * gl
            new_left_x = max(x_min + 0.1, min(x_max - 0.1, new_left_x))

            # 右：α 大
            gr = grad(right_x)
            new_right_x = right_x - lr_right * gr
            # 右侧不裁剪 y——若震荡就让它震
            if new_right_x < x_min + 0.1:
                new_right_x = x_min + 0.1
            if new_right_x > x_max - 0.1:
                new_right_x = x_max - 0.1

            # 留下淡轨迹点
            left_trail = Dot(
                point=left_axes.c2p(left_x, f(left_x)),
                color=GREEN, radius=0.05,
            ).set_opacity(0.5)
            right_trail = Dot(
                point=right_axes.c2p(right_x, f(right_x)),
                color=GREEN, radius=0.05,
            ).set_opacity(0.5)

            play_t(
                FadeIn(left_trail),
                FadeIn(right_trail),
                left_dot.animate.move_to(left_axes.c2p(new_left_x, f(new_left_x))),
                right_dot.animate.move_to(right_axes.c2p(new_right_x, f(new_right_x))),
                run_time=0.55,
            )
            left_x = new_left_x
            right_x = new_right_x

        # 6. 收尾保持
        wait_t(1.5)

        # 7. 时长对齐
        if duration and duration > 0:
            remaining = duration - scene_ran
            if remaining > 0.1:
                self.wait(remaining)
