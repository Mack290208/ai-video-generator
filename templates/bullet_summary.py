"""
templates/bullet_summary.py
---------------------------
通用要点总结模板：标题 + N 条编号要点。

布局智能：
- 1~3 条要点：垂直居中单列（适合简短总结）
- 4~5 条要点：左右两列对称排布（避免下方被字幕挤压）
  - 左列放第 1, 3, (5)
  - 右列放第 2, 4

参数：
    title         - 主标题（必填）
    point_1..5    - 要点 1~5，空字符串表示不显示该条
    duration      - 期望总时长（秒，默认 8.0）
"""

from __future__ import annotations

from typing import List

from manim import (
    BLUE,
    DOWN,
    FadeIn,
    FadeOut,
    GREEN,
    LEFT,
    Scene,
    Text,
    WHITE,
    Write,
    YELLOW,
    Animation,
)

from layouts.constants import (
    FONT_ZH,
    FS_TITLE,
    TITLE_Y,
)
from templates._param import param_float, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "point_1": {"type": "str", "required": False, "default": ""},
    "point_2": {"type": "str", "required": False, "default": ""},
    "point_3": {"type": "str", "required": False, "default": ""},
    "point_4": {"type": "str", "required": False, "default": ""},
    "point_5": {"type": "str", "required": False, "default": ""},
    "duration": {"type": "float", "required": False, "default": 8.0},
}

TEMPLATE_META = {
    "summary": "标题 + N 条编号要点逐条添入。1~3 条单列居中；4~5 条自动左右两列对称排布避免被字幕挤压。",
    "use_cases": [
        "课程结尾的本节回顾（多用 4~5 条）",
        "三个主要性质 / 三个步骤 这种静态列举",
        "定义页（某个概念有几条性质）",
    ],
    "not_for": [
        "需要画面动态下降 / 曲线动画的场景（用 curve_descent）",
        "有序推导过程（用 formula_evolve）",
    ],
    "example_params": {
        "title": "本节回顾",
        "point_1": "梯度下降沿负梯度方向更新参数",
        "point_2": "学习率 α 控制每一步的更新幅度",
        "point_3": "α 太小收敛慢，太大会震荡发散",
    },
}


# 配色：第 1 黄 / 第 2 蓝 / 第 3 绿 / 第 4-5 白
_POINT_COLORS = [YELLOW, BLUE, GREEN, WHITE, WHITE]


def _build_single_column(
    points: List[str],
    bullet_font_size: int,
    title_y: float,
    first_bullet_y: float,
    line_gap: float,
) -> List[Text]:
    """单列布局 - 编号开头左对齐（所有 "1." "2." "3." 在同一 x 上）。超宽则缩字。"""
    bullets: List[Text] = []
    align_x = -5.5
    # 单列最大允许宽度：从 align_x 到右边缘0.5 需位置
    max_w = 7.11 - 0.5 - align_x   # ≈ 12.11。实际不会被触发但作安全网
    for i, p in enumerate(points):
        color = _POINT_COLORS[i] if i < len(_POINT_COLORS) else WHITE
        bullet = Text(
            f"{i + 1}.  {p}",
            font=FONT_ZH,
            font_size=bullet_font_size,
            color=color,
        )
        if bullet.width > max_w:
            bullet.scale(max_w / bullet.width)
        y = first_bullet_y - i * line_gap
        bullet.move_to([align_x + bullet.width / 2.0, y, 0])
        bullets.append(bullet)
    return bullets


def _build_two_columns(
    points: List[str],
    bullet_font_size: int,
    first_bullet_y: float,
    line_gap: float,
) -> List[Text]:
    """左右两列对称布局 - 限宽 + 中线两侧向外展开。

    布局思路：
      - 左列 = 以中线偏左 0.4 为“右锡定”（文本向左生长）
      - 右列 = 以中线偏右 0.4 为“左锡定”（文本向右生长）
      - 二列不会跨过中线重叠
      - 超出画宽者在上层自适应字号后还超 → 用 set_width 限住
    分配规则：
      4 条：左 [1,3]，右 [2,4]
      5 条：左 [1,3,5]，右 [2,4]
    """
    bullets: List[Text] = []

    # 中线两侧锡点。距中线 0.4 留出中间间距
    left_anchor_x = -0.4    # 左列文本右边缘 锡定在这里
    right_anchor_x = +0.4   # 右列文本左边缘 锡定在这里

    # 单个 bullet 最大允许宽度（左右边缘1 及中间留白）
    # 画布 x 范围 ±7.11，边缘安全距 0.5，以及靠中线一侧 0.4
    max_w = 7.11 - 0.5 - 0.4   # ≈ 6.21

    for i, p in enumerate(points):
        color = _POINT_COLORS[i] if i < len(_POINT_COLORS) else WHITE
        is_left = (i % 2 == 0)        # i=0(第1) 在左, i=1(第2) 在右, ...
        col_idx = i // 2              # 在所属列里的第几个
        y = first_bullet_y - col_idx * line_gap

        bullet = Text(
            f"{i + 1}.  {p}",
            font=FONT_ZH,
            font_size=bullet_font_size,
            color=color,
        )

        # 太宽 → 按比例缩到 max_w
        if bullet.width > max_w:
            bullet.scale(max_w / bullet.width)

        if is_left:
            # 左列：右锡定到 left_anchor_x
            bullet.move_to([left_anchor_x - bullet.width / 2.0, y, 0])
        else:
            # 右列：左锡定到 right_anchor_x
            bullet.move_to([right_anchor_x + bullet.width / 2.0, y, 0])

        bullets.append(bullet)

    return bullets


class BulletSummaryScene(Scene):
    """要点列表总结动画（智能单列/双列）。"""

    def construct(self):
        title = param_str("title", "本节回顾")
        duration = param_float("duration", 8.0)

        raw_points = [param_str(f"point_{i}", "") for i in range(1, 6)]
        points = [p for p in raw_points if p.strip()]
        n = len(points)

        # 标题位置（与 TitleBar 一致放在顶部）
        title_obj = Text(
            title,
            font=FONT_ZH,
            font_size=FS_TITLE + 16,  # 50pt 大标题
            color=WHITE,
        )
        title_obj.move_to([0, TITLE_Y - 0.4, 0])

        # 选择布局
        if n <= 3:
            # 单列居中
            bullet_font_size = 34
            first_bullet_y = 1.5
            line_gap = 1.05
            bullets = _build_single_column(
                points, bullet_font_size, TITLE_Y - 0.4, first_bullet_y, line_gap
            )
        else:
            # 双列对称
            bullet_font_size = 28  # 双列要稍小
            first_bullet_y = 1.0
            line_gap = 1.15
            bullets = _build_two_columns(
                points, bullet_font_size, first_bullet_y, line_gap
            )

        # ---------- 时序 ----------
        title_dur = 1.2
        per_bullet_dur = 0.8
        outro_dur = 0.8

        scene_ran = 0.0
        self.play(Write(title_obj), run_time=title_dur)
        scene_ran += title_dur

        for b in bullets:
            self.play(FadeIn(b, shift=LEFT * 0.4), run_time=per_bullet_dur)
            scene_ran += per_bullet_dur

        # 中间保持
        remaining = duration - scene_ran - outro_dur
        if remaining > 0.1:
            self.wait(remaining)

        # 退场
        all_objs = [title_obj] + bullets
        self.play(*[FadeOut(o) for o in all_objs], run_time=outro_dur)
