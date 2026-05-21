"""
templates/scatter_classify.py
-----------------------------
二维散点分类模板：两类样本 + 决策边界 + 区域填色。

教学价值：
- 二分类问题的可视化（KNN / SVM / 逻辑回归 / 感知机 / 决策树边界）
- 线性可分 vs 非线性可分
- 决策边界的几何含义

画面流程：
1. 标题
2. 2D 坐标系出现
3. 红色样本点 FadeIn（class A）
4. 蓝色样本点 FadeIn（class B）
5. 决策边界 Create（直线/圆/抛物线）
6. 两侧区域半透明染色（红区 / 蓝区）
7. 收尾保持

参数：
    title              - 主标题（必填）
    subtitle           - 副标题（可选，置于坐标系上方）
    class_a_label      - A 类标签文字（如"正类"）
    class_b_label      - B 类标签文字（如"负类"）
    class_a_points     - 字符串 "x1,y1; x2,y2; ..." 用分号分隔（A 类）
    class_b_points     - 同上（B 类）
    boundary_kind      - 决策边界类型：linear / circle / parabola
    boundary_a         - 边界参数 a（linear: y=ax+b 中的 a；circle: 圆心 cx；parabola: y=a(x-h)²+k 中的 a）
    boundary_b         - linear: b；circle: cy；parabola: h
    boundary_c         - linear: 不用；circle: r；parabola: k
    show_regions       - 是否给两侧涂半透明色（默认 true）
    duration           - 期望总时长

设计：
- x 范围固定 [-5, 5]，y 范围固定 [-3, 3]，方便 LLM 给坐标
- 决策边界从一端 Create 到另一端，体现"模型在学"
- 区域填色用很淡的颜色（30% 透明度）避免遮挡点
"""

from __future__ import annotations

from typing import List, Tuple

from manim import (
    Axes,
    BLUE,
    Circle,
    Create,
    Dot,
    FadeIn,
    GREEN,
    LEFT,
    ORANGE,
    Polygon,
    RED,
    RIGHT,
    Scene,
    Text,
    UP,
    DOWN,
    VGroup,
    WHITE,
    Write,
    YELLOW,
    MathTex,
)

from components import TitleBar
from layouts.constants import (
    AXES_X_LENGTH,
    AXES_Y_LENGTH,
    FONT_ZH,
    FS_AXIS,
    FS_BODY,
    SUBTITLE_TOP_Y,
)
from templates._param import param_bool, param_float, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "subtitle": {"type": "str", "required": False, "default": ""},
    "class_a_label": {"type": "str", "required": False, "default": "类 A"},
    "class_b_label": {"type": "str", "required": False, "default": "类 B"},
    "class_a_points": {
        "type": "str",
        "required": False,
        "default": "-3,1.2; -2.5,2.0; -2,1.5; -3.5,0.5; -2.8,-0.2; -1.8,1.0",
    },
    "class_b_points": {
        "type": "str",
        "required": False,
        "default": "2,-1.0; 2.5,-1.8; 3,-0.5; 1.8,-2.0; 3.2,-1.5; 2.2,-0.8",
    },
    "boundary_kind": {
        "type": "str",
        "required": False,
        "default": "linear",
        "allowed": ["linear", "circle", "parabola"],
    },
    "boundary_a": {"type": "float", "required": False, "default": 0.6},
    "boundary_b": {"type": "float", "required": False, "default": -0.5},
    "boundary_c": {"type": "float", "required": False, "default": 0.0},
    "show_regions": {"type": "bool", "required": False, "default": True},
    "duration": {"type": "float", "required": False, "default": 0.0},
}


TEMPLATE_META = {
    "summary": "二维散点 + 决策边界可视化：两类样本点 + 一条线性/圆形/抛物线决策边界 Create 出现，两侧可选半透明染色。直观展示分类算法的几何含义。",
    "use_cases": [
        "线性可分二分类（感知机、逻辑回归、线性 SVM）",
        "非线性边界（核 SVM、神经网络）",
        "KNN / 决策树的决策边界几何展示",
        "线性 vs 非线性可分对比的引子",
        "概念解释：什么是决策边界",
    ],
    "not_for": [
        "多分类（>2 类，暂不支持）",
        "高维样本（只能 2D 可视化）",
        "需要数学推导（用 formula_evolve）",
        "需要超参数对比（用 lr_comparison）",
    ],
    "example_params": {
        "title": "线性可分二分类",
        "subtitle": "决策边界把两类样本分开",
        "class_a_label": "正类 (+1)",
        "class_b_label": "负类 (-1)",
        "class_a_points": "-3,1.2; -2.5,2.0; -2,1.5; -3.5,0.5; -2.8,-0.2",
        "class_b_points": "2,-1.0; 2.5,-1.8; 3,-0.5; 1.8,-2.0; 3.2,-1.5",
        "boundary_kind": "linear",
        "boundary_a": 0.6,
        "boundary_b": -0.5,
        "duration": 14.0,
    },
}


def _parse_points(s: str) -> List[Tuple[float, float]]:
    """解析 'x1,y1; x2,y2; ...' 格式为 (float, float) 列表。"""
    out: List[Tuple[float, float]] = []
    if not s.strip():
        return out
    for chunk in s.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            x_str, y_str = chunk.split(",")
            out.append((float(x_str.strip()), float(y_str.strip())))
        except (ValueError, IndexError):
            continue
    return out


# 坐标范围（固定，方便 LLM）
X_MIN, X_MAX = -5.0, 5.0
Y_MIN, Y_MAX = -3.0, 3.0


class ScatterClassifyScene(Scene):
    """2D 散点分类 + 决策边界。"""

    def construct(self):
        title_text = param_str("title", "二维分类")
        subtitle_text = param_str("subtitle", "")
        class_a_label = param_str("class_a_label", "类 A")
        class_b_label = param_str("class_b_label", "类 B")
        class_a_points = _parse_points(param_str("class_a_points", ""))
        class_b_points = _parse_points(param_str("class_b_points", ""))
        boundary_kind = param_str("boundary_kind", "linear").lower()
        a = param_float("boundary_a", 0.6)
        b = param_float("boundary_b", -0.5)
        c = param_float("boundary_c", 0.0)
        show_regions = param_bool("show_regions", True)
        duration = param_float("duration", 0.0)

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

        # ---------- 1. 标题 ----------
        bar = TitleBar(title=title_text)
        play_t(*bar.write_anims(), run_time=1.0)

        # ---------- 2. 副标题（可选） ----------
        if subtitle_text.strip():
            sub = Text(
                subtitle_text,
                font=FONT_ZH,
                font_size=FS_BODY + 2,
                color=WHITE,
            ).move_to([0, 2.5, 0])
            play_t(FadeIn(sub, shift=DOWN * 0.2), run_time=0.6)

        # ---------- 3. 坐标系 ----------
        axes = Axes(
            x_range=[X_MIN, X_MAX, 1],
            y_range=[Y_MIN, Y_MAX, 1],
            x_length=AXES_X_LENGTH,
            y_length=AXES_Y_LENGTH * 0.95,
            axis_config={
                "color": WHITE,
                "include_numbers": False,
                "font_size": FS_AXIS - 4,
            },
            tips=False,
        )
        # 把坐标系下移一点，避免顶部和副标题/标题挤压
        axes.move_to([0, -0.2, 0])

        x_label = MathTex("x_1", font_size=FS_BODY + 4).next_to(
            axes.x_axis, RIGHT, buff=0.15
        )
        y_label = MathTex("x_2", font_size=FS_BODY + 4).next_to(
            axes.y_axis, UP, buff=0.15
        )
        play_t(Create(axes), FadeIn(x_label), FadeIn(y_label), run_time=1.0)

        # ---------- 4. A 类点 + 标签 ----------
        a_dots = VGroup(
            *[
                Dot(point=axes.c2p(x, y), color=RED, radius=0.09)
                for x, y in class_a_points
            ]
        )
        a_legend = Text(
            "● " + class_a_label,
            font=FONT_ZH,
            font_size=FS_BODY,
            color=RED,
        ).move_to([-5.0, 2.5, 0])
        play_t(FadeIn(a_dots), FadeIn(a_legend), run_time=0.9)

        # ---------- 5. B 类点 + 标签 ----------
        b_dots = VGroup(
            *[
                Dot(point=axes.c2p(x, y), color=BLUE, radius=0.09)
                for x, y in class_b_points
            ]
        )
        b_legend = Text(
            "● " + class_b_label,
            font=FONT_ZH,
            font_size=FS_BODY,
            color=BLUE,
        ).move_to([+5.0, 2.5, 0])
        play_t(FadeIn(b_dots), FadeIn(b_legend), run_time=0.9)

        # ---------- 6. 决策边界 ----------
        boundary = self._build_boundary(axes, boundary_kind, a, b, c)
        play_t(Create(boundary), run_time=1.6)

        # ---------- 7. 两侧区域填色（可选） ----------
        if show_regions:
            region_a, region_b = self._build_regions(axes, boundary_kind, a, b, c)
            if region_a is not None and region_b is not None:
                play_t(FadeIn(region_a), FadeIn(region_b), run_time=0.8)

        # ---------- 8. 收尾保持 ----------
        wait_t(1.6)

        # ---------- 9. 时长对齐 ----------
        if duration and duration > 0:
            remaining = duration - scene_ran
            if remaining > 0.1:
                self.wait(remaining)

    # =================================================================
    # 辅助方法
    # =================================================================
    def _build_boundary(self, axes, kind: str, a: float, b: float, c: float):
        """根据 kind 构造决策边界对象。"""
        if kind == "circle":
            cx, cy, r = a, b, max(0.3, c if c > 0 else 1.5)
            # circle 在 axes 坐标里画
            return axes.plot_implicit_curve(
                lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 - r ** 2,
                color=GREEN,
            ) if False else self._draw_circle(axes, cx, cy, r)
        if kind == "parabola":
            # y = a*(x - h)^2 + k
            h, k = b, c
            return axes.plot(lambda x: a * (x - h) ** 2 + k, x_range=[X_MIN, X_MAX], color=GREEN)
        # 默认 linear: y = a*x + b
        return axes.plot(lambda x: a * x + b, x_range=[X_MIN, X_MAX], color=GREEN)

    @staticmethod
    def _draw_circle(axes, cx: float, cy: float, r: float):
        """用 axes 坐标参数画圆。"""
        # axes 单位转屏幕单位（不严格相等，但近似 axes.x_axis.unit_size）
        unit = (axes.c2p(1, 0)[0] - axes.c2p(0, 0)[0])  # 1 单位 = 多少屏幕距离
        circle = Circle(radius=r * unit, color=GREEN, stroke_width=4)
        circle.move_to(axes.c2p(cx, cy))
        return circle

    def _build_regions(self, axes, kind: str, a: float, b: float, c: float):
        """构造两侧填色区域；不支持 circle 时返回 (None, None)。"""
        if kind == "linear":
            # 线 y = a*x + b 把 [X_MIN,X_MAX] x [Y_MIN,Y_MAX] 切成两半
            # 上半（y > a*x + b，红区）：四边形 = 直线段 + 顶部两点
            # 下半（蓝区）：直线段 + 底部两点
            x_l, x_r = X_MIN, X_MAX
            y_at_l = max(Y_MIN, min(Y_MAX, a * x_l + b))
            y_at_r = max(Y_MIN, min(Y_MAX, a * x_r + b))
            # 上半多边形（A 类区，红色淡）
            upper = Polygon(
                axes.c2p(x_l, y_at_l),
                axes.c2p(x_r, y_at_r),
                axes.c2p(x_r, Y_MAX),
                axes.c2p(x_l, Y_MAX),
                color=RED,
                fill_color=RED,
                fill_opacity=0.15,
                stroke_width=0,
            )
            # 下半多边形（B 类区，蓝色淡）
            lower = Polygon(
                axes.c2p(x_l, y_at_l),
                axes.c2p(x_r, y_at_r),
                axes.c2p(x_r, Y_MIN),
                axes.c2p(x_l, Y_MIN),
                color=BLUE,
                fill_color=BLUE,
                fill_opacity=0.15,
                stroke_width=0,
            )
            return upper, lower

        # parabola / circle 暂不画区域，避免几何复杂度
        return None, None
