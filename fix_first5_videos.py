# -*- coding: utf-8 -*-
"""
fix_first5_videos.py — 批量修复前5个视频的所有布局问题
=====================================================
流程:
  1. 读取每个视频对应的 storyboard JSON
  2. 修复有问题的 segment (自定义代码/模板参数)
  3. 用 Manim 渲染修复后的 segment
  4. 用 FFmpeg 把修复的 segment 替换进原视频
  5. 输出新文件到桌面（原文件不动）
"""

import json, os, re, shutil, subprocess, sys, time, wave
from pathlib import Path

# ============================================================
# 路径
# ============================================================
BASE_DIR = Path(r"C:\Users\hymac\Desktop\临时python骨架穿透文件")
MANIM_VENV = BASE_DIR / ".venv_manim" / "Scripts" / "python.exe"
OUTPUTS = BASE_DIR / "outputs" / "approach1"
AUDIO_DIR = OUTPUTS / "audio"
VIDEO_DIR = OUTPUTS / "video"
TEMP_DIR = OUTPUTS / "temp"
SRC_VIDEO_DIR = Path(r"C:\Users\hymac\Desktop\视频未检测")
DESKTOP = Path.home() / "Desktop"
FFMPEG = "ffmpeg"

for d in (TEMP_DIR, VIDEO_DIR):
    d.mkdir(parents=True, exist_ok=True)


def get_wav_dur(path):
    try:
        with wave.open(path, 'r') as wf:
            return wf.getnframes() / wf.getframerate()
    except:
        return 0

def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                        capture_output=True, text=True)
    return float(r.stdout.strip())


# ============================================================
# 修复定义
# ============================================================

FIXES = {
    # task_id: {seg_id: {"type": "custom"/"template", ...}}
    
    # === Video 1: 什么是机器学习 (a1_1781767916) ===
    # Seg#8 custom: 奥卡姆剃刀文字太低(y=-2.5), 曲线+文字重叠
    "a1_1781767916": {
        8: {
            "type": "custom",
            "code": r'''from manim import *
import numpy as np

class CustomScene(Scene):
    def construct(self):
        title = Text("归纳偏好：选哪个规律？", font="Microsoft YaHei", font_size=34, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title))

        # 数据点 — 放在 y∈[-0.5, 1.5] 的安全区域
        dots = VGroup()
        dot_positions = [[-3, -0.5, 0], [-1, 0.5, 0], [1, 0, 0], [3, 1, 0]]
        for pos in dot_positions:
            d = Dot(point=pos, color=BLUE)
            dots.add(d)
        self.play(FadeIn(dots))

        # 多条曲线 — 只在 y∈[-1, 2] 范围内
        curves = VGroup()
        curve1 = ParametricFunction(
            lambda t: [-3 + 4*t, -0.5 + 2*t - 2*t**2 + t**3, 0],
            t_range=[0, 1], color=RED
        )
        curves.add(curve1)

        curve2 = ParametricFunction(
            lambda t: [-3 + 4*t, -0.5 + 1.5*t, 0],
            t_range=[0, 1], color=GREEN
        )
        curves.add(curve2)

        curve3 = ParametricFunction(
            lambda t: [-3 + 4*t, -0.5 + 1.5*t + 0.3*np.sin(4*np.pi*t), 0],
            t_range=[0, 1], color=ORANGE
        )
        curves.add(curve3)

        self.play(Create(curves))

        # 高亮绿色曲线
        self.play(
            curves[0].animate.set_opacity(0.3),
            curves[2].animate.set_opacity(0.3),
            curves[1].animate.set_color(YELLOW).scale(1.1)
        )

        # 奥卡姆剃刀 — 提高到 y=-1.8，远离字幕区
        occam = Text("奥卡姆剃刀：选择最简单的", font="Microsoft YaHei", font_size=22, color=YELLOW)
        occam.move_to([0, -1.8, 0])
        self.play(Write(occam))
        self.wait(1)
'''
        }
    },

    # === Video 2: 假设空间与归纳偏好 (a1_1781768120) ===
    # Seg#6 custom: 训练数据框和箭头重叠
    "a1_1781768120": {
        6: {
            "type": "custom",
            "code": r'''from manim import *

class CustomScene(Scene):
    def construct(self):
        title = Text("多个假设符合数据", font="Microsoft YaHei", font_size=34, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title))

        # 训练数据 — 放在右中区域，留足间距
        data_box = Rectangle(width=2.8, height=1.2, color=GREEN).move_to([4.5, 0, 0])
        data_label = Text("训练数据", font="Microsoft YaHei", font_size=22, color=GREEN)
        data_label.move_to(data_box.get_center())
        self.play(Create(data_box), Write(data_label))

        # 三个假设 — 左侧，间隔拉大
        h1 = Rectangle(width=3.0, height=0.9, color=YELLOW).move_to([-4.5, 2.0, 0])
        h2 = Rectangle(width=3.0, height=0.9, color=ORANGE).move_to([-4.5, 0, 0])
        h3 = Rectangle(width=3.0, height=0.9, color=PURPLE).move_to([-4.5, -2.0, 0])

        t1 = Text("颜色=深绿→好瓜", font="Microsoft YaHei", font_size=18, color=YELLOW)
        t1.move_to(h1.get_center())
        t2 = Text("根蒂=蜷缩→好瓜", font="Microsoft YaHei", font_size=18, color=ORANGE)
        t2.move_to(h2.get_center())
        t3 = Text("敲声=清脆→好瓜", font="Microsoft YaHei", font_size=18, color=PURPLE)
        t3.move_to(h3.get_center())

        self.play(Create(h1), Create(h2), Create(h3))
        self.play(Write(t1), Write(t2), Write(t3))

        # 箭头 — 从假设框右侧到数据框左侧，留间距
        arr1 = Arrow(start=h1.get_right() + RIGHT*0.1, end=data_box.get_left() + LEFT*0.1, color=YELLOW, buff=0)
        arr2 = Arrow(start=h2.get_right() + RIGHT*0.1, end=data_box.get_left() + LEFT*0.1, color=ORANGE, buff=0)
        arr3 = Arrow(start=h3.get_right() + RIGHT*0.1, end=data_box.get_left() + LEFT*0.1, color=PURPLE, buff=0)
        self.play(Create(arr1), Create(arr2), Create(arr3))

        # 问号
        qmark = Text("？", font="Microsoft YaHei", font_size=48, color=RED)
        qmark.next_to(data_box, DOWN, buff=0.5)
        self.play(Write(qmark))
        self.wait(1)
'''
        }
    },

    # === Video 3: 经验风险与过拟合 (a1_1781760566) ===
    # Seg#4 custom: 流程图中间元素密集重叠
    "a1_1781760566": {
        4: {
            "type": "custom",
            "code": r'''from manim import *

class CustomScene(Scene):
    def construct(self):
        title = Text("经验风险：训练集上的错误率", font="Microsoft YaHei", font_size=30, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title))

        # 特征输入 — 左侧
        feat_text = Text("特征", font="Microsoft YaHei", font_size=24, color=BLUE)
        feat_text.move_to([-5, 0, 0])
        self.play(Write(feat_text))

        dots = VGroup(
            Dot(point=[-5, -0.5, 0], color=BLUE),
            Dot(point=[-5, -0.8, 0], color=BLUE),
            Dot(point=[-5, -1.1, 0], color=BLUE)
        )
        self.play(FadeIn(dots))

        # 箭头1 — 特征→模型
        arrow1 = Arrow(start=[-4.2, 0, 0], end=[-2, 0, 0], color=WHITE)
        self.play(Create(arrow1))

        # 模型方框 — 正中间
        model_box = Rectangle(width=2.5, height=1.8, color=YELLOW, fill_opacity=0.2)
        model_box.move_to([0, 0, 0])
        model_label = Text("模型 f(x)", font="Microsoft YaHei", font_size=22, color=YELLOW)
        model_label.move_to(model_box.get_center())
        self.play(Create(model_box), Write(model_label))

        # 箭头2 — 模型→输出
        arrow2 = Arrow(start=[2, 0, 0], end=[3.5, 0, 0], color=WHITE)
        self.play(Create(arrow2))

        # 输出 — 右侧
        output = Text("好瓜/坏瓜", font="Microsoft YaHei", font_size=22, color=GREEN)
        output.move_to([5, 0, 0])
        self.play(Write(output))

        # 底部说明 — y=-2.0 安全区
        bottom_text = Text("经验风险 = 训练集上的错误率", font="Microsoft YaHei", font_size=24, color=ORANGE)
        bottom_text.move_to([0, -2.0, 0])
        self.play(Write(bottom_text))

        self.wait(1)
        self.play(FadeOut(VGroup(feat_text, dots, arrow1, model_box, model_label, arrow2, output, bottom_text, title)))
        self.wait(0.5)
'''
        }
    },

    # === Video 4: 交叉验证与模型选择 (a1_1781758354) ===
    # Seg#4 custom: 模型圆y=-2.5侵入字幕区 + 箭头穿越文字
    "a1_1781758354": {
        4: {
            "type": "custom",
            "code": r'''from manim import *

class CustomScene(Scene):
    def construct(self):
        title = Text("留出法：训练集 vs 测试集", font="Microsoft YaHei", font_size=34, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title))

        # 整个数据集 — 缩小，留出底部空间
        full_rect = Rectangle(width=5.5, height=2.0, color=WHITE, fill_opacity=0.1)
        full_rect.move_to([0, 1.2, 0])
        self.play(Create(full_rect))

        # 分割线
        split_line = Line(start=[0, 0.2, 0], end=[0, 2.2, 0], color=YELLOW, stroke_width=3)
        self.play(Create(split_line))

        # 训练集（左边）
        train_rect = Rectangle(width=2.75, height=2.0, color=BLUE, fill_opacity=0.3)
        train_rect.move_to([-1.375, 1.2, 0])
        train_label = Text("训练集", font="Microsoft YaHei", font_size=26, color=BLUE)
        train_label.move_to(train_rect.get_center())
        self.play(FadeIn(train_rect), Write(train_label))

        # 测试集（右边）
        test_rect = Rectangle(width=2.75, height=2.0, color=ORANGE, fill_opacity=0.3)
        test_rect.move_to([1.375, 1.2, 0])
        test_label = Text("测试集", font="Microsoft YaHei", font_size=26, color=ORANGE)
        test_label.move_to(test_rect.get_center())
        self.play(FadeIn(test_rect), Write(test_label))

        # 模型 — 提高到 y=-1.0，远离字幕区
        model = Circle(radius=0.5, color=PURPLE, fill_opacity=0.6)
        model.move_to([0, -1.0, 0])
        model_label = Text("模型", font="Microsoft YaHei", font_size=22, color=WHITE)
        model_label.move_to(model.get_center())
        model_group = VGroup(model, model_label)
        self.play(FadeIn(model_group))

        # 箭头 — 从训练集底部到模型顶部，模型底部到测试集底部
        arrow1 = Arrow(start=train_rect.get_bottom() + DOWN*0.1, end=model.get_top() + UP*0.1, color=BLUE, buff=0)
        arrow2 = Arrow(start=model.get_right() + RIGHT*0.1, end=test_rect.get_bottom() + DOWN*0.1, color=ORANGE, buff=0)
        self.play(Create(arrow1), Create(arrow2))

        self.wait(1)
'''
        }
    },

    # === Video 5: 误差与过拟合与欠拟合 (a1_1781758511) ===
    # Seg#1 intro: 标题太长, 64pt重叠 → 已修intro_v2模板字号54pt
    # 但还需要重新渲染这个intro segment
    "a1_1781758511": {
        1: {
            "type": "template",
            "template": "intro_v2",
            "params": {
                "title": "误差与过拟合与欠拟合",
                "subtitle": "机器学习·西瓜书",
                "duration": 8.0
            }
        }
    }
}


# ============================================================
# 渲染函数
# ============================================================

def render_custom_segment(code: str, output_name: str, duration: float) -> Path:
    """渲染自定义 Manim 代码 segment"""
    temp_py = TEMP_DIR / f"{output_name}.py"
    temp_py.write_text(code, encoding="utf-8")

    env = os.environ.copy()
    env["MANIM_PARAM_DURATION"] = str(duration)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    miktex = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64"))
    if miktex.exists():
        env["PATH"] = f"{miktex};{env.get('PATH','')}"
    env["PYTHONPATH"] = f"{BASE_DIR}{os.pathsep}{env.get('PYTHONPATH','')}"

    cmd = [
        str(MANIM_VENV), "-m", "manim",
        "-qm", "--disable_caching",
        "--media_dir", str(VIDEO_DIR),
        "-o", output_name,
        str(temp_py),
        "CustomScene",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env, cwd=str(BASE_DIR))
    if result.returncode != 0:
        raise RuntimeError(f"Manim render failed:\n{result.stderr[-500:]}")

    for f in VIDEO_DIR.rglob(f"{output_name}.mp4"):
        return f
    raise RuntimeError(f"Output not found: {output_name}")


def render_template_segment(template: str, params: dict, output_name: str) -> Path:
    """渲染模板 segment"""
    template_file = BASE_DIR / "templates" / f"{template}.py"

    env = os.environ.copy()
    for k, v in params.items():
        env[f"MANIM_PARAM_{k.upper()}"] = str(v)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    miktex = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64"))
    if miktex.exists():
        env["PATH"] = f"{miktex};{env.get('PATH','')}"
    env["PYTHONPATH"] = f"{BASE_DIR}{os.pathsep}{env.get('PYTHONPATH','')}"

    # 从模板文件获取 scene 类名
    template_content = template_file.read_text(encoding="utf-8")
    scene_match = re.search(r'class\s+(\w+Scene)', template_content)
    scene_name = scene_match.group(1) if scene_match else "CustomScene"

    cmd = [
        str(MANIM_VENV), "-m", "manim",
        "-qm", "--disable_caching",
        "--media_dir", str(VIDEO_DIR),
        "-o", output_name,
        str(template_file),
        scene_name,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env, cwd=str(BASE_DIR))
    if result.returncode != 0:
        raise RuntimeError(f"Template render failed:\n{result.stderr[-500:]}")

    for f in VIDEO_DIR.rglob(f"{output_name}.mp4"):
        return f
    raise RuntimeError(f"Output not found: {output_name}")


def splice_segment(original: Path, new_seg: Path, start: float, end: float, output: Path):
    """用 new_seg 替换 original 中 [start, end] 时间段"""
    tmp = TEMP_DIR
    
    # Part 1: 视频开始到 start
    part1 = tmp / "splice_p1.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(original), "-t", str(start),
                     "-c", "copy", str(part1)], capture_output=True, timeout=60)

    # Part 2: end 到视频结束
    part2 = tmp / "splice_p2.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(original), "-ss", str(end),
                     "-c", "copy", str(part2)], capture_output=True, timeout=60)

    # 调整新 segment 时长匹配原时段
    target_dur = end - start
    new_dur = probe_dur(new_seg)
    padded = tmp / "splice_new.mp4"
    
    if abs(new_dur - target_dur) > 0.3 and 0.3 < (new_dur / target_dur) < 3.0:
        speed = new_dur / target_dur
        subprocess.run([
            FFMPEG, "-y", "-i", str(new_seg),
            "-filter:v", f"setpts={1/speed}*PTS",
            "-an",  # 去音频，后面用原音频
            "-c:v", "libx264", "-crf", "23",
            str(padded)
        ], capture_output=True, timeout=120)
    else:
        shutil.copy2(new_seg, padded)

    # 用 concat 拼接（视频轨）
    concat_list = tmp / "concat.txt"
    concat_list.write_text(f"file '{part1}'\nfile '{padded}'\nfile '{part2}'\n", encoding="utf-8")
    
    video_only = tmp / "splice_video.mp4"
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(concat_list), "-c", "copy", str(video_only)],
                    capture_output=True, timeout=120)

    # 合并原音频（保持音频不变）
    subprocess.run([
        FFMPEG, "-y",
        "-i", str(video_only),
        "-i", str(original),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "copy",
        str(output)
    ], capture_output=True, timeout=120)

    # 清理临时文件
    for f in [part1, part2, padded, concat_list, video_only]:
        f.unlink(missing_ok=True)

    dur = probe_dur(output)
    size = output.stat().st_size / 1024
    print(f"    -> {output.name} ({dur:.1f}s, {size:.0f}KB)")


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  批量修复前5个视频的布局问题")
    print("=" * 60)

    # 映射: task_id → 源视频文件名
    # 先按 duration 匹配
    task_to_video = {}
    src_videos = sorted(SRC_VIDEO_DIR.glob("*.mp4"))[:5]
    
    for sv in src_videos:
        sv_dur = probe_dur(sv)
        for tid in FIXES:
            final = OUTPUTS / f"{tid}_final.mp4"
            if final.exists():
                final_dur = probe_dur(final)
                if abs(final_dur - sv_dur) < 0.5:
                    task_to_video[tid] = sv
                    break

    for tid, fixes in FIXES.items():
        src_video = task_to_video.get(tid)
        if not src_video:
            print(f"\n[SKIP] {tid}: source video not matched")
            continue

        video_name = src_video.name
        print(f"\n{'='*60}")
        print(f"  修复: {video_name}")
        print(f"  Task: {tid}")
        print(f"{'='*60}")

        # 加载 storyboard 获取 segment 时间
        sb_path = OUTPUTS / f"{tid}_storyboard.json"
        with open(sb_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        segments = data.get("segments", [])
        
        # 计算每个 segment 的时间范围
        cumulative = 0.0
        seg_timings = {}
        for seg in segments:
            sid = seg["id"]
            af = AUDIO_DIR / f"{tid}_seg_{sid:02d}.wav"
            dur = get_wav_dur(str(af))
            seg_timings[sid] = (cumulative, cumulative + dur + 0.5, dur)
            cumulative += dur + 0.5

        # 对每个有问题的 segment 渲染修复版本
        current_video = src_video  # 当前版本的视频路径
        
        for sid, fix in sorted(fixes.items()):
            start, end, audio_dur = seg_timings.get(sid, (0, 0, 0))
            if start == 0 and end == 0:
                print(f"  [SKIP] Seg#{sid}: timing not found")
                continue

            output_name = f"fix_{tid}_seg{sid:02d}"
            print(f"\n  渲染 Seg#{sid} ({fix['type']}) [{start:.1f}~{end:.1f}s]...")

            try:
                if fix["type"] == "custom":
                    new_seg = render_custom_segment(
                        fix["code"], output_name, audio_dur + 1.0
                    )
                elif fix["type"] == "template":
                    new_seg = render_template_segment(
                        fix["template"], fix["params"], output_name
                    )
                else:
                    print(f"    [SKIP] Unknown type: {fix['type']}")
                    continue

                print(f"    渲染成功: {new_seg.name}")

                # 拼接
                fixed_video = TEMP_DIR / f"{video_name.replace('.mp4','')}_fixed_seg{sid}.mp4"
                splice_segment(current_video, new_seg, start, end, fixed_video)
                
                # 更新当前视频为修复后的版本
                current_video = fixed_video

            except Exception as e:
                print(f"    [ERROR] {e}")
                continue

        # 最终输出到桌面
        out_name = video_name.replace(".mp4", "_v2.mp4")
        out_path = DESKTOP / out_name
        shutil.copy2(current_video, out_path)
        print(f"\n  ✓ 完成: {out_path.name}")

    # 清理
    print(f"\n{'='*60}")
    print("  全部修复完成！请检查桌面上的 _v2.mp4 文件")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
