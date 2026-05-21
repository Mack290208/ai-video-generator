"""
components/bullet_list.py
-------------------------
要点列表组件：标题 + 编号要点逐条淡入。

适合：
- 总结/回顾页（"本节回顾"+3条要点）
- 知识点小结
- 流程步骤

调用方决定动画时序，组件只构造 mobjects 并暴露动画工厂。

用法：
    bl = BulletList(
        title="本节回顾",
        points=["梯度沿负方向更新", "α 控制步长", "α 太小慢, 太大震荡"],
    )
    self.play(bl.title_anim(), run_time=1.0)
    for anim in bl.bullet_anims():
        self.play(anim, run_time=0.9)
    # 退场
    self.play(*bl.fadeout_anims(), run_time=0.8)
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from manim import (
    BLUE,
    DOWN,
    FadeIn,
    FadeOut,
    GREEN,
    LEFT,
    Text,
    UP,
    VGroup,
    WHITE,
    Write,
    YELLOW,
    Animation,
)

from layouts.constants import (
    FONT_ZH,
    FS_SUBTITLE,
    FS_TITLE,
    TITLE_Y,
)


# 要点轮播配色（与 outro 保持一致：第 1 黄 / 第 2 蓝 / 第 3 绿 / 之后白）
_POINT_COLORS = [YELLOW, BLUE, GREEN, WHITE, WHITE]


class BulletList:
    def __init__(
        self,
        title: str,
        points: Sequence[str],
        title_y: float = TITLE_Y - 0.4,    # 比纯标题略下，给要点空间
        first_bullet_y: float = 1.6,
        line_gap: float = 1.05,
        bullet_font_size: int = 34,
        title_font_size: int = FS_TITLE + 16,  # 50pt 与 legacy outro 保持一致
        colors: Optional[Sequence] = None,
    ) -> None:
        # 过滤空 point
        self.points: List[str] = [p.strip() for p in points if p and p.strip()]

        # 标题
        self.title = Text(title, font=FONT_ZH, font_size=title_font_size, color=WHITE)
        self.title.move_to([0, title_y, 0])

        # 要点（居中对齐，自上而下）
        palette = list(colors) if colors else _POINT_COLORS
        self.bullets: List[Text] = []
        for i, p in enumerate(self.points):
            color = palette[i] if i < len(palette) else WHITE
            bullet = Text(
                f"{i + 1}.  {p}",
                font=FONT_ZH,
                font_size=bullet_font_size,
                color=color,
            )
            bullet.move_to([0, first_bullet_y - i * line_gap, 0])
            self.bullets.append(bullet)

    # --------------------------------------------------------
    # 动画工厂
    # --------------------------------------------------------
    def title_anim(self) -> Animation:
        """标题 Write 动画。"""
        return Write(self.title)

    def bullet_anims(self) -> List[Animation]:
        """每条要点的 FadeIn 动画（调用方按节奏 self.play 一条一条）。"""
        return [FadeIn(b, shift=LEFT * 0.4) for b in self.bullets]

    def fadeout_anims(self) -> List[Animation]:
        return [FadeOut(self.title), *[FadeOut(b) for b in self.bullets]]

    # --------------------------------------------------------
    # 视图
    # --------------------------------------------------------
    @property
    def group(self) -> VGroup:
        return VGroup(self.title, *self.bullets)

    @property
    def n_points(self) -> int:
        return len(self.bullets)
