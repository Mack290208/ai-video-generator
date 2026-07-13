# -*- coding: utf-8 -*-
"""
test_llm_api.py
测试 LLM API 连接（支持 MiMo、DeepSeek、OpenAI 兼容）
"""
import os
import sys
from pathlib import Path

# 加载 .env 文件
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

import requests


def test_mimo_api():
    """测试 MiMo API"""
    api_key = os.getenv("MIMO_API_KEY")
    base_url = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    model = os.getenv("MIMO_MODEL", "mimo-v2-pro")
    
    print("=" * 60)
    print("测试 MiMo API (小米大模型)")
    print("=" * 60)
    
    if not api_key or api_key == "your_mimo_api_key_here":
        print("❌ MIMO_API_KEY 未配置")
        print()
        print("请按以下步骤配置：")
        print("1. 访问 https://open.xiaomi.com 或联系小米 AI 团队")
        print("2. 获取 MiMo API Key")
        print("3. 编辑 .env 文件，替换 your_mimo_api_key_here")
        print()
        return False
    
    print(f"API 地址: {base_url}")
    print(f"模型: {model}")
    
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "你好，请回复'连接成功'"}
                ],
                "max_tokens": 10
            },
            timeout=15
        )
        
        if resp.status_code == 200:
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✅ API 连接成功！")
            print(f"   模型响应: {content}")
            return True
        else:
            print(f"❌ API 调用失败: {resp.status_code}")
            print(f"   错误信息: {resp.text}")
            return False
            
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


def test_deepseek_api():
    """测试 DeepSeek API"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    
    print()
    print("=" * 60)
    print("测试 DeepSeek API")
    print("=" * 60)
    
    if not api_key or api_key == "your_deepseek_api_key_here":
        print("❌ DEEPSEEK_API_KEY 未配置")
        print()
        print("请按以下步骤配置：")
        print("1. 访问 https://platform.deepseek.com")
        print("2. 注册/登录账号")
        print("3. 创建 API Key")
        print("4. 编辑 .env 文件，替换 your_deepseek_api_key_here")
        print()
        return False
    
    try:
        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": "你好，请回复'连接成功'"}
                ],
                "max_tokens": 10
            },
            timeout=15
        )
        
        if resp.status_code == 200:
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✅ API 连接成功！")
            print(f"   模型响应: {content}")
            return True
        else:
            print(f"❌ API 调用失败: {resp.status_code}")
            print(f"   错误信息: {resp.text}")
            return False
            
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


def test_storyboard_generation():
    """测试 storyboard 生成"""
    print()
    print("=" * 60)
    print("测试 storyboard 生成")
    print("=" * 60)
    
    # 导入 storyboard 服务
    sys.path.insert(0, str(Path(__file__).parent))
    from llm_storyboard_service import generate_storyboard_with_llm
    
    topic = "梯度下降算法"
    print(f"主题: {topic}")
    print("正在生成...")
    
    storyboard = generate_storyboard_with_llm(topic)
    
    if storyboard.get("error"):
        print(f"❌ 生成失败: {storyboard['error']}")
        return False
    else:
        print(f"✅ 生成成功！")
        print(f"   视频标题: {storyboard.get('video_title', '未命名')}")
        print(f"   段落数量: {len(storyboard.get('segments', []))}")
        print(f"   预计时长: {storyboard.get('duration_target_seconds', 0)} 秒")
        
        # 显示段落概览
        print()
        print("段落概览:")
        for i, seg in enumerate(storyboard.get("segments", []), 1):
            template = seg.get("template", "?")
            narration = seg.get("narration", "")[:30]
            print(f"   {i}. [{template}] {narration}...")
        
        return True


def main():
    """主测试函数"""
    print("AI助教视频生成系统 - LLM API 测试")
    print()
    
    # 测试 MiMo
    mimo_ok = test_mimo_api()
    
    # 测试 DeepSeek
    deepseek_ok = test_deepseek_api()
    
    # 如果有可用的 API，测试 storyboard 生成
    if mimo_ok or deepseek_ok:
        print()
        print("=" * 60)
        print("检测到可用的 API，测试 storyboard 生成...")
        print("=" * 60)
        test_storyboard_generation()
    else:
        print()
        print("=" * 60)
        print("⚠️  没有可用的 API，请先配置其中一个：")
        print("  - MIMO_API_KEY (小米 MiMo)")
        print("  - DEEPSEEK_API_KEY (DeepSeek)")
        print("=" * 60)


if __name__ == "__main__":
    main()
