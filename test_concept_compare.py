"""
test_concept_compare.py
-----------------------
第五阶段第 1 个模板烟雾测试：concept_compare（双栏概念对比）

用决策树视频里 LLM 标记缺失的"信息增益 vs 基尼系数"作为典型样本验证。
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
    print("[1] 当前模板列表")
    print("=" * 60)
    tpls = list_templates()
    for tid, meta in tpls.items():
        print(f"  - [{meta['kind']:6}] {tid:24} scene={meta.get('scene')}")
    print()

    if "concept_compare" not in tpls:
        print("[FAIL] concept_compare 没被发现，检查 templates/concept_compare.py")
        return 1

    print("=" * 60)
    print("[2] concept_compare schema")
    print("=" * 60)
    schema = get_template_schema("concept_compare")
    print(json.dumps(schema, ensure_ascii=False, indent=2))
    print()

    print("=" * 60)
    print("[3] 渲染：信息增益 vs 基尼系数")
    print("=" * 60)
    r = render_manim_scene(
        "concept_compare",
        params={
            "title": "信息增益 vs 基尼系数",
            "left_title": "信息增益",
            "right_title": "基尼系数",
            "left_formula": r"IG = H(D) - \sum_v \frac{|D_v|}{|D|} H(D_v)",
            "right_formula": r"Gini(D) = 1 - \sum_i p_i^2",
            "left_point_1": "源自信息论，衡量分裂前后熵的减少",
            "left_point_2": "ID3 / C4.5 算法采用",
            "left_point_3": "对类别多的特征有偏好",
            "right_point_1": "衡量样本不纯度，越小越纯",
            "right_point_2": "CART 算法采用",
            "right_point_3": "无对数计算，速度更快",
            "left_color": "BLUE",
            "right_color": "YELLOW",
            "duration": 18.0,
        },
        quality="low",
        output_filename="concept_compare_smoke",
    )
    print(f"  [OK] {Path(r['video_path']).name}")
    print(f"  size = {r['file_size_bytes']} bytes")
    print(f"  path = {r['video_path']}")
    print()

    print("[DONE] concept_compare 烟雾测试通过！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
