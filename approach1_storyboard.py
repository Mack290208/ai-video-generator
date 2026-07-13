# -*- coding: utf-8 -*-
"""
方案1: 精细分镜 (Detailed Storyboard)
=====================================
核心改进：音频先行，动画跟随音频时长。

流程：
  1. DeepSeek API 生成精细分镜 JSON（每段有 narration + visual_instructions + template + params）
  2. TTS 先行：为每段旁白生成音频，测量实际时长
  3. 用实际音频时长回填每段的 start_time / duration
  4. Manim 渲染：每段动画的 duration 参数 = 该段音频实际时长
  5. FFmpeg 合成：视频段拼接 + 音频合并 + 字幕烧录

与旧流水线的关键区别：
  - 旧：Manim 时长独立，音频被动拼接 → 音画不同步
  - 新：音频先生成并测量，Manim 时长 = 音频时长 → 精确同步

用法：
    python approach1_storyboard.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import wave
import contextlib
from pathlib import Path

# ============================================================
# 路径常量
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
MANIM_VENV = BASE_DIR / ".venv_manim" / "Scripts" / "python.exe"
OUTPUT_DIR = BASE_DIR / "outputs" / "approach1"
AUDIO_DIR = OUTPUT_DIR / "audio"
VIDEO_DIR = OUTPUT_DIR / "video"
TEMP_DIR = OUTPUT_DIR / "temp"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"

for d in (AUDIO_DIR, VIDEO_DIR, TEMP_DIR, SUBTITLE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# 桌面输出
DESKTOP = Path.home() / "Desktop"

# ============================================================
# 加载 .env
# ============================================================
def load_dotenv(env_path: Path) -> None:
    """加载 .env 文件到 os.environ（不覆盖已有的变量）。"""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        # 去除可能的引号
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        os.environ.setdefault(key, val)


# ============================================================
# 步骤 1: DeepSeek 生成精细分镜
# ============================================================

STORYBOARD_SYSTEM_PROMPT = r"""你是一个 AI 教学视频分镜师。你需要为一个机器学习知识点生成**精细分镜脚本**。

## 输出格式（严格 JSON）

```json
{
  "video_title": "视频主标题",
  "duration_target_seconds": 180,
  "segments": [
    {
      "id": 1,
      "template": "intro_v2",
      "narration": "这段的旁白文字（中文，口语化，适合TTS朗读）",
      "subtitle": "字幕文字（可与旁白略有不同，更精炼）",
      "visual_instructions": "对画面的具体描述",
      "params": {
        "title": "标题文字",
        "subtitle": "副标题",
        "duration": 5.0
      }
    },
    {
      "id": 2,
      "template": "custom",
      "narration": "旁白内容",
      "subtitle": "字幕",
      "visual_instructions": "画一只猫和一个西瓜",
      "manim_code": "from manim import *\nclass CustomScene(Scene):\n    def construct(self):\n        # 你的 Manim 代码\n        self.wait(5)",
      "params": {}
    }
  ]
}
```

**注意：每个 segment 二选一：**
- 用模板：设置 `"template": "模板名"` + `"params": {...}`
- 用自定义代码：设置 `"template": "custom"` + `"manim_code": "..."` （此时 params 可以为空）

## 可用模板及其参数

### intro_v2（开场页）
- title: 主标题（必填）
- subtitle: 副标题（可选）
- duration: 时长（秒，会被实际音频时长覆盖）

### curve_descent（曲线下降动画）
- title: 主标题（必填）
- func_label: 函数公式 LaTeX，如 L(\\theta) = (\\theta - 2)^2
- rule_label: 更新规则 LaTeX（可选）
- x_min, x_max, y_min, y_max: 坐标范围
- start_x: 起始点
- lr: 学习率
- steps: 迭代步数
- func_kind: quadratic_centered_at_2 或 quadratic_centered_at_0

### formula_evolve（公式推导链路，水平版）
- title: 主标题（必填）
- step_1..step_4: LaTeX 公式（⚠ 绝对不能含中文！中文放 caption）
- caption_1..caption_4: 步骤说明（中文，**每个 caption 不超过 8 个字**，太长会重叠）
- final_emphasis: 是否高亮最后一步（默认 true）
- duration: 时长
- **重要：step_X 字段只能写纯数学公式如 L(\\theta)、\\nabla L(\\theta)，不能写中文！中文说明放 caption_X**
- **caption 要极简：如「输入特征」「学习映射」「最优解」，不要写长句子**

### lr_comparison（学习率对比，左右分屏）
- title: 主标题（必填）
- func_label: 函数公式 LaTeX
- start_x: 共同起点
- lr_left, lr_right: 左右学习率
- lr_left_label, lr_right_label: 左右标签
- steps: 每边步数
- duration: 时长

### concept_compare（概念双栏对比）
- title: 主标题（必填）
- left_title, right_title: 左右栏标题（必填）
- left_formula, right_formula: LaTeX 公式（可选）
- left_point_1..3, right_point_1..3: 要点
- duration: 时长

### bullet_summary（要点总结）
- title: 主标题（必填）
- point_1..point_5: 要点文字
- duration: 时长

### data_flow（神经网络数据流）
- title: 主标题（必填）
- subtitle: 副标题
- layer_sizes: 各层节点数，逗号分隔如 "3,4,2"
- layer_labels: 各层标签，分号分隔
- pulse_count: 脉冲次数
- duration: 时长

## 何时用模板 vs 自定义代码

**用模板的场景：**
- 开场/结尾 → intro_v2
- 要点列举/总结 → bullet_summary
- 公式推导链路 → formula_evolve
- 两个概念的明确对比 → concept_compare（如"回归 vs 分类"）
- 梯度下降/优化动画 → curve_descent
- 学习率对比 → lr_comparison
- 神经网络结构 → data_flow

**用自定义代码的场景：**
- 需要画具体物体（猫、西瓜、水果摊等）
- 需要讲故事/举例（"想象一下..."）
- 需要自定义动画效果（流程图、因果关系、类比图示）
- 模板都不能很好地匹配内容时

**判断标准：这段旁白在说什么，动画就应该画什么。**

## 自定义 Manim 代码规范

当 `template: "custom"` 时，必须提供 `manim_code` 字段。

### 代码结构
```python
from manim import *

class CustomScene(Scene):
    def construct(self):
        # 你的动画代码
        # ... 各种 Manim 对象和动画 ...
        self.wait(1)  # 最后保持画面
```

### 重要约束
1. **类名必须是 `CustomScene`**，继承 `Scene`
2. **中文字体**：`Text("中文", font="Microsoft YaHei")` — 用微软雅黑
3. **字号不要太大**：标题 34，正文 22-28，避免文字溢出
4. **文字位置**：标题放 y=3.4 附近，正文内容在 y∈[-2.4, 2.8] 之间
5. **不要用 MathTex 写中文**！中文必须用 Text()，公式用 MathTex()
6. **画面尺寸**：1280×720，安全区域 x∈[-6.5, 6.5], y∈[-3.5, 3.5]
7. **不要在最后 self.wait() 超过 2 秒**（总时长由外部自动控制）
8. **颜色**：深色背景上用亮色文字（WHITE, YELLOW, GREEN 等）
9. **只用下面列出的 API，不要用其他类或参数！**
10. **物体间距**：并排物体之间至少间隔 2.5 单位，上下物体之间至少间隔 1.2 单位。文字标签不能互相重叠！如果空间不够，就减少物体数量或缩小字号。
11. **标签用多行**：特征标签用 `\n` 换行显示，不要挤在一行。例如：`Text("颜色:绿\n根蒂:有\n敲声:清脆", font_size=18)`

### 可用 Manim 类和函数（白名单）
```
# 场景
Scene

# 文字（中文必须用 Text！）
Text(text, font="Microsoft YaHei", font_size=28, color=WHITE)
MathTex(r"公式")  # 只能写纯数学公式，不能含中文

# 几何图形
Circle(radius=1, color=BLUE, fill_opacity=0.8)
Rectangle(width=3, height=1.5, color=YELLOW)  # ⚠ 没有 corner_radius 参数！
Square(side_length=2, color=RED)
Triangle(color=GREEN)  # ⚠ 没有 corner_radius 参数！
Line(start=LEFT, end=RIGHT)
Arrow(start=LEFT*2, end=RIGHT*2, color=GREEN)
Dot(point=[x, y, 0], color=RED)
Arc(radius=1, start_angle=0, angle=PI, color=BLUE)

# 分组和排列
VGroup(obj1, obj2, ...)  # 分组
group.arrange(RIGHT, buff=0.5)  # 水平排列
group.arrange(DOWN, buff=0.3)   # 垂直排列

# 位置移动
obj.to_edge(UP, buff=0.5)
obj.to_edge(DOWN)
obj.move_to([x, y, 0])
obj.next_to(other_obj, RIGHT, buff=0.2)
obj.shift(RIGHT * 2)
obj.scale(1.5)

# 常用方向常量
UP, DOWN, LEFT, RIGHT, ORIGIN
UL, UR, DL, DR  # 四角

# 常用颜色
WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, GRAY, PINK
DARK_BLUE, DARK_BROWN, LIGHT_GRAY, GOLD
GREEN_A (浅绿), GREEN_E (深绿), RED_A, RED_E, BLUE_A, BLUE_E  # ⚠ 没有 DARK_GREEN！用 GREEN_E

# 动画
Write(obj)                    # 书写/画出文字
FadeIn(obj)                   # 淡入
FadeOut(obj)                  # 淡出
Create(obj)                   # 画出几何图形
Transform(obj1, obj2)         # 变形
obj.animate.shift(RIGHT*2)    # 动画移动
obj.animate.scale(2)          # 动画缩放
obj.animate.set_color(RED)    # 动画变色
```

### ⚠ 绝对不能用的 API（黑名单）
```
SpeechBubble    — 不存在！用 Rectangle + Text 模拟
RoundedRectangle — 不一定可用，用 Rectangle 代替
corner_radius   — 不是合法参数！
DARK_GREEN      — 不存在！用 GREEN_E（深绿）或 GREEN_A（浅绿）
DARK_RED        — 不存在！用 RED_E
Dot3D, Line3D   — 3D 类在 720p 下效果差，不要用
SVGMobject      — 需要 SVG 文件，不要用
ImageMobject    — 需要图片文件，不要用
Axes, NumberPlane — 坐标系用 curve_descent 模板更合适
MathTex 中文     — MathTex 里绝对不能写中文！中文用 Text()
```

### 常用 Manim 元素速查
```python
# 文字（多行用 \n）
title = Text("标题", font="Microsoft YaHei", font_size=34, color=WHITE)
label = Text("颜色:绿\n根蒂:有\n敲声:清脆", font="Microsoft YaHei", font_size=20)  # 多行标签！
title.to_edge(UP, buff=0.5)  # 移到顶部
title.move_to([0, 3.4, 0])   # 移到指定位置

# 几何图形
circle = Circle(radius=1, color=BLUE)
rect = Rectangle(width=3, height=1.5, color=YELLOW)
arrow = Arrow(start=LEFT*2, end=RIGHT*2, color=GREEN)
line = Line(start=LEFT, end=RIGHT)

# 数学公式（不能含中文！）
formula = MathTex(r"L(\theta) = (\theta - 2)^2")

# 分组
group = VGroup(obj1, obj2, obj3)
group.arrange(RIGHT, buff=0.5)  # 水平排列
group.arrange(DOWN, buff=0.3)   # 垂直排列

# 动画
self.play(Write(title))           # 书写效果
self.play(FadeIn(obj))            # 淡入
self.play(Transform(a, b))        # 变形
self.play(obj.animate.shift(RIGHT * 2))  # 移动
self.play(Create(circle))         # 画出图形
self.wait(1)                      # 停留
```

### 示例：画一只猫和一个西瓜
```python
from manim import *

class CustomScene(Scene):
    def construct(self):
        # 标题
        title = Text("机器学习的例子", font="Microsoft YaHei", font_size=34, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title))

        # 画一只简笔画猫（用圆形+三角形）
        cat_head = Circle(radius=0.6, color=ORANGE, fill_opacity=0.8)
        cat_ear_l = Triangle(color=ORANGE, fill_opacity=0.8).scale(0.25).move_to([-.35, .55, 0])
        cat_ear_r = Triangle(color=ORANGE, fill_opacity=0.8).scale(0.25).move_to([.35, .55, 0])
        cat_eye_l = Dot(point=[-.2, .1, 0], color=BLACK)
        cat_eye_r = Dot(point=[.2, .1, 0], color=BLACK)
        cat = VGroup(cat_head, cat_ear_l, cat_ear_r, cat_eye_l, cat_eye_r)
        cat.shift(LEFT * 2.5)
        self.play(FadeIn(cat))

        # 画一个西瓜
        melon = Circle(radius=0.7, color=GREEN, fill_opacity=0.9)
        melon_stripe = Arc(radius=0.7, start_angle=PI/4, angle=PI/2, color=DARK_GREEN)
        melon = VGroup(melon, melon_stripe)
        melon.shift(RIGHT * 2.5)
        self.play(FadeIn(melon))

        # 标签
        cat_label = Text("猫", font="Microsoft YaHei", font_size=28, color=ORANGE)
        cat_label.next_to(cat, DOWN)
        melon_label = Text("西瓜", font="Microsoft YaHei", font_size=28, color=GREEN)
        melon_label.next_to(melon, DOWN)
        self.play(Write(cat_label), Write(melon_label))

        self.wait(1)
```

## 重要规则

1. **旁白口语化**：不要写书面语，要像老师在课堂上讲话一样自然
2. **每段旁白 15~40 个中文字**：太长学生记不住，太短信息量不足
3. **旁白要有停顿感**：列举多个项目时，用句号「。」分隔，不要用逗号连在一起。例如：
   - ❌ 错误：「颜色深绿是好瓜，声音清脆是好瓜，颜色深绿且声音清脆是好瓜」
   - ✅ 正确：「第一种，颜色深绿就是好瓜。第二种，声音清脆就是好瓜。第三种，颜色深绿且声音清脆，才是好瓜。」
   - 关键词之间、列举项之间必须有明显的断句，让 TTS 有停顿
4. **visual_instructions 要具体**：不要写"展示梯度下降"，要写"在坐标系 x∈[-3,5], y∈[0,12] 上画二次函数 (θ-2)² 曲线，用蓝色表示；黄色圆点从 θ₀=-2.5 开始，每步沿负梯度方向移动，留下绿色轨迹点"
5. **params.duration 只是占位**：实际渲染时会被音频时长覆盖，但请写一个合理的参考值
6. **总计 5~8 个 segment**，总旁白文字量控制在 180~350 字
7. **教学逻辑**：开场引入 → 核心概念 → 公式解释 → 可视化演示 → 对比/拓展 → 总结收尾
8. **只输出 JSON，不要有任何其它文字**
9. **动画必须跟旁白内容匹配**

## 模板选择指南（重要！）

- **intro_v2**：只用于开场和结尾
- **bullet_summary**：最通用，用于列举要点、总结、步骤说明
- **curve_descent**：需要展示梯度下降/优化过程时使用
- **lr_comparison**：需要对比两种学习率效果时使用
- **formula_evolve**：需要展示**纯数学公式推导链路**时使用（如 3×4×4+1=49 这种计算过程）
- **concept_compare**：**仅用于**两个明确对立/并列概念的对比（如"监督学习 vs 无监督学习"），不要硬套
- **data_flow**：展示神经网络结构、数据流向
- **不要为了用模板而用模板**：如果内容更适合用 bullet_summary 讲清楚，就用 bullet_summary，不要强行用 concept_compare

## LaTeX 规则（极其重要！⚠）

**formula_evolve 的 step_X 字段只能写纯数学公式，绝对不能包含任何中文字符！**
- ✅ 正确：`3 \\times 4 \\times 4 + 1 = 49`、`|\\mathcal{H}| = \\prod_{i=1}^{m} |\\text{dom}(x_i)| + 1`
- ✅ 正确：`L(\\theta) = (\\theta - 2)^2`
- ❌ 错误：`\\text{输入：西瓜特征}`（含中文！）
- ❌ 错误：`\\text{数据} \\rightarrow \\text{模型} \\rightarrow \\text{预测}`（含中文！）
- 中文说明放在 caption_X 字段，LaTeX 公式放 step_X 字段

同理，concept_compare 的 left_formula / right_formula 也不能含中文。
curve_descent 的 func_label / rule_label 也不能含中文。
"""


def call_deepseek(messages: list, api_key: str) -> str:
    """调用 DeepSeek API，返回纯文本响应。"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 8000,
    }).encode()

    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    """从 LLM 响应中提取 JSON 对象。"""
    # 尝试从 ```json ... ``` 代码块中提取
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试从 ``` ... ``` 代码块中提取
    m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试直接解析整段文本
    # 找到第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = text[start:end + 1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 修复常见问题：LaTeX 反斜杠未转义
            # \theta → \\theta，但要避免双重转义
            fixed = raw.replace("\\\\", "\x00")  # 保护已有的 \\
            fixed = re.sub(r'\\(?![\\nrtbfu"/])', r'\\\\', fixed)
            fixed = fixed.replace("\x00", "\\\\")
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
    raise ValueError("无法从 LLM 响应中提取 JSON")


def generate_storyboard(topic: str, api_key: str, task_id: str) -> dict:
    """Step 1: 调用 DeepSeek 生成精细分镜 JSON。"""
    print("=" * 60)
    print(f"[Step 1/5] 生成精细分镜 — 主题: {topic}")
    print("=" * 60)

    user_prompt = f"""请为「{topic}」这个知识点生成精细分镜脚本。

背景：这是《机器学习》（周志华著，俗称"西瓜书"）的教学视频系列，面向大学生。
要求：
1. 内容准确，符合西瓜书的讲解体系
2. 总时长目标 2.5~3.5 分钟（150~210 秒）
3. 8~12 个 segment
4. 用中文旁白，口语化，像老师在课堂上讲课的语气，适合 TTS 朗读
5. visual_instructions 要足够具体，让渲染引擎知道画什么
6. 严格按 JSON 格式输出

请直接输出 JSON。"""

    messages = [
        {"role": "system", "content": STORYBOARD_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    print("  → 调用 DeepSeek API ...")
    raw = call_deepseek(messages, api_key)
    print(f"  ← 收到 {len(raw)} 字符响应")

    storyboard = extract_json(raw)

    # 验证基本结构
    assert "segments" in storyboard, "JSON 缺少 segments 字段"
    assert len(storyboard["segments"]) >= 3, "segment 数量太少"

    # 保存
    sb_path = OUTPUT_DIR / f"{task_id}_storyboard.json"
    sb_path.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ 分镜已保存: {sb_path.name}")
    print(f"  ✓ {len(storyboard['segments'])} 个 segment, "
          f"目标时长 {storyboard.get('duration_target_seconds', '?')}s")

    return storyboard


# ============================================================
# 步骤 2: TTS 先行 — 生成音频并测量实际时长
# ============================================================

def get_wav_duration(wav_path: Path) -> float:
    """读取 WAV 文件时长（秒）。"""
    with contextlib.closing(wave.open(str(wav_path), "rb")) as w:
        return w.getnframes() / float(w.getframerate())


def generate_tts_segment(
    text: str,
    output_path: Path,
    ref_audio: str = "",
    prompt_text: str = "",
) -> tuple[Path, float]:
    """生成单段 TTS 音频。支持两种引擎：
    
    - edge (默认): Edge TTS 云希，免费、快速、音质好
    - gpt-sovits: GPT-SoVITS 本地推理，支持音色克隆
    
    通过 TTS_PROVIDER 环境变量切换。

    Returns
    -------
    (audio_path, duration_seconds)
    """
    provider = os.getenv("TTS_PROVIDER", "edge").lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if provider == "gpt-sovits":
        _tts_gpt_sovits(text, output_path, ref_audio, prompt_text)
    else:
        _tts_edge(text, output_path)

    duration = get_wav_duration(output_path)
    return output_path, duration


def _tts_edge(text: str, output_path: Path) -> None:
    """Edge TTS (云希) 生成音频，mp3 转 wav。"""
    import subprocess

    voice = os.getenv("EDGE_TTS_VOICE", "zh-CN-YunxiNeural")
    rate = os.getenv("EDGE_TTS_RATE", "+10%")

    mp3_path = output_path.with_suffix(".mp3")
    cmd = [
        sys.executable, "-m", "edge_tts",
        "--voice", voice,
        "--rate", rate,
        "--text", text,
        "--write-media", str(mp3_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Edge TTS 失败: {result.stderr[:200]}")

    # mp3 转 wav
    cmd_ffmpeg = [
        "ffmpeg", "-y", "-i", str(mp3_path),
        "-ar", "22050", "-ac", "1",
        str(output_path),
    ]
    result = subprocess.run(cmd_ffmpeg, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"mp3→wav 转换失败: {result.stderr[:200]}")

    mp3_path.unlink(missing_ok=True)


def _tts_gpt_sovits(text: str, output_path: Path, ref_audio: str, prompt_text: str) -> None:
    """GPT-SoVITS 本地推理，支持音色克隆。"""
    base_url = os.getenv("GPT_SOVITS_BASE_URL", "http://127.0.0.1:9880")
    if not ref_audio:
        ref_audio = os.getenv("GPT_SOVITS_REF_AUDIO", "")
    if not prompt_text:
        prompt_text = os.getenv("GPT_SOVITS_PROMPT_TEXT", "机器学习是人工智能的核心")

    params = {
        "refer_wav_path": ref_audio,
        "prompt_text": prompt_text,
        "prompt_language": os.getenv("GPT_SOVITS_PROMPT_LANG", "zh"),
        "text": text,
        "text_language": os.getenv("GPT_SOVITS_TEXT_LANG", "zh"),
    }
    url = f"{base_url}/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=120) as resp:
        audio_data = resp.read()

    output_path.write_bytes(audio_data)


def _fix_segments(segments: list[dict]) -> None:
    """自动修复 LLM 生成的分镜 JSON 中缺失的关键字段。

    DeepSeek 有时不会严格按照 {narration, params, visual_instructions} 格式输出。
    这个函数就地修复：
    1. narration 缺失 → 从 title/subtitle 构造
    2. params 缺失 → 把模板相关字段收集到 params
    3. visual_instructions 缺失 → 用模板名 + params 生成占位
    """
    PARAM_KEYS_BY_TEMPLATE = {
        "intro_v2": ["title", "subtitle"],
        "curve_descent": ["title", "left_title", "right_title", "left_formula", "right_formula",
                          "left_point_1", "left_point_2", "right_point_1", "right_point_2"],
        "formula_evolve": ["title", "step_1", "step_2", "step_3", "step_4",
                           "caption_1", "caption_2", "caption_3", "caption_4", "final_emphasis"],
        "concept_compare": ["title", "left_title", "right_title", "left_formula", "right_formula",
                            "left_point_1", "left_point_2", "left_point_3",
                            "right_point_1", "right_point_2", "right_point_3"],
        "bullet_summary": ["title", "point_1", "point_2", "point_3", "point_4"],
        "data_flow": ["title", "subtitle", "layer_sizes", "layer_labels"],
        "lr_comparison": ["title", "func_label", "start_x", "lr_left", "lr_right",
                          "label_left", "label_right"],
        "scatter_classify": ["title", "func_label", "rule_label", "x_min", "x_max"],
        "neural_network": ["title", "subtitle", "layer_sizes", "layer_labels"],
        "decision_tree": ["title", "root_label", "left_label", "right_label",
                          "left_left_label", "left_right_label", "right_left_label", "right_right_label"],
        "knn_demo": ["title", "k_value"],
        "overfitting": ["title", "func_label", "start_x"],
        "confusion_matrix": ["title"],
        "bullet_summary_v2": ["title", "point_1", "point_2", "point_3"],
        "gradient_descent": ["title"],
    }

    for seg in segments:
        template = seg.get("template", "unknown")
        param_keys = PARAM_KEYS_BY_TEMPLATE.get(template, [])

        # 1. 补 narration
        if "narration" not in seg or not seg["narration"]:
            title = seg.get("title", "")
            subtitle = seg.get("subtitle", "")
            if subtitle:
                seg["narration"] = f"{title}。{subtitle}" if title else subtitle
            elif title:
                seg["narration"] = title
            else:
                # 最后兜底：从 params 文本字段拼
                text_parts = []
                for k in ["point_1", "point_2", "point_3", "point_4",
                           "caption_1", "caption_2", "left_title", "right_title"]:
                    v = seg.get(k, "")
                    if v and not v.startswith("\\") and len(v) > 2:
                        text_parts.append(v)
                seg["narration"] = "；".join(text_parts[:3]) if text_parts else "请看动画演示。"

        # 2. 补 params（把模板相关字段移到 params 里）
        if "params" not in seg or not seg["params"]:
            params = {}
            for k in param_keys:
                if k in seg:
                    params[k] = seg.pop(k)
            # 也收集未知的模板字段
            for k, v in list(seg.items()):
                if k not in ("id", "template", "narration", "subtitle",
                             "visual_instructions", "params", "duration", "manim_code", "title"):
                    if isinstance(v, (str, int, float, bool, list)):
                        params[k] = v
            seg["params"] = params
            if "title" not in seg and "title" in params:
                seg["title"] = params["title"]

        # 3. 补 visual_instructions
        if "visual_instructions" not in seg or not seg["visual_instructions"]:
            title = seg.get("title", seg.get("params", {}).get("title", ""))
            seg["visual_instructions"] = f"使用 {template} 模板展示「{title}」"

        # 3.5 清理所有 LaTeX 字段中的中文（会导致黑屏）
        import re
        LATEX_FIELDS = {
            "formula_evolve": ["step_1", "step_2", "step_3", "step_4"],
            "concept_compare": ["left_formula", "right_formula"],
            "curve_descent": ["func_label", "rule_label"],
            "lr_comparison": ["func_label"],
            "scatter_classify": ["func_label"],
        }
        latex_keys = LATEX_FIELDS.get(template, [])
        params = seg.get("params", {})
        for k in latex_keys:
            val = params.get(k, "")
            if val and re.search(r'[\u4e00-\u9fff]', val):
                # 找到对应的 caption 字段（如果有）
                caption_key = k.replace("step_", "caption_").replace("func_label", "caption").replace("rule_label", "caption_rule")
                if not params.get(caption_key):
                    chinese_parts = re.findall(r'[\u4e00-\u9fff：:、，。（）()]+', val)
                    if chinese_parts:
                        params[caption_key] = "".join(chinese_parts)
                # 清除 LaTeX 中的中文
                clean = re.sub(r'\\text\{[^}]*[\u4e00-\u9fff][^}]*\}', '', val)
                clean = re.sub(r'[\u4e00-\u9fff：:、，。]+', '', clean).strip()
                if clean and len(clean) > 2:
                    params[k] = clean
                else:
                    # 无法修复，给个安全的占位
                    if "step_" in k:
                        params[k] = f"\\mathrm{{step}}_{k[-1]}"
                    else:
                        params[k] = "f(x)"

        # 4. 补 subtitle
        if "subtitle" not in seg or not seg["subtitle"]:
            seg["subtitle"] = seg["narration"]

    print(f"  ✓ 分镜字段修复完成（{len(segments)} segments）")


def generate_all_tts(storyboard: dict, task_id: str) -> list[dict]:
    """Step 2: 为每段旁白生成 TTS 音频，测量实际时长。

    Returns
    -------
    音频结果列表，每项包含:
      segment_id, narration, audio_path, audio_duration_seconds
    """
    print()
    print("=" * 60)
    print("[Step 2/5] TTS 先行 — Edge TTS (云希) 生成音频")
    print("=" * 60)

    segments = storyboard["segments"]
    # --- 自动修复：补全缺失的 narration / params / visual_instructions ---
    _fix_segments(segments)
    audio_results = []

    for i, seg in enumerate(segments, start=1):
        narration = seg["narration"]
        seg_id = seg.get("id", i)
        audio_path = AUDIO_DIR / f"{task_id}_seg_{i:02d}.wav"

        # 复用已存在的 wav（调试重跑）
        if audio_path.exists() and audio_path.stat().st_size > 1024:
            duration = get_wav_duration(audio_path)
            print(f"  [{i}/{len(segments)}] REUSE {audio_path.name}  "
                  f"{duration:.2f}s  「{narration[:25]}...」")
        else:
            print(f"  [{i}/{len(segments)}] TTS: 「{narration[:30]}...」")
            try:
                _, duration = generate_tts_segment(
                    text=narration,
                    output_path=audio_path,
                )
                print(f"         → {audio_path.name}  {duration:.2f}s")
            except Exception as e:
                print(f"         ✗ TTS 失败: {e}")
                # 用估算时长作为 fallback: 中文 ~5.5 字/秒
                duration = max(2.0, len(narration) / 5.5)
                print(f"         → 使用估算时长: {duration:.2f}s")
                # 创建静音 wav 作为占位
                _create_silence_wav(audio_path, duration)

        audio_results.append({
            "segment_id": seg_id,
            "segment_index": i,
            "narration": narration,
            "audio_path": str(audio_path),
            "audio_duration_seconds": duration,
        })

    total = sum(r["audio_duration_seconds"] for r in audio_results)
    print(f"\n  音频总时长: {total:.2f}s ({len(audio_results)} 段)")

    return audio_results


def _create_silence_wav(path: Path, duration: float) -> None:
    """创建一个指定时长的静音 WAV 文件（TTS 失败时的 fallback）。"""
    framerate = 24000
    n_frames = int(framerate * duration)
    with contextlib.closing(wave.open(str(path), "wb")) as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * n_frames)


# ============================================================
# 步骤 3: 回填时序 — 用实际音频时长计算 start_time / duration
# ============================================================

def compute_timing(storyboard: dict, audio_results: list[dict]) -> list[dict]:
    """Step 3: 用实际音频时长计算每段的 start_time 和 duration。

    在每段音频前后各加 0.5s 缓冲（留白），让画面切换不那么急促。

    Returns
    -------
    带时序信息的 segment 列表（每个 dict 包含原 storyboard 字段 + timing 字段）
    """
    print()
    print("=" * 60)
    print("[Step 3/5] 回填时序 — 音频时长驱动动画时长")
    print("=" * 60)

    PRE_BUFFER = 0.5   # 每段前面的留白
    POST_BUFFER = 0.5  # 每段后面的留白

    segments = storyboard["segments"]
    timed_segments = []
    current_time = 0.0

    for i, (seg, audio) in enumerate(zip(segments, audio_results)):
        audio_dur = audio["audio_duration_seconds"]
        # 总段时长 = 留白 + 音频 + 留白
        segment_duration = PRE_BUFFER + audio_dur + POST_BUFFER

        timed_seg = dict(seg)  # 复制原 segment
        timed_seg["start_time"] = round(current_time, 3)
        timed_seg["duration"] = round(segment_duration, 3)
        timed_seg["audio_duration"] = round(audio_dur, 3)
        timed_seg["pre_buffer"] = PRE_BUFFER
        timed_seg["post_buffer"] = POST_BUFFER

        timed_segments.append(timed_seg)
        current_time += segment_duration

        print(f"  seg {i+1}: start={timed_seg['start_time']:6.2f}s  "
              f"dur={segment_duration:5.2f}s  (audio={audio_dur:5.2f}s + buffer)  "
              f"template={seg.get('template','?'):<16s}")

    total = current_time
    print(f"\n  总视频时长: {total:.2f}s")

    # 保存带时序的 storyboard
    timed_sb = dict(storyboard)
    timed_sb["segments"] = timed_segments
    timed_sb["actual_total_seconds"] = round(total, 3)

    sb_path = OUTPUT_DIR / "storyboard_timed.json"
    sb_path.write_text(json.dumps(timed_sb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ 带时序分镜已保存: {sb_path.name}")

    return timed_segments


# ============================================================
# 步骤 4: Manim 渲染 — 每段动画时长 = 音频时长
# ============================================================

def render_manim_segment(
    template: str,
    params: dict,
    target_duration: float,
    output_name: str,
    task_id: str,
) -> Path:
    """渲染单个 Manim 模板段。

    关键：params['duration'] = target_duration（来自音频实际时长 + buffer），
    模板内部会用 self.wait() 补齐到该时长。
    """
    # 确保 duration 参数等于音频时长 + buffer
    params = dict(params)
    params["duration"] = max(2.0, target_duration)

    manim_python = str(MANIM_VENV)
    project_root = str(BASE_DIR)

    # 构建 Manim 命令
    cmd = [
        manim_python, "-m", "manim",
        "-qm",  # 720p30
        "--disable_caching",
        "--media_dir", str(VIDEO_DIR),
        "-o", output_name,
    ]

    # 模板脚本路径
    # v2 模板在 templates/ 目录
    template_py = BASE_DIR / "templates" / f"{template}.py"
    # legacy 模板在 manim_scenes/ 目录
    legacy_py = BASE_DIR / "manim_scenes" / f"{template}.py"

    if template_py.exists():
        script_path = template_py
        # v2 模板 Scene 类名：驼峰命名
        scene_name = "".join(p.capitalize() for p in template.split("_")) + "Scene"
        is_v2 = True
    elif legacy_py.exists():
        script_path = legacy_py
        # legacy 模板的 Scene 类名
        legacy_names = {
            "gradient_descent": "GradientDescentScene",
            "intro": "IntroScene",
            "outro": "OutroScene",
        }
        scene_name = legacy_names.get(template, "".join(p.capitalize() for p in template.split("_")) + "Scene")
        is_v2 = False
    else:
        raise FileNotFoundError(f"找不到模板: {template} (尝试了 {template_py} 和 {legacy_py})")

    cmd += [str(script_path), scene_name]

    # 环境变量
    env = os.environ.copy()

    # MiKTeX
    miktex_bin = os.getenv("MIKTEX_BIN")
    miktex_path = Path(miktex_bin) if miktex_bin else Path(os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64"
    ))
    if miktex_path.exists():
        existing_path = env.get("PATH", "")
        if str(miktex_path) not in existing_path:
            env["PATH"] = f"{miktex_path};{existing_path}"

    # PYTHONPATH
    if project_root not in env.get("PYTHONPATH", "").split(os.pathsep):
        env["PYTHONPATH"] = (
            f"{project_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
            if env.get("PYTHONPATH") else project_root
        )

    # 注入参数
    if is_v2:
        # v2 模板用 MANIM_PARAM_<UPPER_KEY>
        for key, value in params.items():
            if value is not None:
                env[f"MANIM_PARAM_{key.upper()}"] = str(value)
    else:
        # legacy 模板用各自的环境变量
        legacy_env_map = {
            "gradient_descent": {
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
            "intro": {
                "title": "MANIM_INTRO_TITLE",
                "subtitle": "MANIM_INTRO_SUBTITLE",
                "duration": "MANIM_INTRO_DURATION",
            },
            "outro": {
                "title": "MANIM_OUTRO_TITLE",
                "duration": "MANIM_OUTRO_DURATION",
            },
        }
        env_map = legacy_env_map.get(template, {})
        for key, value in params.items():
            if value is not None and key in env_map:
                env[env_map[key]] = str(value)

    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
        cwd=str(BASE_DIR),
    )

    if result.returncode != 0:
        stderr_tail = "\n".join((result.stderr or "").splitlines()[-20:])
        stdout_tail = "\n".join((result.stdout or "").splitlines()[-10:])
        raise RuntimeError(
            f"Manim 渲染失败 (template={template}, scene={scene_name})\n"
            f"STDERR:\n{stderr_tail}\nSTDOUT:\n{stdout_tail}"
        )

    # 查找输出视频
    for vf in VIDEO_DIR.rglob(f"{output_name}.mp4"):
        return vf
    # fallback: 模糊搜索
    matches = list(VIDEO_DIR.rglob(f"*{output_name}*.mp4"))
    if matches:
        return matches[0]

    raise RuntimeError(f"找不到 Manim 渲染产物: {output_name}.mp4")


def _patch_custom_code_duration(code: str, target_duration: float) -> str:
    """给 LLM 生成的自定义 Manim 代码注入时长控制。

    策略：找到 construct() 方法体的最后位置，在末尾追加 self.wait()。
    关键：必须在方法体的最外层缩进位置插入，不能插入到循环/条件内部。
    """
    import re

    # 移除代码中 LLM 自己加的末尾 self.wait()
    code = re.sub(
        r'\n\s+self\.wait\(\s*[\d.]+\s*\)\s*$',
        '',
        code.rstrip(),
        flags=re.MULTILINE,
    )

    # 统计 LLM 代码中的动画时长
    play_count = len(re.findall(r'self\.play\(', code))
    explicit_run_times = re.findall(r'run_time\s*=\s*([\d.]+)', code)
    explicit_total = sum(float(t) for t in explicit_run_times)
    implicit_count = play_count - len(explicit_run_times)
    estimated_anim_time = explicit_total + implicit_count * 1.0

    wait_time = max(2.0, target_duration - estimated_anim_time)

    # 找 construct 方法体的结束位置
    # 策略：找到 "def construct(self):" 行，然后找到方法体最后一行
    # 方法体结束 = 缩进级别回到 construct 定义之前的级别（或文件末尾）
    lines = code.split('\n')
    construct_start = -1
    construct_indent = 0

    for i, line in enumerate(lines):
        if 'def construct' in line and 'self' in line:
            construct_start = i
            construct_indent = len(line) - len(line.lstrip())
            break

    if construct_start < 0:
        # 找不到 construct，直接在文件末尾追加
        code += f'\n    self.wait({wait_time:.1f})  # 撑满音频时长\n'
        return code

    # 方法体缩进 = def 行缩进 + 4 空格
    body_indent_level = construct_indent + 4

    # 从 construct 行往下找，找到方法体最后一行
    # 方法体结束条件：遇到一个非空行，其缩进 <= construct_indent（回到了类级别）
    # 或者到达文件末尾
    last_body_line = construct_start
    for i in range(construct_start + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            # 空行跳过（可能是方法体内的空行）
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= construct_indent:
            # 回到了类级别或更高，方法体结束
            break
        last_body_line = i

    # 在方法体最后一行之后插入 self.wait()
    body_indent = " " * body_indent_level
    wait_line = f'{body_indent}self.wait({wait_time:.1f})  # 撑满音频时长'
    lines.insert(last_body_line + 1, wait_line)

    return '\n'.join(lines)


def render_custom_manim_code(
    manim_code: str,
    target_duration: float,
    output_name: str,
    task_id: str,
) -> Path:
    """渲染 LLM 生成的自定义 Manim 代码。

    流程：
    1. 把代码写入临时 .py 文件
    2. 用 Manim venv 执行渲染
    3. 返回渲染产物路径
    """
    params = {"duration": max(2.0, target_duration)}

    # 写入临时文件
    temp_py = TEMP_DIR / f"{output_name}_custom.py"
    temp_py.parent.mkdir(parents=True, exist_ok=True)

    # 注入时长控制：确保 Manim 场景不会比音频短
    patched_code = _patch_custom_code_duration(manim_code, target_duration)
    # 自动修复已知的颜色名问题
    patched_code = patched_code.replace('DARK_GREEN', 'GREEN_E')
    patched_code = patched_code.replace('DARK_RED', 'RED_E')

    # 清理 LLM 从 JSON 中混入的尾部大括号
    patched_code = patched_code.rstrip()
    while patched_code.endswith('}') and not patched_code.rstrip().endswith(']}'):
        # 检查这是否是 Python 代码的合法结尾（字典/集合）
        # 简单策略：如果 } 单独一行或只有缩进，就删掉
        lines = patched_code.rstrip().split('\n')
        last_line = lines[-1].strip()
        if last_line == '}':
            patched_code = '\n'.join(lines[:-1]).rstrip()
        else:
            break

    # 自动修复 MathTex 中的中文（LaTeX 不支持中文，会导致编译失败）
    import re as _re
    def _fix_mathtex_chinese(match):
        """把 MathTex 中的中文替换为占位符，中文移到旁边用 Text 显示。"""
        content = match.group(1)
        if not _re.search(r'[\u4e00-\u9fff]', content):
            return match.group(0)  # 没有中文，不修改
        # 移除中文部分，只保留 LaTeX 公式
        cleaned = _re.sub(r'\\text\{[^}]*[\u4e00-\u9fff][^}]*\}', '', content)
        cleaned = _re.sub(r'[\u4e00-\u9fff]+', '', cleaned).strip()
        if not cleaned or len(cleaned) < 3:
            cleaned = r'\rightarrow'  # 太短了就用箭头占位
        return f'MathTex(r"{cleaned}"'
    patched_code = _re.sub(
        r'MathTex\(r"(.*?)"',
        _fix_mathtex_chinese,
        patched_code,
    )
    temp_py.write_text(patched_code, encoding="utf-8")

    manim_python = str(MANIM_VENV)
    project_root = str(BASE_DIR)

    # Scene 类名约定：LLM 生成的代码必须用 CustomScene
    scene_name = "CustomScene"

    cmd = [
        manim_python, "-m", "manim",
        "-qm",  # 720p30
        "--disable_caching",
        "--media_dir", str(VIDEO_DIR),
        "-o", output_name,
        str(temp_py),
        scene_name,
    ]

    env = os.environ.copy()

    # MiKTeX
    miktex_bin = os.getenv("MIKTEX_BIN")
    miktex_path = Path(miktex_bin) if miktex_bin else Path(os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64"
    ))
    if miktex_path.exists():
        existing_path = env.get("PATH", "")
        if str(miktex_path) not in existing_path:
            env["PATH"] = f"{miktex_path};{existing_path}"

    # PYTHONPATH
    if project_root not in env.get("PYTHONPATH", "").split(os.pathsep):
        env["PYTHONPATH"] = (
            f"{project_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
            if env.get("PYTHONPATH") else project_root
        )

    # 注入参数
    for key, value in params.items():
        if value is not None:
            env[f"MANIM_PARAM_{key.upper()}"] = str(value)

    # 执行渲染
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=120, env=env, cwd=project_root,
    )

    if result.returncode != 0:
        stderr_tail = result.stderr[-500:] if result.stderr else ""
        raise RuntimeError(f"自定义 Manim 代码渲染失败:\n{stderr_tail}")

    # 查找产物
    video_sub = VIDEO_DIR / "videos"
    for candidate in video_sub.rglob(f"{output_name}.mp4"):
        return candidate

    # 兜底查找
    for candidate in VIDEO_DIR.rglob(f"{output_name}.mp4"):
        return candidate

    raise RuntimeError(f"找不到自定义 Manim 渲染产物: {output_name}.mp4")


def render_all_segments(timed_segments: list[dict], task_id: str) -> list[dict]:
    """Step 4: 渲染所有 segment 的 Manim 动画。"""
    print()
    print("=" * 60)
    print("[Step 4/5] Manim 渲染 — 动画时长 = 音频时长")
    print("=" * 60)

    rendered = []

    for i, seg in enumerate(timed_segments, start=1):
        template = seg.get("template", "bullet_summary")
        manim_code = seg.get("manim_code", "")
        target_dur = seg["duration"]  # 含 buffer 的总时长
        params = dict(seg.get("params", {}))
        # 不要让 storyboard 原始的 duration 覆盖我们的计算值
        # (params 里的 duration 只是 LLM 的参考值)

        is_custom = bool(manim_code and manim_code.strip())
        render_type = "自定义代码" if is_custom else template
        output_name = f"{task_id}_seg_{i:02d}_{template if not is_custom else 'custom'}"

        print(f"\n  [{i}/{len(timed_segments)}] 渲染: {render_type}")
        print(f"           target_duration = {target_dur:.2f}s")

        if is_custom:
            # ---- 自定义 Manim 代码模式 ----
            print(f"           mode = custom_manim_code ({len(manim_code)} chars)")
            try:
                video_path = render_custom_manim_code(
                    manim_code=manim_code,
                    target_duration=target_dur,
                    output_name=output_name,
                    task_id=task_id,
                )
                file_size = video_path.stat().st_size / 1024
                print(f"           → {video_path.name}  ({file_size:.0f} KB)")

                rendered.append({
                    "segment_index": i,
                    "video_path": str(video_path),
                    "target_duration": target_dur,
                    "template": "custom",
                    "is_custom": True,
                })
            except Exception as e:
                print(f"           ✗ 自定义代码渲染失败: {e}")
                print(f"           → 降级为 bullet_summary 模板")
                # 降级：用 bullet_summary 模板兜底
                fallback_params = {"title": seg.get("title", ""), "duration": target_dur}
                for pi in range(1, 6):
                    k = f"point_{pi}"
                    if k in seg.get("params", {}):
                        fallback_params[k] = seg["params"][k]
                try:
                    video_path = render_manim_segment(
                        template="bullet_summary",
                        params=fallback_params,
                        target_duration=target_dur,
                        output_name=output_name,
                        task_id=task_id,
                    )
                    rendered.append({
                        "segment_index": i,
                        "video_path": str(video_path),
                        "target_duration": target_dur,
                        "template": "bullet_summary",
                        "is_fallback": True,
                    })
                except Exception as e2:
                    fallback_path = _create_black_video(target_dur, output_name, task_id)
                    if fallback_path:
                        rendered.append({
                            "segment_index": i,
                            "video_path": str(fallback_path),
                            "target_duration": target_dur,
                            "template": "black",
                            "is_fallback": True,
                        })
                        print(f"           → 使用纯黑 fallback: {fallback_path.name}")
        else:
            # ---- 模板模式（原有逻辑）----
            # 打印关键参数
            for k, v in params.items():
                if k != "duration":
                    print(f"           {k} = {v}")

            try:
                video_path = render_manim_segment(
                    template=template,
                    params=params,
                    target_duration=target_dur,
                    output_name=output_name,
                    task_id=task_id,
                )
                file_size = video_path.stat().st_size / 1024
                print(f"           → {video_path.name}  ({file_size:.0f} KB)")

                rendered.append({
                    "segment_index": i,
                    "video_path": str(video_path),
                    "target_duration": target_dur,
                    "template": template,
                })
            except Exception as e:
                print(f"           ✗ 渲染失败: {e}")
                # 生成纯黑视频作为 fallback
                fallback_path = _create_black_video(target_dur, output_name, task_id)
                if fallback_path:
                    rendered.append({
                        "segment_index": i,
                        "video_path": str(fallback_path),
                        "target_duration": target_dur,
                        "template": template,
                        "is_fallback": True,
                    })
                    print(f"           → 使用纯黑 fallback: {fallback_path.name}")

    return rendered


def _create_black_video(duration: float, output_name: str, task_id: str) -> Path | None:
    """用 FFmpeg 创建一个纯黑视频作为 fallback。"""
    out = VIDEO_DIR / f"{output_name}.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1280x720:d={duration:.2f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        return out if out.exists() else None
    except Exception:
        return None


# ============================================================
# 步骤 5: 合成最终视频
# ============================================================

def concat_wav(paths: list[Path], out_path: Path, gap_seconds: float = 0.5) -> float:
    """拼接多个 WAV 文件，每段之间插入静音间隔。

    Returns: 总时长（秒）
    """
    if not paths:
        raise ValueError("没有音频文件可拼接")

    with contextlib.closing(wave.open(str(paths[0]), "rb")) as first:
        params = first.getparams()
        framerate = first.getframerate()
        sampwidth = first.getsampwidth()
        nchannels = first.getnchannels()

    gap_frames = int(framerate * gap_seconds)
    silence = b"\x00" * (gap_frames * sampwidth * nchannels)

    total_frames = 0
    with contextlib.closing(wave.open(str(out_path), "wb")) as out:
        out.setnchannels(nchannels)
        out.setsampwidth(sampwidth)
        out.setframerate(framerate)

        for i, p in enumerate(paths):
            with contextlib.closing(wave.open(str(p), "rb")) as w:
                frames = w.readframes(w.getnframes())
                out.writeframes(frames)
                total_frames += w.getnframes()

            # 段间静音（最后一段后面不加）
            if i < len(paths) - 1:
                out.writeframes(silence)
                total_frames += gap_frames

    return total_frames / float(framerate)


def concat_videos(video_paths: list[Path], out_path: Path) -> None:
    """用 FFmpeg concat demuxer 拼接多个视频，每段之间加 0.3s 黑屏过渡。"""
    # 先为每段视频加一个短黑屏尾帧
    enhanced_paths = []
    for i, vp in enumerate(video_paths):
        # 在每段视频末尾加 0.3s 黑屏
        black_tail = TEMP_DIR / f"seg_{i:02d}_with_black.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(vp),
            "-f", "lavfi", "-t", "0.3", "-i", "color=c=black:s=1280x720:r=30",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
            "-map", "[outv]",
            "-an",
            str(black_tail),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            enhanced_paths.append(black_tail)
        else:
            enhanced_paths.append(vp)  # fallback

    list_file = TEMP_DIR / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for vp in enhanced_paths:
            safe_path = str(vp).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"视频拼接失败:\n{result.stderr[-500:]}")


def _split_subtitle(text: str, max_chars: int = 18) -> list[str]:
    """将长字幕拆成多条短字幕，每条不超过 max_chars 字。
    
    优先在标点处断开，绝不在标点前断开（避免"，"出现在行首）。
    """
    if len(text) <= max_chars:
        return [text]
    
    # 标点符号集合（不能出现在行首的）
    punct = set("，。、；！？,.：）】》")
    # 断点标点（可以在此处断开）
    break_punct = "，。、；！？,.： "
    
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        # 在 max_chars 范围内找最后一个断点标点
        cut = -1
        search_end = min(max_chars, len(remaining))
        search_start = max(0, max_chars // 3)
        for i in range(search_end - 1, search_start - 1, -1):
            if remaining[i] in break_punct:
                cut = i + 1  # 标点留在前半段
                break
        if cut <= 0:
            # 没找到标点，在 max_chars 处硬切，但确保下一行不以标点开头
            cut = max_chars
            # 如果切完后下一行以标点开头，把标点移到前一行
            while cut < len(remaining) and remaining[cut] in punct:
                cut += 1
        chunk = remaining[:cut].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].lstrip()
    return chunks


def generate_srt(timed_segments: list[dict], audio_results: list[dict], srt_path: Path) -> None:
    """生成 SRT 字幕文件，时间轴与音频精确同步。
    
    改进：长旁白拆成多条短字幕（每条≤15字），按时间均匀分配。
    """
    lines = []
    cue_index = 1

    def fmt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    for seg, audio in zip(timed_segments, audio_results):
        start_s = seg["start_time"] + seg["pre_buffer"]
        end_s = start_s + audio["audio_duration_seconds"]
        total_dur = end_s - start_s

        # 字幕用完整旁白文字
        narration = seg.get("narration", seg.get("subtitle", ""))
        
        # 拆成短字幕（每条≤18字，确保单行显示）
        chunks = _split_subtitle(narration, max_chars=18)
        n = len(chunks)
        
        # 按字数比例分配时间
        total_chars = sum(len(c) for c in chunks)
        t = start_s
        for i, chunk in enumerate(chunks):
            # 按字数比例分配时长
            ratio = len(chunk) / total_chars if total_chars > 0 else 1.0 / n
            chunk_dur = total_dur * ratio
            chunk_end = min(t + chunk_dur, end_s)
            
            lines.append(f"{cue_index}")
            lines.append(f"{fmt(t)} --> {fmt(chunk_end)}")
            lines.append(chunk)
            lines.append("")
            cue_index += 1
            t = chunk_end

    srt_path.write_text("\n".join(lines), encoding="utf-8")


def compose_final_video(
    timed_segments: list[dict],
    audio_results: list[dict],
    rendered_videos: list[dict],
    task_id: str,
    topic: str = "西瓜书",
) -> Path:
    """Step 5: 合成最终视频。

    流程：
    1. 拼接所有视频段
    2. 拼接所有音频（带间隔）
    3. 合并视频 + 音频
    4. 烧录字幕
    """
    print()
    print("=" * 60)
    print("[Step 5/5] 合成最终视频")
    print("=" * 60)

    # 1. 拼接视频
    print("  → 拼接视频段 ...")
    video_paths = [Path(v["video_path"]) for v in rendered_videos]
    concat_video_path = TEMP_DIR / f"{task_id}_concat.mp4"
    concat_videos(video_paths, concat_video_path)
    print(f"    ✓ 视频拼接完成: {concat_video_path.name}")

    # 2. 拼接音频（含 buffer 间隔）
    print("  → 拼接音频 ...")
    audio_paths = [Path(a["audio_path"]) for a in audio_results]
    merged_audio = AUDIO_DIR / f"{task_id}_merged.wav"
    audio_dur = concat_wav(audio_paths, merged_audio, gap_seconds=1.0)  # 1s = pre_buffer + post_buffer
    print(f"    ✓ 音频拼接完成: {merged_audio.name}  ({audio_dur:.2f}s)")

    # 3. 生成字幕
    print("  → 生成字幕 ...")
    srt_path = SUBTITLE_DIR / f"{task_id}.srt"
    generate_srt(timed_segments, audio_results, srt_path)
    print(f"    ✓ 字幕已生成: {srt_path.name}")

    # 4. 合并视频 + 音频
    print("  → 合并视频 + 音频 ...")
    merged_path = TEMP_DIR / f"{task_id}_with_audio.mp4"
    cmd_merge = [
        "ffmpeg", "-y",
        "-i", str(concat_video_path),
        "-i", str(merged_audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(merged_path),
    ]
    result = subprocess.run(cmd_merge, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"音频合并失败:\n{result.stderr[-500:]}")
    print(f"    ✓ 合并完成: {merged_path.name}")

    # 5. 烧录字幕
    print("  → 烧录字幕 ...")
    final_name = f"{task_id}_final.mp4"
    final_path = OUTPUT_DIR / final_name

    # 字幕样式：白色，最底部，半透明黑底
    # MarginV=15 让字幕紧贴底部（类似"纯音乐，请欣赏"的位置）
    subtitle_style = (
        "FontName=Microsoft YaHei,"
        "FontSize=20,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H80000000,"
        "BorderStyle=3,"
        "Outline=2,"
        "Shadow=1,"
        "MarginV=15,"
        "Alignment=2"
    )
    # Windows 路径需要转义冒号
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

    cmd_sub = [
        "ffmpeg", "-y",
        "-i", str(merged_path),
        "-vf", f"subtitles='{srt_escaped}':force_style='{subtitle_style}'",
        "-c:v", "libx264", "-crf", "23",
        "-c:a", "copy",
        str(final_path),
    ]
    result = subprocess.run(cmd_sub, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        # 字幕烧录失败，退回到无字幕版本
        print(f"    ⚠ 字幕烧录失败，使用无字幕版本")
        print(f"      stderr: {result.stderr[-300:]}")
        shutil.copy2(merged_path, final_path)
    else:
        print(f"    ✓ 字幕烧录完成")

    file_size = final_path.stat().st_size / 1024 / 1024
    print(f"\n  最终视频: {final_path.name}  ({file_size:.1f} MB)")

    # 复制到桌面（用主题命名）
    safe_topic = topic.replace(" ", "_").replace("/", "_")[:20]
    desktop_path = DESKTOP / f"西瓜书_{safe_topic}.mp4"
    shutil.copy2(final_path, desktop_path)
    print(f"  已复制到桌面: {desktop_path.name}")

    return final_path


# ============================================================
# 主流程
# ============================================================

def main():
    import sys as _sys
    topic = _sys.argv[1] if len(_sys.argv) > 1 else "什么是机器学习"
    task_id = f"a1_{int(time.time())}"

    # 加载 .env
    load_dotenv(BASE_DIR / ".env")

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("错误: 未设置 DEEPSEEK_API_KEY，请在 .env 文件中配置")
        sys.exit(1)

    print("╔══════════════════════════════════════════════════════════╗")
    print("║     方案1: 精细分镜 (Detailed Storyboard)               ║")
    print("║     核心改进: 音频先行，动画跟随音频时长                  ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  主题: {topic}")
    print(f"  任务 ID: {task_id}")
    print()

    start_time = time.time()

    # ---- Step 1: 生成分镜 ----
    try:
        storyboard = generate_storyboard(topic, api_key, task_id)
    except Exception as e:
        print(f"\n✗ Step 1 失败: {e}")
        sys.exit(1)

    # ---- Step 2: TTS 先行 ----
    try:
        audio_results = generate_all_tts(storyboard, task_id)
    except Exception as e:
        print(f"\n✗ Step 2 失败: {e}")
        sys.exit(1)

    # ---- Step 3: 回填时序 ----
    try:
        timed_segments = compute_timing(storyboard, audio_results)
    except Exception as e:
        print(f"\n✗ Step 3 失败: {e}")
        sys.exit(1)

    # ---- Step 4: Manim 渲染 ----
    try:
        rendered_videos = render_all_segments(timed_segments, task_id)
    except Exception as e:
        print(f"\n✗ Step 4 失败: {e}")
        sys.exit(1)

    if not rendered_videos:
        print("\n✗ 没有成功渲染任何视频段")
        sys.exit(1)

    # ---- Step 5: 合成 ----
    try:
        final_path = compose_final_video(
            timed_segments, audio_results, rendered_videos, task_id, topic
        )
    except Exception as e:
        print(f"\n✗ Step 5 失败: {e}")
        sys.exit(1)

    # ---- Step 6: 自检 ----
    try:
        from video_self_check import quick_check
        print()
        print("=" * 60)
        print("[Step 6/6] 视频自检 — 检测文字重叠/越界/字幕遮挡")
        print("=" * 60)
        check_passed = quick_check(final_path)
    except Exception as e:
        print(f"  ⚠ 自检跳过: {e}")
        check_passed = True  # 自检失败不影响流程

    elapsed = time.time() - start_time

    # ---- 汇总报告 ----
    print()
    print("═" * 60)
    print("  方案1 执行完成!")
    print("═" * 60)
    print(f"  总耗时: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"  分镜数: {len(storyboard['segments'])}")
    print(f"  音频总时长: {sum(a['audio_duration_seconds'] for a in audio_results):.1f}s")
    print(f"  视频总时长: {sum(s['duration'] for s in timed_segments):.1f}s")
    print(f"  最终产物: {final_path}")
    print()

    # 打印时序明细
    print("  分镜时序明细:")
    print(f"  {'#':>2}  {'template':<16s}  {'start':>7s}  {'dur':>6s}  {'audio':>6s}  narration")
    print(f"  {'─'*2}  {'─'*16}  {'─'*7}  {'─'*6}  {'─'*6}  {'─'*20}")
    for seg, audio in zip(timed_segments, audio_results):
        narr = seg["narration"][:30] + ("..." if len(seg["narration"]) > 30 else "")
        print(f"  {seg.get('id', '?'):>2}  {seg.get('template','?'):<16s}  "
              f"{seg['start_time']:>6.2f}s  {seg['duration']:>5.2f}s  "
              f"{audio['audio_duration_seconds']:>5.2f}s  {narr}")

    print()


if __name__ == "__main__":
    main()
