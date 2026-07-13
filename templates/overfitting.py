"""
templates/overfitting.py
--------------------------
过拟合可视化模板：展示训练误差 vs 验证误差曲线

适用知识点：
- 过拟合概念
- 欠拟合
- 模型复杂度
- 正则化

参数：
    title         - 主标题
    epochs        - 训练轮数
    complexity    - 模型复杂度（1-5，影响过拟合程度）
    duration      - 期望总时长（秒）
"""

from __future__ import annotations
import numpy as np
from manim import (
    Scene, Create, FadeIn, Write,
    Axes, VGroup, Text, MathTex,
    BLUE, GREEN, YELLOW, WHITE, RED, ORANGE,
    LEFT, RIGHT, UP, DOWN,
)
from components import TitleBar
from layouts.constants import FONT_ZH, FS_BODY
from templates._param import param_float, param_int, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "epochs": {"type": "int", "required": False, "default": 50},
    "complexity": {"type": "int", "required": False, "default": 3},
    "duration": {"type": "float", "required": False, "default": 0.0},
}

TEMPLATE_META = {
    "summary": "过拟合可视化，展示训练误差和验证误差的变化趋势",
    "use_cases": [
        "过拟合概念",
        "欠拟合",
        "模型复杂度选择",
        "正则化原理",
    ],
    "not_for": [
        "具体算法实现",
        "超参数调优细节",
    ],
}


class OverfittingScene(Scene):
    def construct(self):
        title = param_str("title", "过拟合现象")
        epochs = param_int("epochs", 50)
        complexity = param_int("complexity", 3)
        duration = param_float("duration", 0.0)

        # 标题
        title_bar = TitleBar(title)
        self.play(*title_bar.write_anims(), run_time=1.0)
        self.wait(0.5)

        # 创建坐标系
        axes = Axes(
            x_range=[0, epochs, epochs // 5],
            y_range=[0, 1.0, 0.2],
            x_length=10,
            y_length=5,
            axis_config={"include_numbers": True},
        )
        axes.move_to([0, -0.5, 0])

        x_label = Text("训练轮数", font_size=18, font=FONT_ZH)
        x_label.next_to(axes.x_axis, DOWN, buff=0.3)
        y_label = Text("误差", font_size=18, font=FONT_ZH)
        y_label.next_to(axes.y_axis, LEFT, buff=0.3)

        self.play(Create(axes), Write(x_label), Write(y_label))
        self.wait(0.5)

        # 生成误差曲线数据
        x_vals = np.linspace(1, epochs, 100)

        # 训练误差：单调递减
        train_error = 0.8 * np.exp(-0.05 * x_vals) + 0.05

        # 验证误差：先降后升（过拟合）
        complexity_factor = complexity * 0.15
        val_error = 0.8 * np.exp(-0.03 * x_vals) + 0.1 + complexity_factor * (x_vals / epochs) ** 2

        # 绘制曲线 - 训练误差用实线，验证误差用不同样式
        train_curve = axes.plot_line_graph(
            x_values=x_vals,
            y_values=train_error,
            line_color=BLUE,
            stroke_width=3,
        )

        # 验证误差用虚线效果
        val_curve = axes.plot_line_graph(
            x_values=x_vals,
            y_values=val_error,
            line_color=RED,
            stroke_width=3,
        )
        # 将验证误差曲线转换为虚线样式
        from manim import DashedVMobject
        val_dashed = DashedVMobject(val_curve["line_graph"], num_dashes=20, dashed_ratio=0.5)

        # 图例
        train_legend = Text("训练误差（实线）", font_size=16, font=FONT_ZH, color=BLUE)
        train_legend.move_to([3, 3, 0])
        val_legend = Text("验证误差（虚线）", font_size=16, font=FONT_ZH, color=ORANGE)
        val_legend.next_to(train_legend, DOWN, buff=0.3)

        # 动画
        self.play(Create(train_curve), run_time=1.5)
        self.play(Write(train_legend), run_time=0.5)
        self.play(Create(val_dashed), run_time=1.5)
        self.play(Write(val_legend), run_time=0.5)

        # 标记过拟合点
        overfit_x = epochs * 0.6
        overfit_y = 0.8 * np.exp(-0.03 * overfit_x) + 0.1 + complexity_factor * (overfit_x / epochs) ** 2
        overfit_point = axes.coords_to_point(overfit_x, overfit_y)

        overfit_marker = Text("过拟合", font_size=20, font=FONT_ZH, color=YELLOW)
        overfit_marker.next_to(overfit_point, UP, buff=0.2)
        self.play(Write(overfit_marker))

        self.wait(2.0)
