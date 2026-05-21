"""
templates/data_flow.py
----------------------
神经网络数据流模板：多层节点 + 全连接箭头 + 前向传播脉冲动画。

教学价值：
- 神经网络前向传播过程可视化
- 全连接 / 多层感知机 (MLP) 的拓扑结构
- "数据是怎么从输入流到输出的"
- 反向传播的引子（之后可以反向复用）

画面流程：
1. 标题
2. 各层节点 FadeIn（从左到右逐层）
3. 全连接箭头 Create
4. 黄色脉冲 N 波从输入流到输出（模拟前向传播）
5. 收尾保持

参数：
    title              - 主标题（必填）
    subtitle           - 副标题（可选）
    layer_sizes        - 各层节点数（如 "3,4,4,2"，逗号分隔）
    layer_labels       - 各层下方标签（如 "输入层;隐层 ReLU;隐层 ReLU;输出层 Softmax"，分号分隔）
    pulse_count        - 前向脉冲波数（默认 3）
    show_arrows        - 是否画箭头（默认 true）
    duration           - 期望总时长

设计：
- 节点最多 6 个/层（更多则塞不下）
- 层数最多 5 层（再多就用更宽画面或拆模板）
- 节点用半透明圆 + 白边，脉冲用小黄圆沿箭头滑过
"""

from __future__ import annotations

from typing import List

from manim import (
    Arrow,
    BLUE,
    Circle,
    Create,
    DOWN,
    Dot,
    FadeIn,
    GREEN,
    LEFT,
    MoveAlongPath,
    ORANGE,
    RIGHT,
    Scene,
    Text,
    UP,
    VGroup,
    WHITE,
    Write,
    YELLOW,
    Line,
)

from components import TitleBar
from layouts.constants import (
    FONT_ZH,
    FS_BODY,
    FS_SUBTITLE,
    SUBTITLE_TOP_Y,
)
from templates._param import param_bool, param_float, param_int, param_str


PARAM_SCHEMA = {
    "title": {"type": "str", "required": True},
    "subtitle": {"type": "str", "required": False, "default": ""},
    "layer_sizes": {
        "type": "str",
        "required": False,
        "default": "3,4,4,2",
    },
    "layer_labels": {
        "type": "str",
        "required": False,
        "default": "输入层;隐层 ReLU;隐层 ReLU;输出层",
    },
    "pulse_count": {"type": "int", "required": False, "default": 3},
    "show_arrows": {"type": "bool", "required": False, "default": True},
    "duration": {"type": "float", "required": False, "default": 0.0},
}


TEMPLATE_META = {
    "summary": "神经网络多层节点 + 全连接箭头 + 前向脉冲动画。可视化数据从输入层流到输出层的过程。",
    "use_cases": [
        "神经网络 / MLP / 全连接网络的结构展示",
        "前向传播过程可视化",
        "深度学习入门：从输入到输出的数据流",
        "反向传播的对照（先看正向，再看反向）",
    ],
    "not_for": [
        "RNN / Transformer 等带循环或注意力的复杂结构（拓扑不一样）",
        "卷积层（CNN，需要专门的 grid 模板）",
        "需要画特定权重值（这里只展示拓扑）",
        "层数 > 5 或单层节点 > 6（画面塞不下）",
    ],
    "example_params": {
        "title": "神经网络前向传播",
        "subtitle": "数据从输入层流到输出层",
        "layer_sizes": "3,4,4,2",
        "layer_labels": "输入层;隐层 ReLU;隐层 ReLU;输出层 Softmax",
        "pulse_count": 3,
        "duration": 14.0,
    },
}


def _parse_csv_ints(s: str, default: List[int]) -> List[int]:
    out: List[int] = []
    for chunk in s.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(max(1, min(6, int(chunk))))
        except ValueError:
            continue
    return out if out else default


def _parse_labels(s: str) -> List[str]:
    return [c.strip() for c in s.split(";")] if s.strip() else []


# 画面布局常量
LAYER_TOP_Y = 1.8           # 节点列最高 y
LAYER_BOTTOM_Y = -1.8       # 节点列最低 y（确保上方留给副标题、下方留给层标签）
NODE_RADIUS = 0.30
PULSE_RADIUS = 0.10


class DataFlowScene(Scene):
    """神经网络前向数据流。"""

    def construct(self):
        title_text = param_str("title", "神经网络前向传播")
        subtitle_text = param_str("subtitle", "")
        layer_sizes = _parse_csv_ints(param_str("layer_sizes", "3,4,4,2"), [3, 4, 4, 2])
        labels = _parse_labels(param_str("layer_labels", ""))
        pulse_count = max(1, min(5, param_int("pulse_count", 3)))
        show_arrows = param_bool("show_arrows", True)
        duration = param_float("duration", 0.0)

        # 限制层数 1~5
        layer_sizes = layer_sizes[:5]
        n_layers = len(layer_sizes)
        if n_layers < 2:
            layer_sizes = layer_sizes + [2]  # 至少两层
            n_layers = len(layer_sizes)

        scene_ran = 0.0

        def play_t(*anims, run_time: float = 1.0):
            nonlocal scene_ran
            self.play(*anims, run_time=run_time)
            scene_ran += run_time

        def wait_t(seconds: float):
            nonlocal scene_ran
            if seconds <= 0:
                return
            self.wait(seconds)
            scene_ran += seconds

        # ---------- 1. 标题 ----------
        bar = TitleBar(title=title_text)
        play_t(*bar.write_anims(), run_time=1.0)

        # ---------- 2. 副标题（可选） ----------
        if subtitle_text.strip():
            sub = Text(
                subtitle_text,
                font=FONT_ZH,
                font_size=FS_SUBTITLE - 4,
                color=WHITE,
            ).move_to([0, 2.55, 0])
            play_t(FadeIn(sub, shift=DOWN * 0.2), run_time=0.6)

        # ---------- 3. 计算各层节点位置 ----------
        # 横向均匀分布，留两端 1.0 单位边距
        x_left = -5.6
        x_right = +5.6
        if n_layers == 1:
            xs = [0.0]
        else:
            x_step = (x_right - x_left) / (n_layers - 1)
            xs = [x_left + i * x_step for i in range(n_layers)]

        # 每层 y 居中分布在 [LAYER_BOTTOM_Y, LAYER_TOP_Y]
        layer_node_positions: List[List[List[float]]] = []
        layer_groups: List[VGroup] = []
        for layer_idx, size in enumerate(layer_sizes):
            x = xs[layer_idx]
            if size == 1:
                ys = [0.0]
            else:
                y_step = (LAYER_TOP_Y - LAYER_BOTTOM_Y) / (size - 1) if size > 1 else 0
                # 限制最大间距 1.0，避免 1 节点撑得太开
                y_step = min(y_step, 1.0)
                total = (size - 1) * y_step
                ys = [(total / 2) - i * y_step for i in range(size)]

            positions: List[List[float]] = []
            nodes = VGroup()
            for y in ys:
                p = [x, y, 0]
                positions.append(p)
                node = Circle(
                    radius=NODE_RADIUS,
                    color=BLUE,
                    fill_color=BLUE,
                    fill_opacity=0.25,
                    stroke_width=2,
                ).move_to(p)
                nodes.add(node)
            layer_node_positions.append(positions)
            layer_groups.append(nodes)

        # ---------- 4. 逐层 FadeIn ----------
        for nodes in layer_groups:
            play_t(FadeIn(nodes, shift=RIGHT * 0.2), run_time=0.55)

        # ---------- 5. 层标签（在节点列下方） ----------
        if labels:
            label_y = LAYER_BOTTOM_Y - 0.6
            label_objs = []
            for layer_idx in range(n_layers):
                if layer_idx >= len(labels):
                    break
                txt = labels[layer_idx]
                if not txt:
                    continue
                t = Text(
                    txt,
                    font=FONT_ZH,
                    font_size=FS_BODY - 4,
                    color=WHITE,
                ).move_to([xs[layer_idx], label_y, 0])
                # 防止越过字幕区
                if t.get_bottom()[1] < SUBTITLE_TOP_Y + 0.05:
                    t.shift([0, (SUBTITLE_TOP_Y + 0.05) - t.get_bottom()[1], 0])
                label_objs.append(t)
            if label_objs:
                play_t(*[FadeIn(t) for t in label_objs], run_time=0.7)

        # ---------- 6. 全连接箭头 ----------
        all_lines: List[Line] = []
        if show_arrows and n_layers >= 2:
            arrows_group = VGroup()
            for li in range(n_layers - 1):
                src_positions = layer_node_positions[li]
                dst_positions = layer_node_positions[li + 1]
                for src in src_positions:
                    for dst in dst_positions:
                        # 从节点边缘到节点边缘的方向向量
                        # 简化：直接画两点连线，半透明白色
                        line = Line(
                            start=src,
                            end=dst,
                            color=WHITE,
                            stroke_width=1.2,
                        ).set_opacity(0.30)
                        arrows_group.add(line)
                        all_lines.append(line)
            play_t(Create(arrows_group), run_time=1.2)

        # ---------- 7. 前向脉冲（模拟数据流） ----------
        # 每一波：一组 dot 从输入层节点出发，沿连线一层一层走到输出层
        if all_lines:
            for wave in range(pulse_count):
                self._run_pulse_wave(layer_node_positions)
                scene_ran += 1.0 * (n_layers - 1) * 0.55  # 估算
        else:
            wait_t(0.5)

        # ---------- 8. 收尾保持 ----------
        wait_t(1.4)

        # ---------- 9. 时长对齐 ----------
        if duration and duration > 0:
            remaining = duration - scene_ran
            if remaining > 0.1:
                self.wait(remaining)

    # =================================================================
    def _run_pulse_wave(self, layer_node_positions: List[List[List[float]]]):
        """从输入层每个节点出发一颗黄点，依次走到下一层每个节点。"""
        n_layers = len(layer_node_positions)
        if n_layers < 2:
            return

        # 简化：每一段动画里，所有当前层->下一层的脉冲并行移动
        # 用 Dot + animate.move_to
        # 第一段：输入层每个节点的脉冲飞向第二层每个节点（多对多并行）
        for li in range(n_layers - 1):
            src_positions = layer_node_positions[li]
            dst_positions = layer_node_positions[li + 1]

            # 每条连线都发一颗脉冲（src×dst 条）。
            # 这样所有连线同时点亮，dst 每个节点都会接收到
            # 来自所有 src 的信号，恶看上去才是“真正的前向传播”。
            dots = VGroup()
            anims = []
            for src in src_positions:
                for target in dst_positions:
                    d = Dot(
                        point=src,
                        color=YELLOW,
                        radius=PULSE_RADIUS,
                    ).set_z_index(10)
                    dots.add(d)
                    anims.append(d.animate.move_to(target))

            self.add(dots)
            self.play(*anims, run_time=0.55)
            self.remove(dots)
