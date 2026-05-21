"""
templates/concept_compare.py
----------------------------
概念双栏对比模板：左右两列纯文字概念对比。

教学价值：
- 信息增益 vs 基尼系数
- L1 正则 vs L2 正则
- 监督学习 vs 无监督学习
- 偏差 vs 方差
- 任何 "A vs B" 概念对照场景

与 lr_comparison 的区别：
- lr_comparison 是数学曲线对比（坐标系 + 下降轨迹）
- concept_compare 是纯文字概念对比（公式 + 要点列表）
- 没有动画曲线，只有"标题 → 公式 → 要点逐条淡入"

参数：
    title              - 主标题（必填）
    left_title         - 左栏小标题（必填，如"信息增益"）
    right_title        - 右栏小标题（必填，如"基尼系数"）
    left_formula       - 左栏 LaTeX 公式（可选）
    right_formula      - 右栏 LaTeX 公式（可选）
    left_point_1..3    - 左栏要点（最多 3 条）
    right_point_1..3   - 右栏要点（最多 3 条）
    left_color         - 左栏配色名（默认 BLUE）
    right_color        - 右栏配色名（默认 YELLOW）
    duration           - 期望总时长（秒）
"""

from __future__ import annotations

from manim import (
    BLUE,
    Create,
    DOWN,
    FadeIn,
    GREEN,
    Line,
    MathTex,
    ORANGE,
    RED,
    Scene,
    Text,
    WHITE,
    Write,
    YELLOW,
)

from components import TitleBar
from layouts.constants import (
    FONT_ZH,
    FS_BODY,
    FS_FORMULA,
    FS_SUBTITLE,
    SUBTITLE_TOP_Y,
    TITLE_Y,
)
from templates._param import param_float, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "left_title": {"type": "str", "required": True},
    "right_title": {"type": "str", "required": True},
    "left_formula": {"type": "str", "required": False, "default": ""},
    "right_formula": {"type": "str", "required": False, "default": ""},
    "left_point_1": {"type": "str", "required": False, "default": ""},
    "left_point_2": {"type": "str", "required": False, "default": ""},
    "left_point_3": {"type": "str", "required": False, "default": ""},
    "right_point_1": {"type": "str", "required": False, "default": ""},
    "right_point_2": {"type": "str", "required": False, "default": ""},
    "right_point_3": {"type": "str", "required": False, "default": ""},
    "left_color": {
        "type": "str",
        "required": False,
        "default": "BLUE",
        "allowed": ["BLUE", "YELLOW", "GREEN", "ORANGE", "RED", "WHITE"],
    },
    "right_color": {
        "type": "str",
        "required": False,
        "default": "YELLOW",
        "allowed": ["BLUE", "YELLOW", "GREEN", "ORANGE", "RED", "WHITE"],
    },
    "duration": {"type": "float", "required": False, "default": 0.0},
}


TEMPLATE_META = {
    "summary": "纯文字概念双栏对比：左右各一个小标题 + 公式 + 1~3 条要点，逐条淡入。适合 A vs B 类概念对照。",
    "use_cases": [
        "信息增益 vs 基尼系数",
        "L1 正则 vs L2 正则",
        "监督学习 vs 无监督学习",
        "偏差（Bias）vs 方差（Variance）",
        "Bagging vs Boosting",
        "任何 \"A vs B\" 类概念对比",
    ],
    "not_for": [
        "需要数学曲线 / 坐标系下降轨迹的对比（用 lr_comparison）",
        "超过两类的多向对比（暂不支持）",
        "纯单栏要点列表（用 bullet_summary）",
    ],
    "example_params": {
        "title": "信息增益 vs 基尼系数",
        "left_title": "信息增益",
        "right_title": "基尼系数",
        "left_formula": r"IG = H(D) - \sum_v \frac{|D_v|}{|D|} H(D_v)",
        "right_formula": r"Gini(D) = 1 - \sum_i p_i^2",
        "left_point_1": "源自信息论，衡量分裂前后熵的减少",
        "left_point_2": "ID3 / C4.5 算法采用",
        "left_point_3": "对类别多的特征有偏好",
        "right_point_1": "衡量样本不纯度，越小越纯",
        "right_point_2": "CART 算法采用",
        "right_point_3": "无对数计算，速度更快",
        "duration": 18.0,
    },
}


_COLOR_MAP = {
    "BLUE": BLUE,
    "YELLOW": YELLOW,
    "GREEN": GREEN,
    "ORANGE": ORANGE,
    "RED": RED,
    "WHITE": WHITE,
}


def _resolve_color(name: str, default):
    return _COLOR_MAP.get(name.upper(), default)


# 左右列中心 x（屏幕宽 14.22，左右各占 ~6 单位居中）
_LEFT_CENTER_X = -3.6
_RIGHT_CENTER_X = +3.6


class ConceptCompareScene(Scene):
    """双栏纯文字概念对比。"""

    def construct(self):
        title_text = param_str("title", "概念对比")
        left_title = param_str("left_title", "A")
        right_title = param_str("right_title", "B")
        left_formula = param_str("left_formula", "")
        right_formula = param_str("right_formula", "")
        left_color = _resolve_color(param_str("left_color", "BLUE"), BLUE)
        right_color = _resolve_color(param_str("right_color", "YELLOW"), YELLOW)
        duration = param_float("duration", 0.0)

        left_points = [
            param_str(f"left_point_{i}", "") for i in range(1, 4)
        ]
        left_points = [p for p in left_points if p.strip()]

        right_points = [
            param_str(f"right_point_{i}", "") for i in range(1, 4)
        ]
        right_points = [p for p in right_points if p.strip()]

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

        # ---------- 2. 中央分隔线（细，半透明）----------
        # 从 y=2.0 到 SUBTITLE_TOP_Y+0.2
        divider = Line(
            start=[0, 2.0, 0],
            end=[0, SUBTITLE_TOP_Y + 0.2, 0],
            color=WHITE,
            stroke_width=1.5,
        ).set_opacity(0.35)
        play_t(Create(divider), run_time=0.5)

        # ---------- 3. 左右栏小标题 ----------
        left_label = Text(
            left_title,
            font=FONT_ZH,
            font_size=FS_SUBTITLE + 4,
            color=left_color,
        ).move_to([_LEFT_CENTER_X, 2.2, 0])

        right_label = Text(
            right_title,
            font=FONT_ZH,
            font_size=FS_SUBTITLE + 4,
            color=right_color,
        ).move_to([_RIGHT_CENTER_X, 2.2, 0])

        play_t(Write(left_label), Write(right_label), run_time=0.9)

        # ---------- 4. 公式（如果给了）----------
        formula_y = 1.1
        left_formula_obj = None
        right_formula_obj = None
        if left_formula.strip():
            left_formula_obj = MathTex(
                left_formula, font_size=FS_FORMULA - 2, color=left_color
            ).move_to([_LEFT_CENTER_X, formula_y, 0])
        if right_formula.strip():
            right_formula_obj = MathTex(
                right_formula, font_size=FS_FORMULA - 2, color=right_color
            ).move_to([_RIGHT_CENTER_X, formula_y, 0])

        formula_anims = []
        if left_formula_obj is not None:
            formula_anims.append(Write(left_formula_obj))
        if right_formula_obj is not None:
            formula_anims.append(Write(right_formula_obj))
        if formula_anims:
            play_t(*formula_anims, run_time=1.0)

        # ---------- 5. 左右要点逐条淡入 ----------
        first_bullet_y = 0.0 if (left_formula_obj or right_formula_obj) else 0.9
        line_gap = 0.85
        bullet_font_size = 24

        # 把 left/right 要点配对显示（i 行同时出现），不够的一边就跳过
        max_points = max(len(left_points), len(right_points))
        per_row_dur = 0.85
        for i in range(max_points):
            row_anims = []
            if i < len(left_points):
                lt = Text(
                    f"• {left_points[i]}",
                    font=FONT_ZH,
                    font_size=bullet_font_size,
                    color=WHITE,
                ).move_to([_LEFT_CENTER_X, first_bullet_y - i * line_gap, 0])
                row_anims.append(FadeIn(lt, shift=DOWN * 0.15))
            if i < len(right_points):
                rt = Text(
                    f"• {right_points[i]}",
                    font=FONT_ZH,
                    font_size=bullet_font_size,
                    color=WHITE,
                ).move_to([_RIGHT_CENTER_X, first_bullet_y - i * line_gap, 0])
                row_anims.append(FadeIn(rt, shift=DOWN * 0.15))
            if row_anims:
                play_t(*row_anims, run_time=per_row_dur)

        # ---------- 6. 收尾保持 ----------
        wait_t(1.2)

        # ---------- 7. 时长对齐 ----------
        if duration and duration > 0:
            remaining = duration - scene_ran
            if remaining > 0.1:
                self.wait(remaining)
