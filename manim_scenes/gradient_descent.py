"""
gradient_descent.py
-------------------
梯度下降教学动画模板（布局优化版 v2）。

运行方式（由 manim_service.py 通过 subprocess 调用）：
    python -m manim -qm manim_scenes/gradient_descent.py GradientDescentScene

可通过环境变量定制：
    MANIM_GD_FUNC_LABEL   显示的函数标签
    MANIM_GD_X_MIN / MAX  x 轴范围（默认 -3 ~ 5）
    MANIM_GD_Y_MIN / MAX  y 轴范围（默认  0 ~ 12）
    MANIM_GD_START_X      起点 θ₀（默认 -2.5）
    MANIM_GD_LR           学习率 α（默认 0.25）
    MANIM_GD_STEPS        迭代步数（默认 8）
    MANIM_GD_TITLE        标题文字

布局说明（16:9 画面，帧宽 14.22，帧高 8.0）：

    ┌────────────────────────────────────────────────┐  y ≈ +4
    │              标题 Title                         │  y ≈ +3.4
    ├────────────────────────────────────────────────┤
    │  L(θ)=(θ-2)²                                    │  公式标签（左上）y ≈ +2.6
    │                                                 │
    │            ┌─────────────┐                      │
    │            │             │  <- 坐标系 y_length=4 │  y ≈ -1.6 ~ +2.4
    │            │    曲线     │                      │
    │            │             │                      │
    │            └─────────────┘                      │
    ├────────────────────────────────────────────────┤
    │ θₜ₊₁ = θₜ - α∇L(θₜ)   α=0.25                     │  y ≈ -2.8
    │ 收敛: θ ≈ 2.000  θ* = 2                          │  y ≈ -3.5
    └────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os

from manim import (
    BLUE,
    DOWN,
    GREEN,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    WHITE,
    YELLOW,
    Axes,
    Create,
    Dot,
    FadeIn,
    FadeOut,
    MathTex,
    Scene,
    Text,
    VGroup,
    Write,
)


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v


class GradientDescentScene(Scene):
    """梯度下降动画：参数沿损失曲面一步步滑向极小值。"""

    def construct(self):
        # ---- 读取参数 ----
        title_text = _env_str("MANIM_GD_TITLE", "梯度下降 Gradient Descent")
        func_label = _env_str(
            "MANIM_GD_FUNC_LABEL", r"L(\theta) = (\theta - 2)^2"
        )
        x_min = _env_float("MANIM_GD_X_MIN", -3.0)
        x_max = _env_float("MANIM_GD_X_MAX", 5.0)
        y_min = _env_float("MANIM_GD_Y_MIN", 0.0)
        y_max = _env_float("MANIM_GD_Y_MAX", 12.0)
        start_x = _env_float("MANIM_GD_START_X", -2.5)
        lr = _env_float("MANIM_GD_LR", 0.25)
        steps = _env_int("MANIM_GD_STEPS", 8)
        # 期望总时长（秒），0 表示不拉伸 ——
        # 将 run_time 和 wait 按比例缩放，让最终时长 ≈ duration。
        duration = _env_float("MANIM_GD_DURATION", 0.0)

        # ---- 目标函数 ----
        def f(x: float) -> float:
            return (x - 2.0) ** 2

        def grad(x: float) -> float:
            return 2.0 * (x - 2.0)

        # ---- 时长对齐策略 ----
        # 模板先按固定速度跑完所有动画（每个 play 的 run_time 不改），
        # 记录完成时间；最后如果比 target 短，就用 self.wait(差值) 补齐。
        # 这样 Manim 内部生成的视频时长 ≈ target，合成器就不需要 setpts 变速。

        scene_ran_seconds = 0.0

        def play_and_track(*anims, run_time: float = 1.0):
            nonlocal scene_ran_seconds
            self.play(*anims, run_time=run_time)
            scene_ran_seconds += run_time

        def wait_and_track(seconds: float):
            nonlocal scene_ran_seconds
            if seconds <= 0:
                return
            self.wait(seconds)
            scene_ran_seconds += seconds

        # =========================================================
        # 上方：标题（独占顶部一行）
        # =========================================================
        title = Text(title_text, font_size=34, font="Microsoft YaHei")
        title.move_to(UP * 3.4)
        play_and_track(Write(title), run_time=1.0)

        # =========================================================
        # 中间：坐标系 + 曲线（主视觉区）
        # 坐标系略偏左，右侧留给信息栏（公式/参数/值）
        # 骨麻注意：整个画面内容不得低于 y = -2.8，底部留给字幕专用。
        # =========================================================
        axes = Axes(
            x_range=[x_min, x_max, 1],
            y_range=[y_min, y_max, 2],
            x_length=7.8,
            y_length=4.2,
            axis_config={"color": WHITE, "include_numbers": True, "font_size": 22},
            tips=False,
        ).move_to(LEFT * 1.9 + UP * 0.3)

        x_label = MathTex(r"\theta", font_size=30).next_to(axes.x_axis, RIGHT, buff=0.2)
        y_label = MathTex("L", font_size=30).next_to(axes.y_axis, UP, buff=0.2)

        play_and_track(Create(axes), FadeIn(x_label), FadeIn(y_label), run_time=1.2)

        # 损失曲线
        curve = axes.plot(f, x_range=[x_min, x_max], color=BLUE)
        # 公式标签：右侧信息栏顶部
        curve_label = MathTex(func_label, font_size=32, color=BLUE)
        curve_label.move_to(RIGHT * 4.6 + UP * 2.3)
        play_and_track(Create(curve), Write(curve_label), run_time=1.5)

        # =========================================================
        # 右侧信息栏（自上而下）：
        #   曲线公式  L(θ) = ...   (y ≈ +2.3，上面已有)
        #   更新规则  θ₁ = θ₀ - α·∇L    (y ≈ +0.8)
        #   学习率    α = 0.25                 (y ≈ +0.0)
        #   当前参数  θₖ = ...                (y ≈ -0.9, 动态刷新)
        #   收敛提示   (最后显示)          (y ≈ -1.8)
        # 严格控制不低于 y = -2.8，给底部字幕让出空间
        # =========================================================
        update_rule = MathTex(
            r"\theta_{t+1} = \theta_t - \alpha \cdot \nabla L(\theta_t)",
            font_size=26,
        )
        update_rule.move_to(RIGHT * 4.6 + UP * 0.8)

        lr_label = MathTex(rf"\alpha = {lr}", font_size=28, color=YELLOW)
        lr_label.move_to(RIGHT * 4.6 + UP * 0.0)

        play_and_track(FadeIn(update_rule), FadeIn(lr_label), run_time=0.8)

        # =========================================================
        # 迭代下降：点在曲线上，标签放在坐标系右侧专用位置（不遮曲线）
        # =========================================================
        current_x = start_x
        dot = Dot(point=axes.c2p(current_x, f(current_x)), color=YELLOW, radius=0.11)
        play_and_track(FadeIn(dot), run_time=0.4)

        # 当前 θ 值显示在右侧信息栏（固定位置，每步刷新）
        theta_display = MathTex(
            rf"\theta_0 = {current_x:.2f}", font_size=30, color=YELLOW
        )
        theta_display.move_to(RIGHT * 4.6 + DOWN * 0.9)
        play_and_track(Write(theta_display), run_time=0.5)

        # 历史点轨迹（小一些、淡绿色，不加标签避免拥挤）
        trail_points = [dot.copy()]

        for step in range(1, steps + 1):
            g = grad(current_x)
            next_x = current_x - lr * g
            # 防越界
            if next_x < x_min + 0.1:
                next_x = x_min + 0.1
            if next_x > x_max - 0.1:
                next_x = x_max - 0.1

            new_point = axes.c2p(next_x, f(next_x))
            trail_dot = Dot(point=axes.c2p(current_x, f(current_x)),
                            color=GREEN, radius=0.06).set_opacity(0.6)
            trail_points.append(trail_dot)

            # 新的 θ 标签（刷新右侧固定位置）
            new_theta_display = MathTex(
                rf"\theta_{{{step}}} = {next_x:.3f}", font_size=30, color=YELLOW
            )
            new_theta_display.move_to(RIGHT * 4.6 + DOWN * 0.9)

            play_and_track(
                FadeIn(trail_dot),
                dot.animate.move_to(new_point),
                FadeOut(theta_display, run_time=0.3),
                FadeIn(new_theta_display, run_time=0.3),
                run_time=0.55,
            )

            theta_display = new_theta_display
            current_x = next_x

        # =========================================================
        # 收敛总结（放在右侧信息栏底部，绝不低于 y = -2.5）
        # =========================================================
        final_zh = Text(
            f"收敛结果：θ ≈ {current_x:.3f}",
            font_size=22,
            font="Microsoft YaHei",
            color=GREEN,
        )
        final_zh.move_to(RIGHT * 4.6 + DOWN * 1.9)
        play_and_track(Write(final_zh), run_time=1.2)

        # 基线 wait
        wait_and_track(1.8)

        # ---- 补齐到目标时长 ----
        if duration and duration > 0:
            remaining = duration - scene_ran_seconds
            if remaining > 0.1:
                # 演示收敛以后让学生有时间回味
                self.wait(remaining)
