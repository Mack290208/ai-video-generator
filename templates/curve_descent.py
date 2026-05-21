"""
templates/curve_descent.py
--------------------------
"曲线下降"教学模板：在一条函数曲线上做迭代式参数更新动画。

适用知识点（参数化即可复用）：
- 梯度下降 / 随机梯度下降（凸函数）
- 牛顿法（替换 update_func）
- 学习率对比（同模板跑两次不同 lr）
- 任意"沿曲线一步步逼近极值"的演示

参数（由 manim_service 通过 params dict 注入，用 templates._param 读取）：
    title         - 主标题
    func_label    - 主公式 LaTeX，如 L(\theta)=(\theta-2)^2
    rule_label    - 更新规则 LaTeX，可选
    x_min/x_max   - x 范围
    y_min/y_max   - y 范围
    start_x       - 起点
    lr            - 学习率
    steps         - 迭代步数
    var           - 参数名（默认 \theta）
    func_kind     - 函数类型（默认 quadratic_centered_at_2，详见 _build_func）
    duration      - 期望总时长（秒）

参数 schema（给 LLM 用）：
    {
      "title": str,
      "func_label": str,           # LaTeX
      "rule_label": str | null,    # LaTeX，None 则不显示
      "x_min": float, "x_max": float,
      "y_min": float, "y_max": float,
      "start_x": float,
      "lr": float,
      "steps": int,
      "var": str,                  # 默认 "\\theta"
      "func_kind": str,            # quadratic_centered_at_2 | quadratic | abs | ...
      "duration": float,
    }
"""

from __future__ import annotations

from typing import Callable, Tuple

from manim import (
    BLUE,
    Dot,
    FadeIn,
    FadeOut,
    GREEN,
    MathTex,
    Scene,
    Write,
    YELLOW,
)

from components import CoordPlot, InfoPanel, TitleBar
from layouts.constants import FS_BODY
from templates._param import param_float, param_int, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "func_label": {"type": "str", "required": True},
    "rule_label": {"type": "str", "required": False, "default": None},
    "x_min": {"type": "float", "required": False, "default": -3.0},
    "x_max": {"type": "float", "required": False, "default": 5.0},
    "y_min": {"type": "float", "required": False, "default": 0.0},
    "y_max": {"type": "float", "required": False, "default": 12.0},
    "start_x": {"type": "float", "required": False, "default": -2.5},
    "lr": {"type": "float", "required": False, "default": 0.25},
    "steps": {"type": "int", "required": False, "default": 8},
    "var": {"type": "str", "required": False, "default": r"\theta"},
    "func_kind": {
        "type": "str",
        "required": False,
        "default": "quadratic_centered_at_2",
        "allowed": ["quadratic_centered_at_2", "quadratic_centered_at_0"],
    },
    "duration": {"type": "float", "required": False, "default": 0.0},
}

TEMPLATE_META = {
    "summary": "一条函数曲线 + 一个迭代点逐步下降，可参数化表达多种优化算法。",
    "use_cases": [
        "梯度下降 Gradient Descent",
        "随机梯度下降 SGD",
        "牛顿法（重定义 grad 为二阶装使用，或加新 func_kind）",
        "任何“沿曲线向极值点逐步逼近”的演示",
    ],
    "not_for": [
        "多变量调优（3D 处理）",
        "对比两种不同超参数（请用 lr_comparison）",
    ],
    "example_params": {
        "title": "梯度下降",
        "func_label": r"L(\theta) = (\theta - 2)^2",
        "start_x": -2.5,
        "lr": 0.25,
        "steps": 8,
    },
}


def _build_func(kind: str) -> Tuple[Callable[[float], float], Callable[[float], float]]:
    """根据 func_kind 返回 (f, gradient)。

    新增函数族在这里加 case，模板代码不动。
    """
    if kind == "quadratic_centered_at_2":
        return (lambda x: (x - 2.0) ** 2), (lambda x: 2.0 * (x - 2.0))
    if kind == "quadratic_centered_at_0":
        return (lambda x: x ** 2), (lambda x: 2.0 * x)
    # fallback
    return (lambda x: (x - 2.0) ** 2), (lambda x: 2.0 * (x - 2.0))


class CurveDescentScene(Scene):
    """沿曲线迭代下降的通用模板。"""

    def construct(self):
        # ---- 读参数 ----
        title_text = param_str("title", "梯度下降 Gradient Descent")
        func_label = param_str("func_label", r"L(\theta) = (\theta - 2)^2")
        rule_label = param_str(
            "rule_label",
            r"\theta_{t+1} = \theta_t - \alpha \cdot \nabla L(\theta_t)",
        )
        x_min = param_float("x_min", -3.0)
        x_max = param_float("x_max", 5.0)
        y_min = param_float("y_min", 0.0)
        y_max = param_float("y_max", 12.0)
        start_x = param_float("start_x", -2.5)
        lr = param_float("lr", 0.25)
        steps = param_int("steps", 8)
        var = param_str("var", r"\theta")
        func_kind = param_str("func_kind", "quadratic_centered_at_2")
        duration = param_float("duration", 0.0)

        f, grad = _build_func(func_kind)

        # ---- 时长追踪（继承昨天的 play_and_track 模式）----
        scene_ran = 0.0

        def play_track(*anims, run_time: float = 1.0):
            nonlocal scene_ran
            self.play(*anims, run_time=run_time)
            scene_ran += run_time

        def wait_track(seconds: float):
            nonlocal scene_ran
            if seconds <= 0:
                return
            self.wait(seconds)
            scene_ran += seconds

        # =========================================================
        # 1. 标题
        # =========================================================
        bar = TitleBar(title=title_text)
        play_track(*bar.write_anims(), run_time=1.0)

        # =========================================================
        # 2. 坐标系 + 曲线
        # =========================================================
        plot = CoordPlot(
            func=f,
            x_range=(x_min, x_max),
            y_range=(y_min, y_max),
            x_label=var,
            y_label="L",
            curve_color=BLUE,
        )
        play_track(*plot.create_anims(), run_time=1.2)
        play_track(plot.draw_curve_anim(), run_time=1.5)

        # =========================================================
        # 3. 信息栏：公式 + 更新规则 + 参数
        # =========================================================
        panel = InfoPanel()
        panel.set_formula(func_label, color=BLUE)
        if rule_label and rule_label.strip():
            panel.set_rule(rule_label)
        panel.set_param(rf"\alpha = {lr}", color=YELLOW)

        slots_to_show = ["formula", "param"]
        if rule_label and rule_label.strip():
            slots_to_show.insert(1, "rule")
        play_track(*panel.fadein_anims_for(slots_to_show), run_time=0.8)

        # =========================================================
        # 4. 起点：dot + 当前 θ 值（信息栏 value 槽）
        # =========================================================
        current_x = start_x
        dot = Dot(point=plot.c2p(current_x, f(current_x)), color=YELLOW, radius=0.11)
        play_track(FadeIn(dot), run_time=0.4)

        panel.set_value(rf"{var}_0 = {current_x:.2f}", color=YELLOW)
        play_track(*panel.write_anims_for(["value"]), run_time=0.5)

        # =========================================================
        # 5. 迭代下降
        # =========================================================
        for step in range(1, steps + 1):
            g = grad(current_x)
            next_x = current_x - lr * g
            # 防越界
            if next_x < x_min + 0.1:
                next_x = x_min + 0.1
            if next_x > x_max - 0.1:
                next_x = x_max - 0.1

            # 留下淡绿色轨迹点
            trail = Dot(
                point=plot.c2p(current_x, f(current_x)),
                color=GREEN,
                radius=0.06,
            ).set_opacity(0.6)

            # 当前值刷新
            value_anims = panel.update_value(
                rf"{var}_{{{step}}} = {next_x:.3f}", color=YELLOW
            )

            play_track(
                FadeIn(trail),
                dot.animate.move_to(plot.c2p(next_x, f(next_x))),
                *value_anims,
                run_time=0.55,
            )
            current_x = next_x

        # =========================================================
        # 6. 收敛提示（信息栏底部）
        # =========================================================
        panel.set_result_zh(
            f"收敛结果：θ ≈ {current_x:.3f}", color=GREEN, font_size=FS_BODY
        )
        play_track(*panel.write_anims_for(["result"]), run_time=1.2)

        # =========================================================
        # 7. 收尾保持 + 时长对齐
        # =========================================================
        wait_track(1.8)

        if duration and duration > 0:
            remaining = duration - scene_ran
            if remaining > 0.1:
                self.wait(remaining)
