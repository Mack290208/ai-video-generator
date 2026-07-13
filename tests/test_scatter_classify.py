import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

1|"""test_scatter_classify.py - 第 3 个新模板烟雾测试"""
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
print("[2] 渲染：线性可分二分类")
print("=" * 60)
r = render_manim_scene(
    "scatter_classify",
    params={
        "title": "线性可分二分类",
        "subtitle": "决策边界把两类样本分开",
        "class_a_label": "正类 (+1)",
        "class_b_label": "负类 (-1)",
        "class_a_points": "-3,1.5; -2.5,2.2; -2,1.8; -3.5,0.8; -2.8,0.3; -1.5,2.0; -2.2,2.5",
        "class_b_points": "2,-1.5; 2.5,-2.0; 3,-1.0; 1.8,-2.2; 3.2,-1.8; 1.5,-0.8; 2.8,-2.5",
        "boundary_kind": "linear",
        "boundary_a": 0.6,
        "boundary_b": 0.0,
        "show_regions": True,
        "duration": 14.0,
    },
    quality="low",
    output_filename="scatter_classify_smoke",
)
print(f"  [OK] {r['video_path']}")
print(f"  size = {r['file_size_bytes']} bytes")
print()
print("[DONE] scatter_classify 通过！")
