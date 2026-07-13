# -*- coding: utf-8 -*-
"""
llm_codegen_service.py
方案C：LLM 直接生成 Manim Python 代码

当没有合适模板时，让 LLM 根据需求生成 Manim 代码
"""
import json
import os
import re
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

# Manim API 参考文档（给 LLM 参考）
MANIM_API_REFERENCE = """
# Manim Community Edition API 参考

## 基础图形
- `Text(text, font_size=24, color=WHITE)` - 文本
- `MathTex(tex_string, font_size=36)` - 数学公式（LaTeX）
- `Circle(radius=1.0, color=BLUE)` - 圆
- `Rectangle(width=4, height=2, color=GREEN)` - 矩形
- `Line(start, end, color=WHITE)` - 线段
- `Arrow(start, end, color=WHITE)` - 箭头
- `Dot(point, color=RED)` - 点
- `Polygon(*points, color=YELLOW)` - 多边形

## 布局
- `VGroup(*mobjects)` - 组合多个对象
- `.arrange(direction, buff=0.5)` - 排列
- `.next_to(mobject, direction, buff=0.5)` - 相对位置
- `.move_to(point)` - 移动到位置
- `.shift(direction * amount)` - 偏移

## 动画
- `Create(mobject)` - 创建（画线效果）
- `Write(mobject)` - 写入（文本/公式）
- `FadeIn(mobject)` - 淡入
- `FadeOut(mobject)` - 淡出
- `Transform(m1, m2)` - 变形
- `Indicate(mobject)` - 闪烁提示
- `Flash(point)` - 闪光

## 颜色
- WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, PINK
- ManimColor("#FF5733") - 自定义颜色

## 位置常量
- UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR
- ORIGIN (原点)
- 上下：UP * 2, DOWN * 3
- 左右：LEFT * 4, RIGHT * 2

## 场景结构
```python
from manim import *

class MyScene(Scene):
    def construct(self):
        # 创建对象
        text = Text("Hello")
        circle = Circle()
        
        # 动画
        self.play(Write(text))
        self.wait(1)
        self.play(Create(circle))
        self.wait(1)
        self.play(FadeOut(text), FadeOut(circle))
```

## TitleBar 用法（重要！）
TitleBar 是自定义封装类，不是 VMobject，不能用 Write(title_bar)！

```python
# 正确用法
title_bar = TitleBar("标题")
self.play(*title_bar.write_anims())  # 创建标题
# ... 其他动画 ...
self.play(*title_bar.fadeout_anims())  # 淡出标题
```

## 常用技巧
1. 居中：`mobject.move_to(ORIGIN)`
2. 等间距排列：`VGroup(a, b, c).arrange(RIGHT, buff=1)`
3. 上方：`text.next_to(circle, UP)`
4. 颜色渐变：`mobject.set_color_by_gradient(RED, BLUE)`
5. 描边：`mobject.set_stroke(WHITE, width=2)`
6. 填充：`mobject.set_fill(BLUE, opacity=0.5)`
"""

# 代码模板
CODE_TEMPLATE = '''# -*- coding: utf-8 -*-
"""
自动生成的 Manim 场景
主题: {title}
"""
from manim import *
import sys
sys.path.insert(0, r"{project_root}")
from templates.common import TitleBar, SubtitleBar, wrap_title, wrap_subtitle

# 画质配置
config.pixel_height = 480
config.pixel_width = 854
config.frame_rate = 15

class GeneratedScene(Scene):
    def construct(self):
        # 标题栏
        title_bar = TitleBar("{title}")
        self.play(*title_bar.write_anims())
        self.wait(0.5)
        
        # === 主要内容 ===
{content}
        
        # 结束
        self.play(*title_bar.fadeout_anims())
        self.wait(0.5)
'''


def generate_manim_code(
    title: str,
    requirements: str,
    llm_func=None
) -> dict:
    """
    使用 LLM 生成 Manim 代码
    
    Args:
        title: 场景标题
        requirements: 代码需求描述
        llm_func: 自定义 LLM 调用函数
    
    Returns:
        dict: {
            "success": bool,
            "code": str,  # 生成的代码
            "error": str  # 错误信息（如果有）
        }
    """
    if llm_func is None:
        from llm_storyboard_service import _get_llm_caller
        llm_func = _get_llm_caller()
    
    # 构建 prompt
    system_prompt = f"""你是一个 Manim 动画代码生成专家。根据用户的需求，生成可执行的 Manim Python 代码。

## Manim API 参考

{MANIM_API_REFERENCE}

## 代码规范

1. 必须包含 `construct()` 方法
2. 使用 TitleBar 创建标题（正确用法见上方参考）
3. 所有动画必须用 `self.play()` 调用
4. 每个重要动画后加 `self.wait(0.5-1.0)`
5. 结尾用 `title_bar.fadeout_anims()` 淡出标题
6. 代码必须是完整的、可直接执行的
7. 不要使用任何未导入的模块

## 输出格式

只输出 Python 代码，不要有其他文字。代码必须可以直接执行。

## 注意事项

- Text() 用于普通文本，MathTex() 用于数学公式
- 中文文本用 Text("中文", font="Microsoft YaHei")
- 颜色使用常量：WHITE, RED, BLUE, GREEN 等
- 位置使用：UP, DOWN, LEFT, RIGHT, ORIGIN
"""

    user_prompt = f"""请生成一个 Manim 动画场景：

标题：{title}
需求：{requirements}

请生成完整的、可执行的 Manim Python 代码。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        response = llm_func(messages)
        code = _extract_code(response)
        
        # 验证代码
        validation = validate_manim_code(code)
        if not validation["valid"]:
            return {
                "success": False,
                "code": None,
                "error": f"代码验证失败: {validation['error']}"
            }
        
        return {
            "success": True,
            "code": code,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "code": None,
            "error": f"LLM 生成失败: {str(e)}"
        }


def _extract_code(text: str) -> str:
    """从 LLM 响应中提取代码"""
    # 尝试提取 ```python ... ``` 代码块
    match = re.search(r'```python\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 尝试提取 ``` ... ``` 代码块
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 如果没有代码块，尝试直接使用（可能是纯代码）
    # 简单验证：包含 class 和 def
    if 'class ' in text and 'def construct' in text:
        return text.strip()
    
    raise ValueError("无法从 LLM 响应中提取有效的 Manim 代码")


def validate_manim_code(code: str) -> dict:
    """
    验证 Manim 代码的安全性和基本正确性
    
    Returns:
        dict: {"valid": bool, "error": str}
    """
    # 检查危险操作
    dangerous_patterns = [
        (r'\bimport\s+os\b', "不允许导入 os 模块"),
        (r'\bimport\s+subprocess\b', "不允许导入 subprocess 模块"),
        (r'\bimport\s+sys\b', "不允许导入 sys 模块"),
        (r'\beval\s*\(', "不允许使用 eval()"),
        (r'\bexec\s*\(', "不允许使用 exec()"),
        (r'\b__import__\b', "不允许使用 __import__"),
        (r'\bopen\s*\(', "不允许使用 open()"),
        (r'\bos\.', "不允许使用 os 模块"),
        (r'\bsubprocess\.', "不允许使用 subprocess 模块"),
        (r'\bsys\.', "不允许使用 sys 模块"),
        (r'\brmdir\b', "不允许删除目录"),
        (r'\brm\s+', "不允许删除文件"),
    ]
    
    for pattern, message in dangerous_patterns:
        if re.search(pattern, code):
            return {"valid": False, "error": message}
    
    # 检查必要结构
    if 'class ' not in code:
        return {"valid": False, "error": "缺少 Scene 类定义"}
    
    if 'def construct' not in code:
        return {"valid": False, "error": "缺少 construct() 方法"}
    
    if 'self.play' not in code and 'self.wait' not in code:
        return {"valid": False, "error": "缺少动画或等待语句"}
    
    return {"valid": True, "error": None}


def execute_manim_code(
    code: str,
    output_dir: str = None,
    quality: str = "medium"
) -> dict:
    """
    执行 Manim 代码并生成视频
    
    Args:
        code: Manim Python 代码
        output_dir: 输出目录
        quality: 画质 ("low", "medium", "high")
    
    Returns:
        dict: {
            "success": bool,
            "video_path": str,  # 生成的视频路径
            "error": str  # 错误信息（如果有）
        }
    """
    project_root = Path(__file__).parent
    manim_venv = project_root / ".venv_manim" / "Scripts" / "python.exe"
    
    if not manim_venv.exists():
        return {
            "success": False,
            "video_path": None,
            "error": "Manim 虚拟环境不存在"
        }
    
    # 创建临时文件
    temp_dir = project_root / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    temp_file = temp_dir / "generated_scene.py"
    
    # 添加必要的导入和配置
    full_code = f'''# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"{project_root}")
from manim import *
from templates.common import TitleBar, SubtitleBar, wrap_title, wrap_subtitle

# 画质配置
config.pixel_height = 480
config.pixel_width = 854
config.frame_rate = 15

{code}
'''
    
    # 写入临时文件
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(full_code)
    
    # 画质参数
    quality_args = {
        "low": ["-ql"],
        "medium": ["-qm"],
        "high": ["-qh"]
    }
    
    # 执行 Manim
    cmd = [
        str(manim_venv),
        "-m", "manim",
        *quality_args.get(quality, ["-qm"]),
        "--media_dir", str(project_root / "media"),
        str(temp_file),
        "GeneratedScene"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project_root)
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "video_path": None,
                "error": f"Manim 执行失败:\n{result.stderr[-500:]}"
            }
        
        # 查找生成的视频
        video_path = _find_generated_video(project_root / "media")
        
        if video_path:
            return {
                "success": True,
                "video_path": str(video_path),
                "error": None
            }
        else:
            return {
                "success": False,
                "video_path": None,
                "error": "找不到生成的视频文件"
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "video_path": None,
            "error": "Manim 执行超时（120秒）"
        }
    except Exception as e:
        return {
            "success": False,
            "video_path": None,
            "error": f"执行失败: {str(e)}"
        }
    finally:
        # 清理临时文件
        if temp_file.exists():
            temp_file.unlink()


def _find_generated_video(media_dir: Path) -> Optional[Path]:
    """查找 Manim 生成的视频文件"""
    # Manim 输出路径格式: media/videos/<name>/480p15/GeneratedScene.mp4
    for video_file in media_dir.rglob("GeneratedScene.mp4"):
        return video_file
    return None


# 测试
if __name__ == "__main__":
    # 测试代码验证
    test_code = '''
class GeneratedScene(Scene):
    def construct(self):
        title_bar = TitleBar("测试")
        self.play(*title_bar.write_anims())
        self.wait(1)
        self.play(*title_bar.fadeout_anims())
'''
    
    result = validate_manim_code(test_code)
    print(f"验证结果: {result}")
