"""
templates/neural_network.py
--------------------------
神经网络结构可视化模板：展示多层网络结构和数据流动

适用知识点：
- 神经网络基础结构
- 前向传播过程
- 深度学习模型架构
- 感知机

参数：
    title         - 主标题
    layers        - 各层神经元数量列表，如 [3, 5, 4, 2]
    layer_labels  - 各层标签，如 ["输入层", "隐藏层1", "隐藏层2", "输出层"]
    show_values   - 是否显示数值（布尔）
    duration      - 期望总时长（秒）
"""

from __future__ import annotations
from manim import (
    Scene, Create, FadeIn, FadeOut, Write,
    Circle, Line, Arrow, VGroup, Text, MathTex,
    BLUE, GREEN, YELLOW, WHITE, RED, ORANGE,
    LEFT, RIGHT, UP, DOWN,
)
from components import TitleBar
from layouts.constants import FONT_ZH, FS_BODY, FS_TITLE
from templates._param import param_float, param_int, param_str, param_bool


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "layers": {"type": "list", "required": False, "default": [3, 5, 4, 2]},
    "layer_labels": {"type": "list", "required": False, "default": ["输入层", "隐藏层1", "隐藏层2", "输出层"]},
    "show_values": {"type": "bool", "required": False, "default": False},
    "duration": {"type": "float", "required": False, "default": 0.0},
}

TEMPLATE_META = {
    "summary": "神经网络结构图，展示多层感知机的层结构和连接",
    "use_cases": [
        "神经网络基础结构",
        "前向传播过程",
        "深度学习模型架构",
        "感知机原理",
    ],
    "not_for": [
        "CNN 卷积操作（需要专门模板）",
        "RNN 序列处理（需要专门模板）",
    ],
}


class NeuralNetworkScene(Scene):
    def construct(self):
        title = param_str("title", "神经网络结构")
        layers = param_str("layers", [3, 5, 4, 2])
        layer_labels = param_str("layer_labels", ["输入层", "隐藏层1", "隐藏层2", "输出层"])
        duration = param_float("duration", 0.0)

        # 如果 layers 是字符串，尝试解析为列表
        if isinstance(layers, str):
            try:
                layers = eval(layers)
            except:
                layers = [3, 5, 4, 2]

        if isinstance(layer_labels, str):
            try:
                layer_labels = eval(layer_labels)
            except:
                layer_labels = ["输入层", "隐藏层1", "隐藏层2", "输出层"]

        # 标题
        title_bar = TitleBar(title)
        self.play(*title_bar.write_anims(), run_time=1.0)
        self.wait(0.5)

        # 绘制网络结构
        network_group = VGroup()
        n_layers = len(layers)
        x_spacing = 2.0
        start_x = -(n_layers - 1) * x_spacing / 2

        # 创建各层神经元
        neuron_groups = []
        for layer_idx, n_neurons in enumerate(layers):
            layer_group = VGroup()
            x = start_x + layer_idx * x_spacing
            y_spacing = min(0.8, 4.0 / max(n_neurons - 1, 1))
            start_y = -(n_neurons - 1) * y_spacing / 2

            for i in range(n_neurons):
                y = start_y + i * y_spacing
                neuron = Circle(radius=0.2, color=BLUE, fill_opacity=0.3)
                neuron.move_to([x, y, 0])
                layer_group.add(neuron)

            neuron_groups.append(layer_group)
            network_group.add(layer_group)

        # 创建连接线
        for layer_idx in range(n_layers - 1):
            for n1 in neuron_groups[layer_idx]:
                for n2 in neuron_groups[layer_idx + 1]:
                    line = Line(n1.get_center(), n2.get_center(), 
                              color=WHITE, stroke_width=1, stroke_opacity=0.3)
                    network_group.add(line)

        # 添加层标签
        for layer_idx, label in enumerate(layer_labels):
            if layer_idx < len(neuron_groups):
                x = start_x + layer_idx * x_spacing
                text = Text(label, font_size=20, font=FONT_ZH)
                text.move_to([x, -2.5, 0])
                network_group.add(text)

        # 动画：逐层显示
        for layer_idx, layer_group in enumerate(neuron_groups):
            self.play(FadeIn(layer_group), run_time=0.5)

        self.play(FadeIn(network_group), run_time=1.0)
        self.wait(2.0)
