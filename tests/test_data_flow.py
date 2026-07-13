import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

1|"""test_data_flow.py - 第 4 个新模板烟雾测试"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.manim_service import list_templates, render_manim_scene

print("=" * 60)
print("[1] 模板列表")
print("=" * 60)
for tid, meta in list_templates().items():
    print(f"  - [{meta['kind']:6}] {tid}")
print()

print("=" * 60)
print("[2] 渲染：神经网络前向传播 (3-4-4-2)")
print("=" * 60)
r = render_manim_scene(
    "data_flow",
    params={
        "title": "神经网络前向传播",
        "subtitle": "数据从输入层流到输出层",
        "layer_sizes": "3,4,4,2",
        "layer_labels": "输入层;隐层 ReLU;隐层 ReLU;输出层 Softmax",
        "pulse_count": 3,
        "show_arrows": True,
        "duration": 14.0,
    },
    quality="low",
    output_filename="data_flow_smoke",
)
print(f"  [OK] {r['video_path']}")
print(f"  size = {r['file_size_bytes']} bytes")
print()
print("[DONE] data_flow 通过！")
