# -*- coding: utf-8 -*-
"""
方案3 v2: LLM 生成完整 Manim 教学脚本（音画同步版）
核心改进：先生成 TTS 音频 → 测量每段时长 → LLM 按实际时长写动画代码
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import wave
import contextlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MANIM_VENV = BASE_DIR / ".venv_manim" / "Scripts" / "python.exe"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMP_DIR = BASE_DIR / "temp"

TEMP_DIR.mkdir(exist_ok=True)
(OUTPUT_DIR / "video").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "audio").mkdir(parents=True, exist_ok=True)


# ============================================================
# 工具函数
# ============================================================

def load_env():
    """加载 .env 文件"""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def call_deepseek(messages: list, max_tokens=8000) -> str:
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
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as resp:
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


def find_scene_class(code: str) -> str:
    """从代码中提取 Scene 子类名"""
    m = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", code)
    return m.group(1) if m else "TeachingScene"


def generate_tts(text: str, output_path: Path) -> float:
    """生成 TTS 音频，返回时长（秒）。支持 edge 和 gpt-sovits 两种引擎。失败时重试一次。"""
    provider = os.getenv("TTS_PROVIDER", "edge").lower()

    for attempt in range(2):
        try:
            if provider == "gpt-sovits":
                _tts_gpt_sovits(text, output_path)
            else:
                _tts_edge(text, output_path)

            duration = get_wav_duration(output_path)
            if duration < 0.5:
                raise RuntimeError(f"音频太短: {duration:.2f}s")
            return duration
        except Exception as e:
            if attempt == 0:
                print(f"      TTS 重试... ({e})")
                time.sleep(1)
            else:
                raise


def get_wav_duration(path: Path) -> float:
    """获取 WAV 文件时长（秒）。"""
    with contextlib.closing(wave.open(str(path), "rb")) as w:
        return w.getnframes() / w.getframerate()


def _tts_edge(text: str, output_path: Path) -> None:
    """Edge TTS 生成音频。"""
    import subprocess
    voice = os.getenv("EDGE_TTS_VOICE", "zh-CN-YunxiNeural")
    rate = os.getenv("EDGE_TTS_RATE", "+10%")
    mp3_path = output_path.with_suffix(".mp3")
    cmd = [sys.executable, "-m", "edge_tts",
           "--voice", voice, "--rate", rate,
           "--text", text, "--write-media", str(mp3_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Edge TTS 失败: {result.stderr[:200]}")
    subprocess.run(["ffmpeg", "-y", "-i", str(mp3_path),
                     "-ar", "22050", "-ac", "1", str(output_path)],
                    capture_output=True, timeout=30)
    mp3_path.unlink(missing_ok=True)


def _tts_gpt_sovits(text: str, output_path: Path) -> None:
    """GPT-SoVITS 本地推理。"""
    base_url = os.getenv("GPT_SOVITS_BASE_URL", "http://127.0.0.1:9880")
    params = {
        "refer_wav_path": os.getenv("GPT_SOVITS_REF_AUDIO", ""),
        "prompt_text": os.getenv("GPT_SOVITS_PROMPT_TEXT", "梯度下降是机器学习中非常核心的概念"),
        "prompt_language": os.getenv("GPT_SOVITS_PROMPT_LANG", "zh"),
        "text": text,
        "text_language": os.getenv("GPT_SOVITS_TEXT_LANG", "zh"),
    }
    url = base_url + "/?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as resp:
        output_path.write_bytes(resp.read())


def concat_wav(paths: list[Path], out_path: Path) -> float:
    """拼接多个 WAV 文件"""
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


# ============================================================
# 流程
# ============================================================

def step1_generate_script_and_narration(topic: str) -> tuple[str, list[str]]:
    """Step 1: LLM 生成 Manim 脚本 + 提取旁白文字"""
    system_prompt = r"""你是一个 Manim 动画教学视频生成专家。生成一个完整的、可执行的 Manim Python 脚本。

## 要求

1. 这是**教学视频**，不是简单动画展示
2. 画面下方显示**中文字幕**（Text 对象，to_edge(DOWN)），配合动画
3. 教学逻辑**循序渐进**：引入 → 公式 → 可视化演示 → 总结
4. **不要在代码里写 self.wait()**！用 `self.wait(WAIT_PLACEHOLDER_N)` 占位，后面会替换
5. 每段旁白对应一个 `# NARRATION[N]` 注释标记

- **MathTex 只能用于纯数学公式**，绝对不能在 MathTex 里写中文！中文用 Text()
- MathTex 示例：`MathTex(r"x_{n+1} = x_n - \alpha \nabla f(x_n)")` ✓
- 错误示例：`MathTex(r"\text{最小值}")` ✗ ← 中文不能放 MathTex 里
- 需要标注中文时用：`Text("最小值", font="Microsoft YaHei")` 然后 `.next_to()` 放在对应位置

## Manim API

```python
from manim import *
# 文本
Text("中文", font="Microsoft YaHei", font_size=28)
MathTex(r"x^2", font_size=40)
# 图形
Axes(x_range=[-3,3,1], y_range=[0,10,2], x_length=6, y_length=4, axis_config={"include_numbers":True})
axes.plot(lambda x: (x-1)**2+1, color=BLUE)
Dot(axes.c2p(x,y), color=RED)
Arrow(start, end, color=YELLOW)
Line(start, end)
# 动画
Write(mob)  Create(mob)  FadeIn(mob)  FadeOut(mob)  Transform(a,b)  Indicate(mob)
mob.animate.shift(UP)
# 布局
mob.to_edge(DOWN, buff=0.5)  mob.next_to(other, UP)  mob.move_to(ORIGIN)
VGroup(a,b).arrange(RIGHT, buff=0.5)
# 颜色
WHITE RED GREEN BLUE YELLOW ORANGE PURPLE
# 位置
UP DOWN LEFT RIGHT ORIGIN
```

## 输出格式

```python
# -*- coding: utf-8 -*-
from manim import *
config.pixel_height = 720
config.pixel_width = 1280
config.frame_rate = 30

class TeachingScene(Scene):
    def construct(self):
        # === 第1段：标题 ===
        # NARRATION[1]: 什么是梯度下降
        title = Text(...)
        self.play(Write(title))
        self.wait(WAIT_PLACEHOLDER_1)
        self.play(FadeOut(title))
        
        # === 第2段：概念引入 ===
        # NARRATION[2]: 梯度下降是...
        sub = Text(...)
        sub.to_edge(DOWN)
        self.play(Write(sub))
        self.wait(WAIT_PLACEHOLDER_2)
        # ... 动画 ...
        self.play(FadeOut(sub))
        
        # ... 以此类推 ...
```

## 关键规则

1. 每段旁白必须有 `# NARRATION[N]: 文字` 注释
2. 每段旁白的等待用 `self.wait(WAIT_PLACEHOLDER_N)` 占位
3. 字幕放在画面下方，不和动画主体重叠
4. 动画主体放在画面上方或中央
5. 总共 6-10 段旁白，每段一个核心知识点
6. **不要写具体的 wait 秒数**，用占位符

只输出 Python 代码块。"""

    user_prompt = f"""为知识点「{topic}」生成完整 Manim 教学动画脚本。

要求：
- 大学生机器学习教学
- 动画含中文字幕 + 函数曲线 + 梯度下降过程动画
- 6-10 段旁白，每段用 NARRATION[n] 标记
- wait 用 WAIT_PLACEHOLDER_n 占位
- 类名用 TeachingScene
- **绝对禁止在 MathTex 里写中文！** 中文全部用 Text()"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    print("[1/5] 调用 DeepSeek 生成 Manim 脚本...")
    response = call_deepseek(messages)
    code = extract_code(response)

    # 提取旁白段落
    narration_texts = []
    for m in re.finditer(r"#\s*NARRATION\[(\d+)\]:\s*(.+)", code):
        narration_texts.append(m.group(2).strip())

    # 如果没提取到，用旧格式
    if not narration_texts:
        for m in re.finditer(r"#\s*\[\d+\]\s*(.+)", code):
            narration_texts.append(m.group(1).strip())

    # 如果还没有，从 Text() 提取
    if not narration_texts:
        narration_texts = re.findall(r'Text\(["\'](.{8,}?)["\']', code)

    print(f"    代码 {len(code)} 字符，{len(narration_texts)} 段旁白")
    for i, t in enumerate(narration_texts, 1):
        print(f"    [{i}] {t[:40]}...")
    return code, narration_texts


def step2_generate_tts(narration_texts: list[str], task_id: str) -> list[dict]:
    """Step 2: 先生成所有 TTS 音频，测量实际时长"""
    print(f"[2/5] 生成 TTS 音频（{len(narration_texts)} 段）...")

    segments = []
    for i, text in enumerate(narration_texts, 1):
        audio_path = OUTPUT_DIR / "audio" / f"{task_id}_seg_{i:02d}.wav"
        try:
            dur = generate_tts(text, audio_path)
            segments.append({
                "index": i,
                "text": text,
                "audio_path": str(audio_path),
                "duration": round(dur, 2),
            })
            print(f"    [{i}/{len(narration_texts)}] {dur:.1f}s - {text[:35]}...")
        except Exception as e:
            print(f"    [{i}/{len(narration_texts)}] ❌ TTS 失败: {e}")
            # 用静音替代
            segments.append({
                "index": i,
                "text": text,
                "audio_path": None,
                "duration": max(3.0, len(text) * 0.2),  # 估算
            })

    total_dur = sum(s["duration"] for s in segments)
    print(f"    总音频时长: {total_dur:.1f}s")
    return segments


def step3_inject_timing(code: str, segments: list[dict]) -> str:
    """Step 3: 将实际音频时长注入 Manim 代码，替换 WAIT_PLACEHOLDER"""
    print("[3/5] 注入音频时长到 Manim 代码...")

    for seg in segments:
        i = seg["index"]
        # 动画本身大约占 1-2 秒（Write/FadeIn 等），wait 填充剩余时间
        # 给 0.8s 的缓冲，让动画有时间播完
        wait_time = max(1.5, seg["duration"] + 0.8)
        placeholder = f"WAIT_PLACEHOLDER_{i}"
        code = code.replace(placeholder, f"{wait_time:.1f}")

    # 也处理不带下标的占位符
    for i, seg in enumerate(segments):
        if "WAIT_PLACEHOLDER" in code:
            wait_time = max(1.5, seg["duration"] + 0.8)
            code = code.replace("WAIT_PLACEHOLDER", f"{wait_time:.1f}", 1)

    print(f"    已替换所有 WAIT_PLACEHOLDER")
    return code


def step4_render_manim(code: str) -> Path:
    """Step 4: 渲染 Manim 脚本"""
    scene_class = find_scene_class(code)
    print(f"[4/5] 渲染 Manim 动画 (Scene: {scene_class})...")

    temp_file = TEMP_DIR / "teaching_scene_v3.py"
    temp_file.write_text(code, encoding="utf-8")

    cmd = [
        str(MANIM_VENV), "-m", "manim",
        "-qm",
        "--media_dir", str(BASE_DIR / "media"),
        str(temp_file),
        scene_class,
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=180, cwd=str(BASE_DIR),
    )

    if result.returncode != 0:
        print(f"    stderr:\n{result.stderr[-1200:]}")
        raise RuntimeError("Manim 渲染失败")

    for vf in (BASE_DIR / "media").rglob(f"{scene_class}.mp4"):
        print(f"    渲染成功: {vf.stat().st_size / 1024:.0f}KB")
        return vf

    raise RuntimeError("找不到渲染输出的视频文件")


def step5_compose(video_path: Path, segments: list[dict], task_id: str, output_path: Path):
    """Step 5: 合成最终视频 — 用 ffmpeg 按时间轴拼接音频，然后合并"""
    print("[5/5] 合成最终视频...")

    # 拼接所有音频（包括失败的用静音填充）
    audio_paths = []
    for seg in segments:
        if seg["audio_path"] and Path(seg["audio_path"]).exists():
            audio_paths.append(Path(seg["audio_path"]))
        else:
            # 生成静音 wav
            silence_path = OUTPUT_DIR / "audio" / f"{task_id}_silence_{seg['index']}.wav"
            _generate_silence(silence_path, seg["duration"])
            audio_paths.append(silence_path)

    full_audio = OUTPUT_DIR / "audio" / f"{task_id}_full.wav"
    audio_dur = concat_wav(audio_paths, full_audio)
    print(f"    音频总时长: {audio_dur:.1f}s")

    # 获取视频时长
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True,
    )
    video_dur = float(probe.stdout.strip()) if probe.stdout.strip() else 0
    print(f"    视频总时长: {video_dur:.1f}s")

    # 合成：以较短的为准
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(full_audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"    FFmpeg 错误:\n{result.stderr[-500:]}")
        raise RuntimeError("视频合成失败")

    size_kb = output_path.stat().st_size / 1024
    print(f"    最终视频: {output_path.name} ({size_kb:.0f}KB)")


def _generate_silence(path: Path, duration: float):
    """生成指定时长的静音 WAV"""
    path.parent.mkdir(parents=True, exist_ok=True)
    framerate = 22050
    nframes = int(framerate * duration)
    with contextlib.closing(wave.open(str(path), "wb")) as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * nframes)


# ============================================================
# 主流程
# ============================================================

def main():
    load_env()

    topic = "什么是梯度下降"
    task_id = f"v3sync_{int(time.time())}"

    print("=" * 50)
    print("方案3 v2: 音画同步版")
    print(f"主题: {topic}")
    print("=" * 50)

    # Step 1: LLM 生成脚本
    code, narration_texts = step1_generate_script_and_narration(topic)

    if len(narration_texts) < 3:
        print(f"⚠️ 只提取到 {len(narration_texts)} 段旁白，可能有问题")
        print("前 500 字代码:")
        print(code[:500])

    # 保存原始代码
    (TEMP_DIR / f"{task_id}_raw.py").write_text(code, encoding="utf-8")

    # Step 2: 先生成 TTS，拿到实际时长
    segments = step2_generate_tts(narration_texts, task_id)

    # Step 3: 用实际时长替换代码中的 WAIT_PLACEHOLDER
    synced_code = step3_inject_timing(code, segments)

    # 保存同步后的代码
    (TEMP_DIR / f"{task_id}_synced.py").write_text(synced_code, encoding="utf-8")

    # Step 4: 渲染 Manim
    try:
        video_path = step4_render_manim(synced_code)
    except Exception as e:
        print(f"❌ 渲染失败: {e}")
        print("\n同步后的代码（前 2000 字）:")
        print(synced_code[:2000])
        return

    # Step 5: 合成
    output_path = OUTPUT_DIR / "video" / f"{task_id}_final.mp4"
    try:
        step5_compose(video_path, segments, task_id, output_path)
    except Exception as e:
        print(f"❌ 合成失败: {e}")
        return

    # 复制到桌面
    import shutil
    desktop_path = Path.home() / "Desktop" / "方案3_梯度下降_音画同步.mp4"
    shutil.copy2(output_path, desktop_path)

    # 打印时序报告
    print(f"\n{'=' * 50}")
    print("📋 时序报告:")
    t = 0
    for seg in segments:
        print(f"  [{seg['index']:2d}] {t:5.1f}s ~ {t+seg['duration']:5.1f}s  ({seg['duration']:4.1f}s)  {seg['text'][:30]}...")
        t += seg["duration"]
    print(f"\n✅ 完成！桌面: {desktop_path.name}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
