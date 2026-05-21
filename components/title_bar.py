"""
components/title_bar.py
-----------------------
标题栏组件：顶部居中标题 + 可选副标题 + 可选装饰线。

设计原则
========
- 组件本身只负责 **构造 mobject 并摆好位置**，不调用 self.play。
- 由调用方（template / scene）决定如何 Write / FadeIn / FadeOut。
- 所有坐标从 layouts.constants 取，禁止硬编码。

用法（模板里）：
    from components import TitleBar

    title_bar = TitleBar(title="梯度下降", subtitle="一步步滑向最低点")
    self.play(*title_bar.write_anims(), run_time=1.2)
    # ... 中间内容 ...
    self.play(*title_bar.fadeout_anims(), run_time=0.6)
"""

from __future__ import annotations

from typing import List, Optional

from manim import (
    BLUE,
    DOWN,
    FadeIn,
    FadeOut,
    LEFT,
    Line,
    RIGHT,
    Text,
    VGroup,
    WHITE,
    Write,
    YELLOW,
    Animation,
)

from layouts.constants import (
    FONT_ZH,
    FS_TITLE,
    FS_SUBTITLE,
    TITLE_Y,
)


class TitleBar:
    """顶部标题栏。

    Parameters
    ----------
    title : str
        主标题文本。
    subtitle : str, optional
        副标题文本；为空则不显示。
    show_decoration : bool
        是否显示左右两条装饰短线（适合 intro 类强仪式感场景）。
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        show_decoration: bool = False,
    ) -> None:
        self._mobjects: List = []

        # 主标题
        self.title = Text(title, font=FONT_ZH, font_size=FS_TITLE, color=WHITE)
        self.title.move_to([0, TITLE_Y, 0])
        self._mobjects.append(self.title)

        # 副标题（可选）
        self.subtitle: Optional[Text] = None
        if subtitle and subtitle.strip():
            self.subtitle = Text(
                subtitle, font=FONT_ZH, font_size=FS_SUBTITLE, color=BLUE
            )
            self.subtitle.next_to(self.title, DOWN, buff=0.4)
            self._mobjects.append(self.subtitle)

        # 装饰线（可选）
        self.deco_left: Optional[Line] = None
        self.deco_right: Optional[Line] = None
        if show_decoration:
            anchor = self.subtitle if self.subtitle is not None else self.title
            self.deco_left = Line(
                start=LEFT * 1.6, end=LEFT * 0.0, color=YELLOW, stroke_width=3
            )
            self.deco_right = Line(
                start=RIGHT * 0.0, end=RIGHT * 1.6, color=YELLOW, stroke_width=3
            )
            self.deco_left.next_to(anchor, DOWN, buff=0.5).shift(LEFT * 2.4)
            self.deco_right.next_to(anchor, DOWN, buff=0.5).shift(RIGHT * 2.4)
            self._mobjects.append(self.deco_left)
            self._mobjects.append(self.deco_right)

    # --------------------------------------------------------
    # 给模板调用的便捷动画工厂
    # --------------------------------------------------------
    def write_anims(self) -> List[Animation]:
        """返回"出场"动画列表，调用方一次性 self.play(*anims)。"""
        anims: List[Animation] = [Write(self.title)]
        if self.subtitle is not None:
            anims.append(FadeIn(self.subtitle, shift=DOWN * 0.2))
        if self.deco_left is not None and self.deco_right is not None:
            anims.append(FadeIn(self.deco_left, shift=RIGHT * 0.3))
            anims.append(FadeIn(self.deco_right, shift=LEFT * 0.3))
        return anims

    def fadeout_anims(self) -> List[Animation]:
        """返回"退场"动画列表。"""
        return [FadeOut(m) for m in self._mobjects]

    # --------------------------------------------------------
    # VGroup 视图（如果模板想直接操作整组）
    # --------------------------------------------------------
    @property
    def group(self) -> VGroup:
        return VGroup(*self._mobjects)

    @property
    def mobjects(self) -> List:
        return list(self._mobjects)
