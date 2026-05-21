"""
components/coord_plot.py
------------------------
坐标系 + 单条函数曲线组件。

封装目标：
- 自动用 layouts.constants 里的标准位置/尺寸
- 默认放在主视觉区（略偏左，给右侧信息栏让位）
- 暴露 axes / curve / labels 让模板可以叠加 dot、tangent 等

用法：
    plot = CoordPlot(
        func=lambda x: (x - 2) ** 2,
        x_range=(-3, 5),
        y_range=(0, 12),
        x_label=r"\theta",
        y_label="L",
    )
    self.play(plot.create_anim(), run_time=1.2)
    self.play(plot.draw_curve_anim(), run_time=1.5)
    # 后续模板可以用 plot.axes.c2p(x, y) 把点/轨迹叠到上面
"""

from __future__ import annotations

from typing import Callable, List, Tuple

from manim import (
    BLUE,
    Animation,
    Axes,
    Create,
    FadeIn,
    FadeOut,
    MathTex,
    RIGHT,
    UP,
    VGroup,
    WHITE,
)

from layouts.constants import (
    AXES_X_LENGTH,
    AXES_Y_LENGTH,
    FS_AXIS,
    FS_BODY,
    MAIN_CENTER_X,
)


class CoordPlot:
    def __init__(
        self,
        func: Callable[[float], float],
        x_range: Tuple[float, float],
        y_range: Tuple[float, float],
        x_step: float = 1.0,
        y_step: float = 2.0,
        x_label: str = "x",
        y_label: str = "y",
        curve_color=BLUE,
        center_offset_y: float = 0.3,
        x_length: float = AXES_X_LENGTH,
        y_length: float = AXES_Y_LENGTH,
    ) -> None:
        self.func = func
        self.x_range = x_range
        self.y_range = y_range

        self.axes = Axes(
            x_range=[x_range[0], x_range[1], x_step],
            y_range=[y_range[0], y_range[1], y_step],
            x_length=x_length,
            y_length=y_length,
            axis_config={
                "color": WHITE,
                "include_numbers": True,
                "font_size": FS_AXIS,
            },
            tips=False,
        )
        self.axes.move_to([MAIN_CENTER_X, center_offset_y, 0])

        self.x_label = MathTex(x_label, font_size=FS_BODY + 8).next_to(
            self.axes.x_axis, RIGHT, buff=0.2
        )
        self.y_label = MathTex(y_label, font_size=FS_BODY + 8).next_to(
            self.axes.y_axis, UP, buff=0.2
        )

        self.curve = self.axes.plot(
            func, x_range=[x_range[0], x_range[1]], color=curve_color
        )

    # --------------------------------------------------------
    # 坐标变换
    # --------------------------------------------------------
    def c2p(self, x: float, y: float):
        """坐标系坐标 → 屏幕点。"""
        return self.axes.c2p(x, y)

    # --------------------------------------------------------
    # 动画工厂
    # --------------------------------------------------------
    def create_anims(self) -> List[Animation]:
        """坐标系 + 轴标签 出场。"""
        return [Create(self.axes), FadeIn(self.x_label), FadeIn(self.y_label)]

    def draw_curve_anim(self) -> Animation:
        """画曲线。"""
        return Create(self.curve)

    def fadeout_anims(self) -> List[Animation]:
        return [
            FadeOut(self.axes),
            FadeOut(self.x_label),
            FadeOut(self.y_label),
            FadeOut(self.curve),
        ]

    @property
    def group(self) -> VGroup:
        return VGroup(self.axes, self.x_label, self.y_label, self.curve)
