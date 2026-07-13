# -*- coding: utf-8 -*-
import os
import json
import requests

# 加载 .env
with open('.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

# 1. 生成 storyboard
from llm_storyboard_service import generate_storyboard_with_llm

topic = "神经网络基础"
print("Step 1: 生成 storyboard...")
storyboard = generate_storyboard_with_llm(topic)

if storyboard.get("error"):
    print("生成失败:", storyboard["error"])
    exit(1)

print(f"标题: {storyboard.get('video_title')}")
print(f"段落数: {len(storyboard.get('segments', []))}")

# 2. 调用视频生成 API
print("\nStep 2: 生成视频...")
try:
    resp = requests.post(
        'http://127.0.0.1:8000/tts/pipeline',
        json=storyboard,
        timeout=600  # 10分钟超时
    )
    
    if resp.status_code == 200:
        result = resp.json()
        print("视频生成成功!")
        print("视频文件:", result.get("output_video"))
        print("时长:", result.get("duration"), "秒")
    else:
        print(f"生成失败: {resp.status_code}")
        print(resp.text[:500])
        
except Exception as e:
    print(f"请求失败: {e}")
