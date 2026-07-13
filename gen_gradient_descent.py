# -*- coding: utf-8 -*-
"""
直接调用 storyboard_pipeline 生成梯度下降教学视频
"""
import os, sys, json, time
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# 加载 .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

from storyboard_pipeline import run_pipeline

storyboard = {
    "video_title": "梯度下降：机器学习的核心引擎",
    "duration_target_seconds": 60,
    "segments": [
        {
            "template": "intro_v2",
            "narration": "梯度下降，机器学习最核心的优化算法。今天我们用一分钟，彻底搞懂它。",
            "params": {
                "title": "梯度下降算法",
                "subtitle": "机器学习的核心引擎",
                "duration": 5.0
            }
        },
        {
            "template": "curve_descent",
            "narration": "想象你站在一座山上，眼前是一片山谷。你的目标是找到最低点。梯度下降的策略很简单：朝着最陡峭的下坡方向，一步一步往下走。",
            "params": {
                "title": "下山的策略",
                "func_label": "损失函数",
                "rule_label": "沿负梯度方向更新",
                "start_x": 0.8,
                "lr": 0.15,
                "steps": 8,
                "duration": 15.0
            }
        },
        {
            "template": "formula_evolve",
            "narration": "数学上，我们用这个公式来描述每一步的更新。新的参数等于旧参数减去学习率乘以梯度。梯度告诉我们上升最快的方向，减去它，就是下降最快的方向。",
            "params": {
                "title": "更新规则",
                "formulas": [
                    "theta_new = theta_old - alpha * grad_L",
                    "alpha: 学习率，控制步长",
                    "grad_L: 梯度方向"
                ],
                "duration": 12.0
            }
        },
        {
            "template": "lr_comparison",
            "narration": "学习率的选择至关重要。太小了，收敛太慢；太大了，会来回震荡甚至发散。好的学习率，既能快速收敛，又不会跳过最优点。",
            "params": {
                "title": "学习率的影响",
                "lr_small": 0.01,
                "lr_good": 0.1,
                "lr_large": 0.5,
                "steps": 15,
                "duration": 12.0
            }
        },
        {
            "template": "bullet_summary",
            "narration": "总结一下。第一，梯度下降沿负梯度方向更新参数。第二，学习率控制每一步的大小。第三，选择合适的学习率是调参的关键。掌握这三点，你就掌握了深度学习的基石。",
            "params": {
                "title": "本节要点回顾",
                "point_1": "沿负梯度方向更新参数",
                "point_2": "学习率 alpha 控制步长大小",
                "point_3": "选好学习率是调参关键",
                "duration": 12.0
            }
        },
        {
            "template": "outro",
            "narration": "感谢观看！梯度下降是神经网络训练的基础，理解它，你就迈出了深度学习的第一步。",
            "params": {
                "title": "感谢观看",
                "points": ["梯度下降是神经网络训练的基础", "理解它 = 迈出深度学习第一步"],
                "duration": 4.0
            }
        }
    ]
}

print("=" * 60)
print("[Video] Gradient Descent")
print("=" * 60)
for i, seg in enumerate(storyboard["segments"], 1):
    tpl = seg["template"]
    dur = seg["params"].get("duration", "?")
    narr = seg["narration"][:40]
    print(f"  {i}. [{tpl}] ({dur}s) {narr}...")

print()
print("TTS ref_audio:", os.getenv("GPT_SOVITS_REF_AUDIO", "NOT SET")[:60])
print()

start = time.time()
result = run_pipeline(storyboard=storyboard, use_whisper=True)
elapsed = time.time() - start

print()
print(f"Pipeline time: {elapsed:.1f}s")
print(f"Result: {json.dumps(result, ensure_ascii=False, indent=2)}")
