import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

1|"""快速 smoke test - concept_compare 不带公式版本"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.manim_service import render_manim_scene

print("渲染：concept_compare（无公式版）...")
r = render_manim_scene(
    "concept_compare",
    params={
        "title": "信息增益 vs 基尼系数",
        "left_title": "信息增益",
        "right_title": "基尼系数",
        "left_point_1": "源自信息论，衡量分裂前后熵的减少",
        "left_point_2": "ID3 / C4.5 算法采用",
        "left_point_3": "对类别多的特征有偏好",
        "right_point_1": "衡量样本不纯度，越小越纯",
        "right_point_2": "CART 算法采用",
        "right_point_3": "无对数计算，速度更快",
        "duration": 14.0,
    },
    quality="low",
    output_filename="concept_compare_noformula",
)
print(f"[OK] {r['video_path']}  size={r['file_size_bytes']} bytes")
