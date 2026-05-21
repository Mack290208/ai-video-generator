"""
test_v2_new_templates.py
------------------------
第三阶段烟雾测试：
- bullet_summary（v2 替代 outro）
- lr_comparison  （新增的"学习率对比"教学模板）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.manim_service import (
    list_templates,
    get_template_schema,
    render_manim_scene,
)


def main() -> int:
    print("=" * 60)
    print("[1] 自动发现的模板列表")
    print("=" * 60)
    for tid, meta in list_templates().items():
        print(f"  - [{meta['kind']:6}] {tid:24} scene={meta.get('scene')}")
    print()

    print("=" * 60)
    print("[2] bullet_summary 渲染")
    print("=" * 60)
    r = render_manim_scene(
        "bullet_summary",
        params={
            "title": "本节回顾",
            "point_1": "梯度下降沿负梯度方向更新参数",
            "point_2": "学习率 α 控制每一步的更新幅度",
            "point_3": "α 太小收敛慢，太大会震荡发散",
            "duration": 8.0,
        },
        quality="low",
        output_filename="bullet_summary_smoke",
    )
    print(f"  [OK] {Path(r['video_path']).name}  size={r['file_size_bytes']} bytes")
    print()

    print("=" * 60)
    print("[3] lr_comparison schema")
    print("=" * 60)
    print(json.dumps(get_template_schema("lr_comparison"), ensure_ascii=False, indent=2)[:600], "...")
    print()

    print("=" * 60)
    print("[4] lr_comparison 渲染（α=0.05 vs α=0.7）")
    print("=" * 60)
    r = render_manim_scene(
        "lr_comparison",
        params={
            "title": "学习率的影响",
            "func_label": r"L(\theta) = (\theta - 2)^2",
            "lr_left": 0.05,
            "lr_left_label": "α=0.05 (太小)",
            "lr_right": 0.7,
            "lr_right_label": "α=0.7  (合适)",
            "steps": 8,
        },
        quality="low",
        output_filename="lr_comparison_smoke",
    )
    print(f"  [OK] {Path(r['video_path']).name}  size={r['file_size_bytes']} bytes")
    print()

    print("[DONE] 第三阶段两个新模板验证通过！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
