"""
test_catalog_dump.py
--------------------
验证 dump_template_catalog 输出能直接喂 LLM。
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.manim_service import dump_template_catalog


def main() -> int:
    cat = dump_template_catalog()
    print(f"count   = {cat['count']}")
    print(f"version = {cat['version']}")
    print()
    print("Templates:")
    for t in cat["templates"]:
        print(f"  - {t['id']:20} | {t['summary'][:50]}")
        print(f"      use_cases: {len(t['use_cases'])}, params: {len(t['params'])}")
    print()

    # 把整个 catalog 写到文件（给 LLM 用）
    out_path = ROOT / "outputs" / "template_catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[saved] {out_path}  ({out_path.stat().st_size} bytes)")
    print()

    # 完整看一项
    print("=== 完整示例：curve_descent ===")
    for t in cat["templates"]:
        if t["id"] == "curve_descent":
            print(json.dumps(t, ensure_ascii=False, indent=2))
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
