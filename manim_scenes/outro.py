"""
outro.py
--------
总结场景：要点列表逐条淡入，避免总结部分用纯色。

环境变量：
    MANIM_OUTRO_TITLE        总结标题（默认 "本节回顾"）
    MANIM_OUTRO_POINT_1..5   要点 1~5，空字符串表示不显示
    MANIM_OUTRO_DURATION     期望时长（秒，默认 8.0）
"""

from __future__ import annotations

import os

from manim import (
    BLUE,
    DOWN,
    FadeIn,
    FadeOut,
    GREEN,
    LEFT,
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


class OutroScene(Scene):
    def construct(self):
        title_text = _env("MANIM_OUTRO_TITLE", "本节回顾")
        duration = _env_float("MANIM_OUTRO_DURATION", 8.0)

        raw_points = [
            os.getenv("MANIM_OUTRO_POINT_1", "梯度下降沿着负梯度方向更新参数"),
            os.getenv("MANIM_OUTRO_POINT_2", "学习率 α 控制每一步的更新幅度"),
            os.getenv("MANIM_OUTRO_POINT_3", "α 太小收敛慢，α 太大可能震荡发散"),
            os.getenv("MANIM_OUTRO_POINT_4", ""),
            os.getenv("MANIM_OUTRO_POINT_5", ""),
        ]
        points = [p.strip() for p in raw_points if p and p.strip()]

        # 标题
        title = Text(title_text, font="Microsoft YaHei", font_size=50, color=WHITE)
        title.move_to(UP * 3.0)
        self.play(Write(title), run_time=1.2)

        # 要点逐条淡入（居中对齐，不靠左）
        bullets = []
        y_start = 1.6
        line_gap = 1.05
        for i, p in enumerate(points):
            bullet = Text(
                f"{i + 1}.  {p}",
                font="Microsoft YaHei",
                font_size=34,
                color=(YELLOW if i == 0 else BLUE if i == 1 else GREEN if i == 2 else WHITE),
            )
            # 居中放置
            bullet.move_to(UP * (y_start - i * line_gap))
            bullets.append(bullet)

        # 动画：每条 0.8~1.0s 淡入，中间保持
        enter_time_each = 0.9
        total_enter = enter_time_each * len(points)
        for b in bullets:
            self.play(FadeIn(b, shift=LEFT * 0.4), run_time=enter_time_each)

        # 剩余时间保持画面
        remaining = max(0.5, duration - 1.2 - total_enter - 0.8)
        self.wait(remaining)

        self.play(FadeOut(title), *[FadeOut(b) for b in bullets], run_time=0.8)
