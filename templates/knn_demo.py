"""
templates/knn_demo.py
--------------------------
KNN 算法可视化模板：展示 K 近邻分类过程

适用知识点：
- KNN 算法原理
- 距离计算
- 多数表决
- K 值选择

参数：
    title         - 主标题
    k             - K 值
    n_points      - 样本点数量
    n_classes     - 类别数量
    duration      - 期望总时长（秒）
"""

from __future__ import annotations
import random
from manim import (
    Scene, Create, FadeIn, Write,
    Dot, Circle, Line, VGroup, Text,
    BLUE, GREEN, YELLOW, WHITE, RED, ORANGE, PURPLE,
    LEFT, RIGHT, UP, DOWN,
)
from components import TitleBar
from layouts.constants import FONT_ZH, FS_BODY
from templates._param import param_float, param_int, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "k": {"type": "int", "required": False, "default": 3},
    "n_points": {"type": "int", "required": False, "default": 20},
    "n_classes": {"type": "int", "required": False, "default": 3},
    "duration": {"type": "float", "required": False, "default": 0.0},
}

TEMPLATE_META = {
    "summary": "KNN 分类算法可视化，展示 K 近邻投票过程",
    "use_cases": [
        "KNN 算法原理",
        "距离度量",
        "多数表决",
        "K 值选择的影响",
    ],
    "not_for": [
        "大规模数据集",
        "高维数据",
    ],
}

CLASS_COLORS = [BLUE, GREEN, ORANGE, PURPLE, RED, YELLOW]


class KNNDemoScene(Scene):
    def construct(self):
        title = param_str("title", "KNN 分类演示")
        k = param_int("k", 3)
        n_points = param_int("n_points", 20)
        n_classes = param_int("n_classes", 3)
        duration = param_float("duration", 0.0)

        # 标题
        title_bar = TitleBar(title)
        self.play(*title_bar.write_anims(), run_time=1.0)
        self.wait(0.5)

        # 生成随机样本点
        random.seed(42)
        points = []
        for _ in range(n_points):
            x = random.uniform(-5, 5)
            y = random.uniform(-3, 3)
            cls = random.randint(0, n_classes - 1)
            points.append((x, y, cls))

        # 绘制样本点
        dots_group = VGroup()
        for x, y, cls in points:
            color = CLASS_COLORS[cls % len(CLASS_COLORS)]
            dot = Dot(point=[x, y, 0], radius=0.1, color=color)
            dots_group.add(dot)

        self.play(FadeIn(dots_group), run_time=1.0)
        self.wait(0.5)

        # 新查询点
        query_x, query_y = 0, 0
        query_dot = Dot(point=[query_x, query_y, 0], radius=0.15, color=WHITE)
        query_label = Text("?", font_size=24, color=WHITE)
        query_label.next_to(query_dot, UP, buff=0.1)
        self.play(FadeIn(query_dot), Write(query_label))
        self.wait(0.5)

        # 计算距离并找到 K 个最近邻
        distances = []
        for i, (x, y, cls) in enumerate(points):
            dist = ((x - query_x) ** 2 + (y - query_y) ** 2) ** 0.5
            distances.append((dist, i, cls))

        distances.sort()
        nearest = distances[:k]

        # 高亮 K 个最近邻
        for dist, idx, cls in nearest:
            x, y, _ = points[idx]
            circle = Circle(radius=0.2, color=YELLOW, stroke_width=3)
            circle.move_to([x, y, 0])
            line = Line([query_x, query_y, 0], [x, y, 0], color=YELLOW, stroke_width=2)
            self.play(Create(circle), Create(line), run_time=0.3)

        # 统计类别投票
        votes = {}
        for _, _, cls in nearest:
            votes[cls] = votes.get(cls, 0) + 1

        predicted_class = max(votes, key=votes.get)
        predicted_color = CLASS_COLORS[predicted_class % len(CLASS_COLORS)]

        # 显示预测结果
        result_text = Text(f"预测类别: {predicted_class}", font_size=24, font=FONT_ZH, color=predicted_color)
        result_text.move_to([0, -3.5, 0])
        self.play(Write(result_text))

        # 更新查询点颜色
        self.play(query_dot.animate.set_color(predicted_color))
        self.wait(2.0)
