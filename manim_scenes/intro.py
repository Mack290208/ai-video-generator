"""
intro.py
--------
开场动画场景：标题 + 副标题 + 装饰线 + 淡入淡出。
用于每个教学视频的开场，避免学生看到纯色+字幕的"PPT 起播"感。

环境变量：
    MANIM_INTRO_TITLE     主标题（默认 "机器学习课堂"）
    MANIM_INTRO_SUBTITLE  副标题（默认 "今天我们来讲：梯度下降"）
    MANIM_INTRO_DURATION  期望时长（秒，默认 5.0；动画会尽量拉伸到这个时长）
"""

from __future__ import annotations

import os

from manim import (
    BLUE,
    DOWN,
    FadeIn,
    FadeOut,
    Line,
    LEFT,
    ORIGIN,
    RIGHT,
    Scene,
    Text,
    UP,
    WHITE,
    YELLOW,
    Write,
)


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if (v and v.strip()) else default


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if not (v and v.strip()):
        return default
    try:
        return float(v)
    except ValueError:
        return default


class IntroScene(Scene):
    def construct(self):
        title_text = _env("MANIM_INTRO_TITLE", "机器学习课堂")
        subtitle_text = _env("MANIM_INTRO_SUBTITLE", "今天我们来讲：梯度下降")
        duration = _env_float("MANIM_INTRO_DURATION", 5.0)

        title = Text(title_text, font="Microsoft YaHei", font_size=64, color=WHITE)
        subtitle = Text(subtitle_text, font="Microsoft YaHei", font_size=36, color=BLUE)

        title.move_to(UP * 0.8)
        subtitle.next_to(title, DOWN, buff=0.6)

        # 装饰线
        line_l = Line(start=LEFT * 3.2, end=LEFT * 1.6, color=YELLOW, stroke_width=3)
        line_r = Line(start=RIGHT * 1.6, end=RIGHT * 3.2, color=YELLOW, stroke_width=3)
        line_l.next_to(subtitle, DOWN, buff=0.8).shift(LEFT * 2.4)
        line_r.next_to(subtitle, DOWN, buff=0.8).shift(RIGHT * 2.4)

        # 动画（总计 ~= duration）
        self.play(Write(title), run_time=1.5)
        self.play(FadeIn(subtitle, shift=DOWN * 0.3), run_time=1.2)
        self.play(FadeIn(line_l, shift=RIGHT * 0.3), FadeIn(line_r, shift=LEFT * 0.3), run_time=0.8)

        # 填满剩余时长
        remaining = max(0.5, duration - (1.5 + 1.2 + 0.8 + 0.8))
        self.wait(remaining)

        self.play(FadeOut(title), FadeOut(subtitle), FadeOut(line_l), FadeOut(line_r), run_time=0.8)
