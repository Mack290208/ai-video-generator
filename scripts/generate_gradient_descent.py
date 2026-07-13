# -*- coding: utf-8 -*-
"""
生成一个高质量的梯度下降教学视频
"""
import os
import json
import requests
import time

# 加载 .env
with open('.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

# 精心设计的 storyboard
storyboard = {
    "video_title": "梯度下降：机器学习的核心引擎",
    "duration_target_seconds": 60,
    "tts_voice": "zh-CN-XiaoxiaoNeural",
    "segments": [
        {
            "template": "intro_v2",
            "narration": "梯度下降，机器学习最核心的优化算法。今天我们用一分钟，彻底搞懂它。",
            "subtitle": "",
            "params": {
                "title": "梯度下降算法",
                "subtitle": "机器学习的核心引擎",
                "duration": 5.0
            }
        },
        {
            "template": "curve_descent",
            "narration": "想象你站在一座山上，眼前是一片山谷。你的目标是找到最低点。梯度下降的策略很简单：朝着最陡峭的下坡方向，一步一步往下走。",
            "subtitle": "",
            "params": {
                "title": "下山的策略",
                "func_label": "损失函数 L(θ)",
                "rule_label": "沿负梯度方向更新",
                "start_x": 0.8,
                "lr": 0.15,
                "steps": 8,
                "duration": 15.0
            }
        },
        {
            "template": "formula_evolve",
            "narration": "数学上，我们用这个公式来描述每一步的更新：新的参数等于旧参数减去学习率乘以梯度。梯度告诉我们上升最快的方向，减去它，就是下降最快的方向。",
            "subtitle": "",
            "params": {
                "title": "更新规则",
                "formulas": [
                    "θ_{new} = θ_{old} - α · ∇L(θ)",
                    "α: 学习率（步长）",
                    "∇L(θ): 梯度方向"
                ],
                "duration": 12.0
            }
        },
        {
            "template": "lr_comparison",
            "narration": "学习率的选择至关重要。太小了，收敛太慢；太大了，会来回震荡甚至发散。好的学习率，既能快速收敛，又不会跳过最优点。",
            "subtitle": "",
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
            "subtitle": "",
            "params": {
                "title": "本节要点回顾",
                "point_1": "沿负梯度方向更新参数 θ",
                "point_2": "学习率 α 控制步长大小",
                "point_3": "选好学习率是调参关键",
                "duration": 12.0
            }
        },
        {
            "template": "outro",
            "narration": "感谢观看！梯度下降是神经网络训练的基础，理解它，你就迈出了深度学习的第一步。",
            "subtitle": "",
            "params": {
                "title": "感谢观看",
                "points": ["梯度下降是神经网络训练的基础", "理解它 = 迈出深度学习第一步"],
                "duration": 4.0
            }
        }
    ]
}

print("=" * 60)
print("梯度下降教学视频 - 视频生成")
print("=" * 60)
print(f"标题: {storyboard['video_title']}")
print(f"段落数: {len(storyboard['segments'])}")
print(f"目标时长: {storyboard['duration_target_seconds']} 秒")
print()

# 显示段落概览
for i, seg in enumerate(storyboard['segments'], 1):
    tpl = seg['template']
    narr = seg['narration'][:50]
    dur = seg['params'].get('duration', '?')
    print(f"  {i}. [{tpl}] ({dur}s) {narr}...")

print()
print("开始生成视频...")
print("=" * 60)

# 保存 storyboard
with open('storyboard_gradient_descent.json', 'w', encoding='utf-8') as f:
    json.dump(storyboard, f, ensure_ascii=False, indent=2)
print("Storyboard 已保存到 storyboard_gradient_descent.json")

# 调用视频生成 API
start_time = time.time()
try:
    resp = requests.post(
        'http://127.0.0.1:8000/tts/pipeline',
        json=storyboard,
        timeout=600
    )
    
    elapsed = time.time() - start_time
    print(f"\nAPI 响应时间: {elapsed:.1f} 秒")
    print(f"状态码: {resp.status_code}")
    
    if resp.status_code == 200:
        result = resp.json()
        print("\n✅ 视频生成成功!")
        print(f"视频文件: {result.get('output_video')}")
        print(f"总时长: {result.get('duration')} 秒")
        print(f"字幕文件: {result.get('subtitle_file')}")
    else:
        print(f"\n❌ 生成失败: {resp.text[:500]}")
        
except Exception as e:
    print(f"\n❌ 请求失败: {e}")
