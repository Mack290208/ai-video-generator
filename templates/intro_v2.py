"""
templates/intro_v2.py
---------------------
重构版开场模板：标题居中 + 字号放大（仪式感更强）。

参数（通过 manim_service.render_manim_scene 的 params dict 传入）：
    title            - 主标题（required）
    subtitle         - 副标题（optional）
    duration         - 期望时长（秒，默认 5.0）
    show_decoration  - 是否显示装饰线（默认 True）
"""

from __future__ import annotations

from manim import (
    BLUE,
    DOWN,
    FadeIn,
    FadeOut,
    LEFT,
    Line,
    RIGHT,
    Scene,
    Text,
    VGroup,
    WHITE,
    Write,
    YELLOW,
)

from layouts.constants import FONT_ZH
from templates._param import param_bool, param_float, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "subtitle": {"type": "str", "required": False, "default": ""},
    "duration": {"type": "float", "required": False, "default": 5.0},
    "show_decoration": {"type": "bool", "required": False, "default": True},
}

TEMPLATE_META = {
    "summary": "课程开场：主标题 + 副标题 + 装饰线居中显示，字号大，仪式感强。区别于其它模板把标题放顶部，开场页标题居中放大。",
    "use_cases": [
        "任何一节课的开场画面",
        "“今天我们来讲：XXX” 这种仪式感强的起播",
    ],
    "not_for": [
        "需要多行内容的场景（请用 bullet_summary）",
        "课程主体内容（开场专用）",
    ],
    "example_params": {
        "title": "机器学习课堂",
        "subtitle": "今天我们来讲：梯度下降",
        "duration": 5.0,
    },
}


# 居中大标题字号（明显大于普通顶部标题 FS_TITLE=34）
# 2026-06-23: 64→54，修复笔画密集汉字（拟、合等）渲染重叠问题
INTRO_TITLE_SIZE = 54
INTRO_SUBTITLE_SIZE = 36


class IntroV2Scene(Scene):
    """开场：标题居中放大 + 副标题 + 装饰线，淡入淡出。"""

    def construct(self):
        title = param_str("title", "机器学习课堂")
        subtitle = param_str("subtitle", "")
        duration = param_float("duration", 5.0)
        show_deco = param_bool("show_decoration", True)

        # ---------- 主标题（居中略偏上，给副标题留位置） ----------
        title_obj = Text(
            title,
            font=FONT_ZH,
            font_size=INTRO_TITLE_SIZE,
            color=WHITE,
        )
        # 如果有副标题，标题略偏上 0.6；否则正中
        title_y = 0.7 if (subtitle and subtitle.strip()) else 0.0
        title_obj.move_to([0, title_y, 0])

        anims_in = [Write(title_obj)]
        anims_out = [FadeOut(title_obj)]

        # ---------- 副标题（标题下方） ----------
        subtitle_obj = None
        if subtitle and subtitle.strip():
            subtitle_obj = Text(
                subtitle,
                font=FONT_ZH,
                font_size=INTRO_SUBTITLE_SIZE,
                color=BLUE,
            )
            subtitle_obj.next_to(title_obj, DOWN, buff=0.55)
            anims_in.append(FadeIn(subtitle_obj, shift=DOWN * 0.3))
            anims_out.append(FadeOut(subtitle_obj))

        # ---------- 装饰线（标题左右两侧） ----------
        # 根据标题真实宽度动态计算：装饰线起点 = 标题边缘 + 0.6 安全间距
        if show_deco:
            line_y = title_y + 0.05  # 与标题中心同高
            title_half_w = title_obj.width / 2.0
            gap = 0.6  # 标题与装饰线之间的间距
            line_inner = title_half_w + gap   # 装饰线靠近标题的端点
            line_outer = max(line_inner + 1.6, 6.5)  # 装饰线外端，至少长 1.6
            line_left = Line(
                start=[-line_outer, line_y, 0],
                end=[-line_inner, line_y, 0],
                color=YELLOW,
                stroke_width=4,
            )
            line_right = Line(
                start=[+line_inner, line_y, 0],
                end=[+line_outer, line_y, 0],
                color=YELLOW,
                stroke_width=4,
            )
            anims_in.append(FadeIn(line_left, shift=RIGHT * 0.4))
            anims_in.append(FadeIn(line_right, shift=LEFT * 0.4))
            anims_out.append(FadeOut(line_left))
            anims_out.append(FadeOut(line_right))

        # ---------- 时序 ----------
        # 出场 ~2.0s
        self.play(*anims_in, run_time=2.0)

        # 中间保持
        remaining = max(0.5, duration - 2.0 - 0.8)
        self.wait(remaining)

        # 退场 ~0.8s
        self.play(*anims_out, run_time=0.8)
