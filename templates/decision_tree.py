"""
templates/decision_tree.py
--------------------------
决策树可视化模板：展示决策树的分裂过程

适用知识点：
- 决策树原理
- 信息增益 / 基尼系数
- 特征选择
- 树的分裂过程

参数：
    title         - 主标题
    feature       - 分裂特征名称
    threshold     - 分裂阈值
    left_label    - 左分支标签
    right_label   - 右分支标签
    depth         - 树的深度（1-3）
    duration      - 期望总时长（秒）
"""

from __future__ import annotations
from manim import (
    Scene, Create, FadeIn, Write,
    Rectangle, Line, VGroup, Text, MathTex,
    BLUE, GREEN, YELLOW, WHITE, RED,
    LEFT, RIGHT, UP, DOWN,
)
from components import TitleBar
from layouts.constants import FONT_ZH, FS_BODY
from templates._param import param_float, param_str, param_int


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "feature": {"type": "str", "required": False, "default": "特征"},
    "threshold": {"type": "str", "required": False, "default": "0.5"},
    "left_label": {"type": "str", "required": False, "default": "是"},
    "right_label": {"type": "str", "required": False, "default": "否"},
    "depth": {"type": "int", "required": False, "default": 2},
    "duration": {"type": "float", "required": False, "default": 0.0},
}

TEMPLATE_META = {
    "summary": "决策树分裂过程可视化，展示特征选择和节点分裂",
    "use_cases": [
        "决策树原理",
        "信息增益计算",
        "基尼系数",
        "特征选择",
    ],
    "not_for": [
        "随机森林（需要多棵树）",
        "神经网络",
    ],
}


class DecisionTreeScene(Scene):
    def construct(self):
        title = param_str("title", "决策树")
        feature = param_str("feature", "特征")
        threshold = param_str("threshold", "0.5")
        left_label = param_str("left_label", "是")
        right_label = param_str("right_label", "否")
        depth = param_int("depth", 2)
        duration = param_float("duration", 0.0)

        # 标题
        title_bar = TitleBar(title)
        self.play(*title_bar.write_anims(), run_time=1.0)
        self.wait(0.5)

        # 根节点
        root_text = f"{feature} <= {threshold}?"
        root = self._create_node(root_text, [0, 2, 0])
        self.play(FadeIn(root))
        self.wait(0.5)

        # 左分支
        left_line = Line([0, 1.5, 0], [-1.5, 0.5, 0], color=GREEN)
        left_node = self._create_node(left_label, [-1.5, 0, 0])
        self.play(Create(left_line), FadeIn(left_node))
        self.wait(0.3)

        # 右分支
        right_line = Line([0, 1.5, 0], [1.5, 0.5, 0], color=RED)
        right_node = self._create_node(right_label, [1.5, 0, 0])
        self.play(Create(right_line), FadeIn(right_node))
        self.wait(0.3)

        # 如果深度 >= 2，添加子节点
        if depth >= 2:
            # 左子节点分裂
            left_child = self._create_node("特征B <= 0.3?", [-2.5, -1.5, 0])
            left_child_line = Line([-1.5, -0.5, 0], [-2.5, -1, 0], color=GREEN)
            self.play(Create(left_child_line), FadeIn(left_child))

            # 右子节点分裂
            right_child = self._create_node("特征C <= 0.7?", [2.5, -1.5, 0])
            right_child_line = Line([1.5, -0.5, 0], [2.5, -1, 0], color=RED)
            self.play(Create(right_child_line), FadeIn(right_child))

        self.wait(2.0)

    def _create_node(self, text, position):
        """创建决策树节点"""
        rect = Rectangle(width=2.5, height=0.8, color=BLUE, fill_opacity=0.2)
        text_obj = Text(text, font_size=20, font=FONT_ZH)
        group = VGroup(rect, text_obj)
        group.move_to(position)
        return group
