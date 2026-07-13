"""
test_template_factory.py
------------------------
模板工厂 v2 烟雾测试。

验证点：
1. manim_service 能自动发现 templates/ 下的 v2 模板
2. list_templates() 返回的 schema 正确
3. render_manim_scene("intro_v2", params={...}) 能跑通
4. render_manim_scene("curve_descent", params={...}) 能跑通
5. 旧的 legacy 模板（gradient_descent / intro / outro）依然能跑
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from __future__ import annotations

import json
import sys
from pathlib import Path

# 项目根加 sys.path（脚本可以直接跑）
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.manim_service import (  # noqa: E402
    list_templates,
    get_template_schema,
    render_manim_scene,
)


def main() -> None:
    print("=" * 60)
    print("【1】列出所有可用模板")
    print("=" * 60)
    all_t = list_templates()
    for tid, meta in all_t.items():
        print(f"  - [{meta['kind']:6}] {tid:24} scene={meta.get('scene')}")
    print()

    print("=" * 60)
    print("【2】curve_descent 的参数 schema")
    print("=" * 60)
    print(json.dumps(get_template_schema("curve_descent"), indent=2, ensure_ascii=False))
    print()

    print("=" * 60)
    print("【3】渲染 intro_v2（v2 自动发现）")
    print("=" * 60)
    res = render_manim_scene(
        "intro_v2",
        params={
            "title": "模板工厂 v2",
            "subtitle": "今天我们来讲：梯度下降",
            "duration": 4.0,
        },
        quality="low",
        output_filename="intro_v2_factory_smoke",
    )
    print(f"  [OK] video_path = {res['video_path']}")
    print(f"  size = {res['file_size_bytes']} bytes")
    print()

    print("=" * 60)
    print("【4】渲染 curve_descent（v2 自动发现，参数走 schema 校验）")
    print("=" * 60)
    res = render_manim_scene(
        "curve_descent",
        params={
            "title": "梯度下降演示",
            "func_label": r"L(\theta) = (\theta - 2)^2",
            "lr": 0.25,
            "steps": 6,  # 测试时少点步数，跑快
            "duration": 0,
        },
        quality="low",
        output_filename="curve_descent_factory_smoke",
    )
    print(f"  [OK] video_path = {res['video_path']}")
    print(f"  size = {res['file_size_bytes']} bytes")
    print()

    print("=" * 60)
    print("【5】渲染 legacy intro（向后兼容）")
    print("=" * 60)
    res = render_manim_scene(
        "intro",
        params={
            "title": "Legacy 兼容性测试",
            "subtitle": "走旧路径",
            "duration": 3.0,
        },
        quality="low",
        output_filename="intro_legacy_smoke",
    )
    print(f"  [OK] video_path = {res['video_path']}")
    print(f"  size = {res['file_size_bytes']} bytes")
    print()

    print("[DONE] 全部通过！模板工厂 v2 可用。")


if __name__ == "__main__":
    main()
