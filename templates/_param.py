"""
templates/_param.py
-------------------
模板内部统一的参数读取 helper。

设计原则
========
manim_service.py 调用模板时，会把 params dict 通过环境变量传入，
统一前缀为 MANIM_PARAM_<UPPER_KEY>。

模板里只需写：
    from templates._param import param_str, param_float, param_int, param_bool

    title = param_str("title", default="机器学习课堂")
    lr    = param_float("lr", default=0.25)

避免每个模板各自定义 _env_xxx 函数。
"""

from __future__ import annotations

import os
from typing import Optional


_PREFIX = "MANIM_PARAM_"


def _env(key: str) -> Optional[str]:
    v = os.getenv(_PREFIX + key.upper())
    if v is None:
        return None
    s = v.strip()
    return s if s else None


def param_str(key: str, default: str = "") -> str:
    v = _env(key)
    return v if v is not None else default


def param_float(key: str, default: float = 0.0) -> float:
    v = _env(key)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def param_int(key: str, default: int = 0) -> int:
    v = _env(key)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def param_bool(key: str, default: bool = False) -> bool:
    v = _env(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "y", "on")
