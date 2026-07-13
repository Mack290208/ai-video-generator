# -*- coding: utf-8 -*-
"""
方案3: LLM 生成完整 Manim 教学脚本
一个知识点 = 一个完整的 Manim Scene，动画和讲解同步
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MANIM_VENV = BASE_DIR / ".venv_manim" / "Scripts" / "python.exe"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMP_DIR = BASE_DIR / "temp"

TEMP_DIR.mkdir(exist_ok=True)
(OUTPUT_DIR / "video").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "audio").mkdir(parents=True, exist_ok=True)


def call_deepseek(messages: list) -> str:
    """调用 DeepSeek API"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY")

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


def extract_code(text: str) -> str:
    """从 LLM 响应中提取 Python 代码"""
    m = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    if "class " in text and "def construct" in text:
        return text.strip()
    raise ValueError("无法从 LLM 响应中提取有效的 Manim 代码")


def generate_manim_script(topic: str) -> tuple[str, list[str]]:
    """
    用 LLM 生成完整的 Manim 教学脚本。
    返回 (manim_code, narration_texts) — narration_texts 是每段旁白文字，用于后续 TTS。
    """
    system_prompt = r"""你是一个 Manim 动画教学视频生成专家。你需要生成一个完整的、可执行的 Manim Python 脚本，用于教授机器学习知识点。

## 要求

1. 这是一个**教学视频**，不是简单的动画展示
2. 动画里必须包含**中文讲解文字**（字幕），显示在画面下方，让学生能跟着文字理解
3. 每个讲解段落要有**足够的等待时间**（self.wait），让学生能看完文字、理解动画
4. 动画节奏要**慢而清晰**，不要急匆匆地切换
5. 教学逻辑要**循序渐进**：引入 → 概念解释 → 可视化演示 → 总结

## Manim API 参考

```python
from manim import *

# 基础图形
Text("中文", font="Microsoft YaHei", font_size=24)
MathTex(r"x^2 + y^2 = r^2", font_size=36)
Circle(radius=1.0, color=BLUE)
Rectangle(width=4, height=2, color=GREEN)
Line(start, end, color=WHITE)
Arrow(start, end, color=WHITE)
Dot(point, color=RED)

# 布局
VGroup(*mobjects).arrange(RIGHT, buff=0.5)
mobject.next_to(other, UP, buff=0.5)
mobject.move_to(ORIGIN)
mobject.shift(UP * 2)

# 动画
Create(mobject)       # 画线创建
Write(mobject)        # 写入文字
FadeIn(mobject)       # 淡入
FadeOut(mobject)      # 淡出
Transform(m1, m2)     # 变形
Indicate(mobject)     # 闪烁提示
mobject.animate.shift(UP)  # 动画属性

# 坐标系
axes = Axes(
    x_range=[-3, 3, 1], y_range=[0, 10, 2],
    x_length=6, y_length=4,
    axis_config={"include_numbers": True},
)
axes.plot(lambda x: (x-1)**2 + 1, color=BLUE)

# 颜色
WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE

# 位置
UP, DOWN, LEFT, RIGHT, ORIGIN
```

## 代码结构

```python
# -*- coding: utf-8 -*-
from manim import *

config.pixel_height = 720
config.pixel_width = 1280
config.frame_rate = 30

class TeachingScene(Scene):
    def construct(self):
        # 1. 标题
        title = Text("标题", font="Microsoft YaHei", font_size=44)
        self.play(Write(title))
        self.wait(2)
        self.play(FadeOut(title))
        
        # 2. 讲解段落1：概念引入
        subtitle1 = Text("讲解文字1...", font="Microsoft YaHei", font_size=28)
        subtitle1.to_edge(DOWN, buff=0.5)
        self.play(Write(subtitle1))
        self.wait(3)  # 等待时间足够学生阅读
        # ... 动画 ...
        self.play(FadeOut(subtitle1))
        
        # 3. 讲解段落2：可视化
        # ... 继续 ...
        
        # 4. 总结
        # ...
```

## 关键原则

- **每个 self.wait() 至少 2 秒**，文字多的段落 wait 3-4 秒
- **字幕放在画面下方** (to_edge(DOWN, buff=0.5))
- **字幕不要和动画主体重叠**
- **每段讲解结束后 FadeOut 字幕再进入下一段**
- **动画主体放在画面上方或中央**
- **总共 60-90 秒**的教学视频

## 输出格式

只输出 Python 代码块，不要有其他文字。

在代码最后，用注释标记每段旁白文字，格式如下：
```python
# NARRATION_SEGMENTS:
# [1] 标题：什么是梯度下降
# [2] 梯度下降是机器学习中最基础的优化算法...
# [3] ...
```
"""

    user_prompt = f"""请为以下知识点生成一个完整的 Manim 教学动画脚本：

**知识点：{topic}**

要求：
1. 这是给大学生看的机器学习教学视频
2. 动画里要显示中文讲解文字（字幕），配合动画演示
3. 教学逻辑：引入概念 → 公式解释 → 动画演示梯度下降过程 → 总结
4. 节奏慢一点，每个段落给足够的阅读时间
5. 总时长 60-90 秒
6. 用坐标系展示函数曲线，用点的移动展示梯度下降过程
7. 最后要有总结要点

请生成完整的、可直接执行的 Manim Python 代码。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    print("[1/4] 调用 DeepSeek 生成 Manim 脚本...")
    response = call_deepseek(messages)
    code = extract_code(response)

    # 提取旁白段落
    narration_texts = []
    for m in re.finditer(r"#\s*\[\d+\]\s*(.+)", code):
        narration_texts.append(m.group(1).strip())

    print(f"    生成了 {len(code)} 字符的代码，{len(narration_texts)} 段旁白")
    return code, narration_texts


def find_scene_class(code: str) -> str:
    """从代码中提取 Scene 子类名"""
    m = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", code)
    if m:
        return m.group(1)
    return "TeachingScene"


def render_manim(code: str) -> Path:
    """渲染 Manim 脚本，返回视频路径"""
    scene_class = find_scene_class(code)
    print(f"[2/4] 渲染 Manim 动画 (Scene: {scene_class})...")

    temp_file = TEMP_DIR / "teaching_scene.py"
    temp_file.write_text(code, encoding="utf-8")

    cmd = [
        str(MANIM_VENV), "-m", "manim",
        "-qm",  # 720p30
        "--media_dir", str(BASE_DIR / "media"),
        str(temp_file),
        scene_class,
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=180, cwd=str(BASE_DIR),
    )

    if result.returncode != 0:
        print(f"Manim stderr:\n{result.stderr[-1000:]}")
        print(f"Manim stdout:\n{result.stdout[-500:]}")
        raise RuntimeError("Manim 渲染失败")

    # 查找输出视频
    for vf in (BASE_DIR / "media").rglob(f"{scene_class}.mp4"):
        print(f"    渲染成功: {vf} ({vf.stat().st_size / 1024:.0f}KB)")
        return vf

    raise RuntimeError("找不到渲染输出的视频文件")


def generate_tts(text: str, output_path: Path) -> float:
    """调用 GPT-SoVITS 生成音频，返回时长"""
    params = {
        "refer_wav_path": os.getenv("GPT_SOVITS_REF_AUDIO", ""),
        "prompt_text": os.getenv("GPT_SOVITS_PROMPT_TEXT", "梯度下降是机器学习中非常核心的概念"),
        "prompt_language": os.getenv("GPT_SOVITS_PROMPT_LANG", "zh"),
        "text": text,
        "text_language": os.getenv("GPT_SOVITS_TEXT_LANG", "zh"),
    }
    url = "http://127.0.0.1:9880/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=60) as resp:
        audio_data = resp.read()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_data)

    # 获取音频时长
    import wave, contextlib
    with contextlib.closing(wave.open(str(output_path), "rb")) as w:
        duration = w.getnframes() / w.getframerate()

    return duration


def concat_wav(paths: list[Path], out_path: Path) -> float:
    """拼接多个 WAV 文件"""
    import wave, contextlib

    with contextlib.closing(wave.open(str(paths[0]), "rb")) as first:
        params = first.getparams()

    total_frames = 0
    with contextlib.closing(wave.open(str(out_path), "wb")) as out:
        out.setparams(params)
        for p in paths:
            with contextlib.closing(wave.open(str(p), "rb")) as w:
                out.writeframes(w.readframes(w.getnframes()))
                total_frames += w.getnframes()

    return total_frames / params.framerate


def generate_audio_for_narrations(narration_texts: list[str], task_id: str) -> Path:
    """为每段旁白生成 TTS，拼接成一个完整音频"""
    print(f"[3/4] 生成 TTS 音频（{len(narration_texts)} 段）...")

    audio_paths = []
    for i, text in enumerate(narration_texts, 1):
        audio_path = OUTPUT_DIR / "audio" / f"{task_id}_seg_{i:02d}.wav"
        try:
            dur = generate_tts(text, audio_path)
            audio_paths.append(audio_path)
            print(f"    [{i}/{len(narration_texts)}] {dur:.1f}s - {text[:30]}...")
        except Exception as e:
            print(f"    [{i}/{len(narration_texts)}] TTS 失败: {e}")

    if not audio_paths:
        raise RuntimeError("所有 TTS 都失败了")

    # 拼接
    concat_path = OUTPUT_DIR / "audio" / f"{task_id}_full.wav"
    total_dur = concat_wav(audio_paths, concat_path)
    print(f"    音频拼接完成: {total_dur:.1f}s")
    return concat_path


def compose_final_video(video_path: Path, audio_path: Path, output_path: Path):
    """合成最终视频：视频 + TTS 音频"""
    print("[4/4] 合成最终视频...")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"FFmpeg 失败:\n{result.stderr[-500:]}")
        raise RuntimeError("视频合成失败")

    size_kb = output_path.stat().st_size / 1024
    print(f"    最终视频: {output_path} ({size_kb:.0f}KB)")


def main():
    topic = "什么是梯度下降"
    task_id = f"v3_{int(time.time())}"

    # 加载 .env
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    print(f"=" * 50)
    print(f"方案3: LLM 生成完整教学视频")
    print(f"主题: {topic}")
    print(f"=" * 50)

    # 1. LLM 生成 Manim 脚本
    code, narration_texts = generate_manim_script(topic)

    # 保存生成的代码
    code_path = TEMP_DIR / f"{task_id}_scene.py"
    code_path.write_text(code, encoding="utf-8")
    print(f"    代码已保存: {code_path}")

    if not narration_texts:
        print("    ⚠️ 没有提取到旁白段落，从代码中推断...")
        # 尝试从 Text() 中提取
        narration_texts = re.findall(r'Text\(["\'](.+?)["\']', code)
        narration_texts = [t for t in narration_texts if len(t) > 5]
        print(f"    从代码中提取到 {len(narration_texts)} 段文字")

    # 2. 渲染 Manim
    try:
        video_path = render_manim(code)
    except Exception as e:
        print(f"❌ 渲染失败: {e}")
        print("\n生成的代码有问题，打印出来供调试：")
        print(code[:2000])
        return

    # 3. 生成 TTS
    try:
        audio_path = generate_audio_for_narrations(narration_texts, task_id)
    except Exception as e:
        print(f"❌ TTS 失败: {e}")
        return

    # 4. 合成
    output_path = OUTPUT_DIR / "video" / f"{task_id}_final.mp4"
    try:
        compose_final_video(video_path, audio_path, output_path)
    except Exception as e:
        print(f"❌ 合成失败: {e}")
        return

    # 复制到桌面
    desktop_path = Path.home() / "Desktop" / "方案3_梯度下降_完整教学.mp4"
    import shutil
    shutil.copy2(output_path, desktop_path)

    print(f"\n{'=' * 50}")
    print(f"✅ 完成！视频已放到桌面: {desktop_path.name}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
