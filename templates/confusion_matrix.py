"""
templates/confusion_matrix.py
--------------------------
混淆矩阵可视化模板：展示分类结果的混淆矩阵

适用知识点：
- 混淆矩阵概念
- 精确率 / 召回率 / F1
- 分类模型评估
- 真阳性 / 假阳性

参数：
    title         - 主标题
    labels        - 类别标签列表，如 ["猫", "狗", "鸟"]
    values        - 矩阵数值（扁平化），如 [50, 3, 2, 5, 45, 1, 1, 2, 48]
    duration      - 期望总时长（秒）
"""

from __future__ import annotations
from manim import (
    Scene, FadeIn, Write,
    Rectangle, VGroup, Text,
    BLUE, GREEN, YELLOW, WHITE, RED, ORANGE,
    LEFT, RIGHT, UP, DOWN,
)
from components import TitleBar
from layouts.constants import FONT_ZH, FS_BODY
from templates._param import param_float, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "labels": {"type": "list", "required": False, "default": ["猫", "狗", "鸟"]},
    "values": {"type": "list", "required": False, "default": [50, 3, 2, 5, 45, 1, 1, 2, 48]},
    "duration": {"type": "float", "required": False, "default": 0.0},
}

TEMPLATE_META = {
    "summary": "混淆矩阵可视化，展示分类结果和评估指标",
    "use_cases": [
        "混淆矩阵概念",
        "精确率 / 召回率 / F1",
        "分类模型评估",
        "多分类问题",
    ],
    "not_for": [
        "回归问题",
        "聚类问题",
    ],
}


class ConfusionMatrixScene(Scene):
    def construct(self):
        title = param_str("title", "混淆矩阵")
        labels = param_str("labels", ["猫", "狗", "鸟"])
        values = param_str("values", [50, 3, 2, 5, 45, 1, 1, 2, 48])
        duration = param_float("duration", 0.0)

        # 解析参数
        if isinstance(labels, str):
            try:
                labels = eval(labels)
            except:
                labels = ["猫", "狗", "鸟"]

        if isinstance(values, str):
            try:
                values = eval(values)
            except:
                values = [50, 3, 2, 5, 45, 1, 1, 2, 48]

        n = len(labels)

        # 标题
        title_bar = TitleBar(title)
        self.play(*title_bar.write_anims(), run_time=1.0)
        self.wait(0.5)

        # 创建矩阵
        matrix_group = VGroup()
        cell_size = 1.2
        start_x = -(n - 1) * cell_size / 2
        start_y = (n - 1) * cell_size / 2 - 1.0  # 整体下移，避免与标题重合

        # 绘制单元格
        for i in range(n):
            for j in range(n):
                idx = i * n + j
                value = values[idx] if idx < len(values) else 0

                # 单元格颜色（对角线为绿色，其他为蓝色）
                color = GREEN if i == j else BLUE
                opacity = min(0.8, value / 50) if value > 0 else 0.1

                rect = Rectangle(
                    width=cell_size * 0.9,
                    height=cell_size * 0.9,
                    color=color,
                    fill_opacity=opacity
                )
                rect.move_to([start_x + j * cell_size, start_y - i * cell_size, 0])

                # 数值文本
                value_text = Text(str(value), font_size=24, color=WHITE)
                value_text.move_to(rect.get_center())

                matrix_group.add(rect, value_text)

        # 添加标签
        for i, label in enumerate(labels):
            # 行标签（左侧）
            row_label = Text(label, font_size=18, font=FONT_ZH)
            row_label.move_to([start_x - cell_size, start_y - i * cell_size, 0])
            matrix_group.add(row_label)

            # 列标签（上方）
            col_label = Text(label, font_size=18, font=FONT_ZH)
            col_label.move_to([start_x + i * cell_size, start_y + cell_size, 0])
            matrix_group.add(col_label)

        # 预测/真实标签
        pred_label = Text("预测", font_size=20, font=FONT_ZH, color=YELLOW)
        pred_label.move_to([0, start_y + cell_size * 1.8, 0])

        true_label = Text("真实", font_size=20, font=FONT_ZH, color=YELLOW)
        true_label.move_to([start_x - cell_size * 1.8, 0, 0])

        matrix_group.add(pred_label, true_label)

        # 动画
        self.play(FadeIn(matrix_group), run_time=1.5)
        self.wait(3.0)
