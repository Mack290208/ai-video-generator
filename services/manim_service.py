"""
manim_service.py
----------------
用 subprocess 调用独立 Manim venv 渲染教学动画片段。

设计要点
========
- Manim 装在独立 venv（默认 .venv_manim），避免与 FastAPI / TTS 环境冲突
- 通过环境变量 MANIM_PYTHON 指向该 venv 的 python.exe
- 通过临时环境变量向 Scene 传参（避免改写模板源码）
- 输出 mp4 统一落到 outputs/manim/

模板系统（v2 模板工厂）
=======================
新模板放在 templates/ 目录，文件名 = 模板 id，必须导出：
  - 一个 Scene 子类（construct 里渲染）
  - PARAM_SCHEMA 字典（参数定义，给 LLM / 校验用）

manim_service 启动时会自动扫描 templates/，无需在这里登记。
旧的 manim_scenes/*.py 仍然支持（在 LEGACY_TEMPLATES 里登记），保留向后兼容。

参数注入
========
所有 v2 模板从环境变量 MANIM_PARAM_<KEY_UPPER> 读取参数，
由 templates/_param.py 提供的 param_str / param_float / ... 统一处理。
旧模板继续用各自的 MANIM_GD_xxx / MANIM_INTRO_xxx 命名，service 用
LEGACY_TEMPLATES 里的 env_whitelist 做映射。
"""

from __future__ import annotations

import importlib
import inspect
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MANIM_PYTHON = BASE_DIR / ".venv_manim" / "Scripts" / "python.exe"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "manim"
TEMPLATES_DIR = BASE_DIR / "templates"

# MiKTeX 默认 user-scope 安装路径（winget --scope user）
_MIKTEX_DEFAULT_BIN = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64"))


# ============================================================
# 旧模板登记（向后兼容；新模板请放 templates/ 目录自动发现）
# ============================================================
LEGACY_TEMPLATES: dict[str, dict[str, Any]] = {
    "gradient_descent": {
        "script": "manim_scenes/gradient_descent.py",
        "scene": "GradientDescentScene",
        "env_whitelist": {
            "title": "MANIM_GD_TITLE",
            "func_label": "MANIM_GD_FUNC_LABEL",
            "x_min": "MANIM_GD_X_MIN",
            "x_max": "MANIM_GD_X_MAX",
            "y_min": "MANIM_GD_Y_MIN",
            "y_max": "MANIM_GD_Y_MAX",
            "start_x": "MANIM_GD_START_X",
            "lr": "MANIM_GD_LR",
            "steps": "MANIM_GD_STEPS",
            "duration": "MANIM_GD_DURATION",
        },
    },
    "intro": {
        "script": "manim_scenes/intro.py",
        "scene": "IntroScene",
        "env_whitelist": {
            "title": "MANIM_INTRO_TITLE",
            "subtitle": "MANIM_INTRO_SUBTITLE",
            "duration": "MANIM_INTRO_DURATION",
        },
    },
    "outro": {
        "script": "manim_scenes/outro.py",
        "scene": "OutroScene",
        "env_whitelist": {
            "title": "MANIM_OUTRO_TITLE",
            "point_1": "MANIM_OUTRO_POINT_1",
            "point_2": "MANIM_OUTRO_POINT_2",
            "point_3": "MANIM_OUTRO_POINT_3",
            "point_4": "MANIM_OUTRO_POINT_4",
            "point_5": "MANIM_OUTRO_POINT_5",
            "duration": "MANIM_OUTRO_DURATION",
        },
    },
}


QUALITY_FLAGS = {
    "low": "-ql",       # 480p15
    "medium": "-qm",    # 720p30
    "high": "-qh",      # 1080p60
    "prod": "-qp",      # 1440p60
    "4k": "-qk",        # 2160p60
}


# ============================================================
# 模板自动发现（v2）
# ============================================================
def _discover_v2_templates() -> dict[str, dict[str, Any]]:
    """扫描 templates/ 目录，找出所有合法模板。

    合法条件：
    - 文件以非下划线开头（_param.py 之类的辅助文件被跳过）
    - 文件里有 **恰好一个** manim.Scene 子类
    - 文件里定义了 PARAM_SCHEMA dict（缺失则给空 schema）

    Returns
    -------
    {
      "<template_id>": {
         "module": "templates.<file_stem>",
         "script": "templates/<file_stem>.py",
         "scene": "<SceneClassName>",
         "schema": {...},
         "kind": "v2",
      },
      ...
    }
    """
    if not TEMPLATES_DIR.exists():
        return {}

    # 让 importlib 能找到 templates 包
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    # 延迟 import：进程的主 venv 不一定装了 manim，
    # 这里只用 importlib 拿到 PARAM_SCHEMA + Scene 类名（不真正构造 Scene）
    # 但 import 模板文件时会触发 `from manim import ...`——所以扫描必须在
    # Manim venv 里跑，或者跳过 import 错误。
    discovered: dict[str, dict[str, Any]] = {}

    for py_file in sorted(TEMPLATES_DIR.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "__init__.py":
            continue
        template_id = py_file.stem
        module_name = f"templates.{template_id}"

        try:
            # reload 避免同一进程多次扫描时拿到陈旧版本
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)
        except Exception as e:
            # 主进程没装 manim 也能继续——只记录脚本路径，scene 类名留空
            # 后续 render 时由子进程（Manim venv）真正解析
            discovered[template_id] = {
                "module": module_name,
                "script": f"templates/{py_file.name}",
                "scene": None,
                "schema": {},
                "kind": "v2",
                "import_error": str(e),
            }
            continue

        # 找 Scene 子类
        scene_name: str | None = None
        try:
            from manim import Scene as _ManimScene  # type: ignore

            for name, obj in vars(module).items():
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, _ManimScene)
                    and obj is not _ManimScene
                    and obj.__module__ == module_name  # 排除从其它模块 import 的
                ):
                    scene_name = name
                    break
        except Exception:
            # manim 没装也无所谓——靠模板内部约定 SceneClassName
            scene_name = None

        schema = getattr(module, "PARAM_SCHEMA", {})
        if not isinstance(schema, dict):
            schema = {}

        meta = getattr(module, "TEMPLATE_META", {})
        if not isinstance(meta, dict):
            meta = {}

        discovered[template_id] = {
            "module": module_name,
            "script": f"templates/{py_file.name}",
            "scene": scene_name,
            "schema": schema,
            "meta": meta,
            "kind": "v2",
        }

    return discovered


# 启动时扫描一次（懒加载也行，但启动时跑一次能尽早暴露 import 错误）
V2_TEMPLATES: dict[str, dict[str, Any]] = _discover_v2_templates()


def list_templates() -> dict[str, dict[str, Any]]:
    """返回所有可用模板（v2 + legacy 合并视图）。"""
    out: dict[str, dict[str, Any]] = {}
    for tid, meta in V2_TEMPLATES.items():
        out[tid] = {
            "kind": "v2",
            "script": meta["script"],
            "scene": meta.get("scene"),
            "schema": meta.get("schema", {}),
            "meta": meta.get("meta", {}),
        }
    for tid, meta in LEGACY_TEMPLATES.items():
        if tid in out:
            continue
        out[tid] = {
            "kind": "legacy",
            "script": meta["script"],
            "scene": meta["scene"],
            "schema": {},  # legacy 没 schema
            "meta": {},
            "env_whitelist": meta["env_whitelist"],
        }
    return out


def dump_template_catalog(only_v2: bool = True) -> dict[str, Any]:
    """导出可以直接喂给 LLM 的模板目录。

    输出结构：
    {
      "version": "v2",
      "count": 4,
      "templates": [
        {
          "id": "curve_descent",
          "summary": "...",
          "use_cases": [...],
          "not_for": [...],
          "params": {...},          # PARAM_SCHEMA 原样
          "example": {...},         # 例参数 dict
        },
        ...
      ]
    }

    Parameters
    ----------
    only_v2 : bool
        默认只导出 v2 模板（legacy 不推荐给 LLM 选用）。
    """
    items: list[dict[str, Any]] = []
    for tid, info in V2_TEMPLATES.items():
        meta = info.get("meta", {}) or {}
        items.append(
            {
                "id": tid,
                "summary": meta.get("summary", ""),
                "use_cases": list(meta.get("use_cases", [])),
                "not_for": list(meta.get("not_for", [])),
                "params": dict(info.get("schema", {}) or {}),
                "example": dict(meta.get("example_params", {}) or {}),
            }
        )
    if not only_v2:
        for tid, info in LEGACY_TEMPLATES.items():
            if any(it["id"] == tid for it in items):
                continue
            items.append(
                {
                    "id": tid,
                    "summary": "(legacy template, no metadata)",
                    "use_cases": [],
                    "not_for": [],
                    "params": {},
                    "example": {},
                    "legacy": True,
                }
            )

    items.sort(key=lambda x: x["id"])
    return {
        "version": "v2",
        "count": len(items),
        "templates": items,
    }


def get_template_schema(template: str) -> dict[str, Any]:
    """返回模板的参数 schema（供 LLM 用）。legacy 模板返回空 dict。"""
    if template in V2_TEMPLATES:
        return dict(V2_TEMPLATES[template].get("schema", {}))
    return {}


# ============================================================
# 参数校验
# ============================================================
class TemplateParamError(ValueError):
    pass


def _validate_params(template: str, params: dict[str, Any]) -> dict[str, Any]:
    """根据 PARAM_SCHEMA 校验+填默认值。仅 v2 模板生效。

    支持的 schema 字段：
      type:     str / float / int / bool
      required: bool
      default:  any
      allowed:  list[str]   （type=str 时使用）

    返回处理后的 params（已填默认、剔除未知 key 会 warn 但保留）。
    """
    if template not in V2_TEMPLATES:
        return dict(params)

    schema = V2_TEMPLATES[template].get("schema", {}) or {}
    out: dict[str, Any] = {}

    # 先处理已知 key
    for key, spec in schema.items():
        if key in params and params[key] is not None:
            value = params[key]
            ptype = spec.get("type", "str")
            try:
                if ptype == "float":
                    value = float(value)
                elif ptype == "int":
                    value = int(value)
                elif ptype == "bool":
                    value = bool(value)
                else:
                    value = str(value)
            except (TypeError, ValueError) as e:
                raise TemplateParamError(
                    f"模板 {template} 参数 {key} 类型应为 {ptype}，收到 {value!r}: {e}"
                )

            allowed = spec.get("allowed")
            if allowed and value not in allowed:
                raise TemplateParamError(
                    f"模板 {template} 参数 {key}={value!r} 不在允许集 {allowed}"
                )
            out[key] = value
        else:
            if spec.get("required", False):
                raise TemplateParamError(
                    f"模板 {template} 缺少必填参数: {key}"
                )
            if "default" in spec:
                out[key] = spec["default"]

    # 透传未知参数（给模板留扩展空间）
    for key, value in params.items():
        if key not in schema and value is not None:
            out[key] = value

    return out


# ============================================================
# 渲染
# ============================================================
def find_manim_python() -> str:
    env_path = os.getenv("MANIM_PYTHON")
    if env_path and Path(env_path).exists():
        return env_path
    if DEFAULT_MANIM_PYTHON.exists():
        return str(DEFAULT_MANIM_PYTHON)
    fallback = shutil.which("python")
    if fallback:
        return fallback
    raise RuntimeError(
        "找不到 Manim 的 Python 解释器。请设置环境变量 MANIM_PYTHON 指向 .venv_manim/Scripts/python.exe"
    )


def _resolve_template(template: str) -> tuple[Path, str, str, dict[str, str] | None]:
    """返回 (脚本绝对路径, Scene 类名, 模板 kind, env_whitelist 或 None)."""
    if template in V2_TEMPLATES:
        meta = V2_TEMPLATES[template]
        script_path = BASE_DIR / meta["script"]
        scene_name = meta.get("scene") or _guess_scene_name(template)
        return script_path, scene_name, "v2", None

    if template in LEGACY_TEMPLATES:
        meta = LEGACY_TEMPLATES[template]
        return (
            BASE_DIR / meta["script"],
            meta["scene"],
            "legacy",
            meta["env_whitelist"],
        )

    raise ValueError(
        f"未知模板: {template}。可用：v2={list(V2_TEMPLATES.keys())} legacy={list(LEGACY_TEMPLATES.keys())}"
    )


def _guess_scene_name(template_id: str) -> str:
    """v2 模板若 import 时拿不到 Scene 类名（主进程没装 manim），按命名约定猜。

    约定：camel_case -> CamelCaseScene
    """
    parts = template_id.split("_")
    return "".join(p.capitalize() for p in parts) + "Scene"


def render_manim_scene(
    template: str,
    params: dict[str, Any] | None = None,
    output_filename: str | None = None,
    output_dir: Path | str | None = None,
    quality: str = "medium",
    fps: int | None = None,
    manim_python: str | None = None,
    extra_args: list[str] | None = None,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """渲染一个 Manim 模板场景。

    Parameters
    ----------
    template : str
        模板 id（v2 模板自动发现 / legacy 模板手动登记）
    params : dict
        模板参数；v2 走 PARAM_SCHEMA 校验，legacy 走 env_whitelist 映射
    """
    params = params or {}
    script_path, scene_name, kind, env_whitelist = _resolve_template(template)

    if not script_path.exists():
        raise FileNotFoundError(f"模板脚本不存在: {script_path}")

    # 校验参数
    if kind == "v2":
        params = _validate_params(template, params)

    py = manim_python or find_manim_python()
    quality_flag = QUALITY_FLAGS.get(quality, "-qm")

    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = (
        _sanitize_name(output_filename) if output_filename else f"{template}_{scene_name}"
    )

    cmd: list[str] = [
        py,
        "-m",
        "manim",
        quality_flag,
        "--disable_caching",  # 模板工厂阶段：避免改了组件还吃旧缓存
        "--media_dir",
        str(out_dir),
        "-o",
        base_name,
    ]
    if fps:
        cmd += ["--fps", str(int(fps))]
    if extra_args:
        cmd += list(extra_args)
    cmd += [str(script_path), scene_name]

    # 环境变量
    env = os.environ.copy()

    # MiKTeX
    miktex_bin = os.getenv("MIKTEX_BIN")
    miktex_path = Path(miktex_bin) if miktex_bin else _MIKTEX_DEFAULT_BIN
    if miktex_path.exists():
        existing_path = env.get("PATH", "")
        if str(miktex_path) not in existing_path:
            env["PATH"] = f"{miktex_path};{existing_path}"

    # 让子进程能 import 我们的 components / layouts / templates 包
    project_root = str(BASE_DIR)
    existing_pp = env.get("PYTHONPATH", "")
    if project_root not in existing_pp.split(os.pathsep):
        env["PYTHONPATH"] = (
            f"{project_root}{os.pathsep}{existing_pp}" if existing_pp else project_root
        )

    # 注入参数
    if kind == "v2":
        # 统一前缀 MANIM_PARAM_<UPPER_KEY>
        for key, value in params.items():
            if value is None:
                continue
            env[f"MANIM_PARAM_{key.upper()}"] = str(value)
    else:
        # legacy: 走白名单映射
        for key, value in params.items():
            if value is None:
                continue
            env_var = (env_whitelist or {}).get(key)
            if not env_var:
                continue
            env[env_var] = str(value)

    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout_seconds,
        cwd=str(BASE_DIR),
    )

    stderr_tail = "\n".join((proc.stderr or "").splitlines()[-15:])
    stdout_tail = "\n".join((proc.stdout or "").splitlines()[-15:])

    if proc.returncode != 0:
        raise RuntimeError(
            f"manim 渲染失败 (exit={proc.returncode})\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDERR TAIL:\n{stderr_tail}\n"
            f"STDOUT TAIL:\n{stdout_tail}"
        )

    quality_subdir = _quality_subdir(quality_flag, fps)
    candidate = out_dir / "videos" / script_path.stem / quality_subdir / f"{base_name}.mp4"
    if not candidate.exists():
        matches = list(out_dir.rglob(f"{base_name}.mp4"))
        if not matches:
            raise RuntimeError(
                f"manim 渲染完成但找不到产物。预期: {candidate}\n"
                f"STDOUT TAIL:\n{stdout_tail}\nSTDERR TAIL:\n{stderr_tail}"
            )
        candidate = matches[0]

    return {
        "video_path": str(candidate),
        "template": template,
        "template_kind": kind,
        "scene": scene_name,
        "quality": quality,
        "cmd": " ".join(cmd),
        "file_size_bytes": candidate.stat().st_size,
        "stderr_tail": stderr_tail,
        "stdout_tail": stdout_tail,
    }


# ============================================================
# 工具函数
# ============================================================
def _sanitize_name(name: str) -> str:
    stem = Path(name).stem if Path(name).suffix else name
    return re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", stem)[:80] or "scene"


def _quality_subdir(quality_flag: str, fps: int | None) -> str:
    if fps:
        if quality_flag == "-ql":
            return f"480p{fps}"
        if quality_flag == "-qm":
            return f"720p{fps}"
        if quality_flag == "-qh":
            return f"1080p{fps}"
        if quality_flag == "-qp":
            return f"1440p{fps}"
        if quality_flag == "-qk":
            return f"2160p{fps}"
    return {
        "-ql": "480p15",
        "-qm": "720p30",
        "-qh": "1080p60",
        "-qp": "1440p60",
        "-qk": "2160p60",
    }.get(quality_flag, "720p30")
