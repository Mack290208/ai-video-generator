# -*- coding: utf-8 -*-
"""
批量生成机器学习知识点视频
使用方式：python batch_generate.py
"""
import json
import requests
import time

API_URL = "http://localhost:8000/tts/pipeline"

# 机器学习知识点列表
ML_TOPICS = [
    {
        "title": "什么是梯度下降",
        "segments": [
            {"template": "intro_v2", "narration": "欢迎来到机器学习课堂，今天我们来讲解梯度下降算法。"},
            {"template": "gradient_descent", "narration": "梯度下降是一种优化算法，通过迭代的方式寻找函数的最小值。"},
            {"template": "curve_descent", "narration": "学习率决定了每一步的大小，太大会震荡，太小会收敛很慢。"},
            {"template": "bullet_summary", "narration": "总结：梯度下降通过计算梯度方向，逐步逼近最优解。"},
            {"template": "outro", "narration": "感谢观看，下节课我们将讲解学习率的选择。"}
        ]
    },
    {
        "title": "线性回归原理",
        "segments": [
            {"template": "intro_v2", "narration": "今天我们来学习线性回归，这是最基础的机器学习算法之一。"},
            {"template": "formula_evolve", "narration": "线性回归的目标是找到一条直线，使得预测值与真实值的误差最小。"},
            {"template": "scatter_classify", "narration": "通过最小二乘法，我们可以计算出最佳的回归系数。"},
            {"template": "bullet_summary", "narration": "线性回归简单高效，是理解更复杂模型的基础。"},
            {"template": "outro", "narration": "下节课我们将学习逻辑回归，感谢观看。"}
        ]
    },
    {
        "title": "学习率的选择",
        "segments": [
            {"template": "intro_v2", "narration": "学习率是深度学习中最重要的超参数之一。"},
            {"template": "lr_comparison", "narration": "学习率太大会导致损失函数震荡，无法收敛。"},
            {"template": "curve_descent", "narration": "学习率太小会导致训练速度很慢，容易陷入局部最优。"},
            {"template": "data_flow", "narration": "常用的学习率调度策略包括阶梯衰减和余弦退火。"},
            {"template": "bullet_summary", "narration": "选择合适的学习率需要多次实验和验证。"},
            {"template": "outro", "narration": "感谢观看，下节课我们将讲解正则化。"}
        ]
    }
]


def generate_video(topic: dict) -> dict:
    """生成单个视频"""
    print(f"\n{'='*50}")
    print(f"正在生成: {topic['title']}")
    print(f"{'='*50}")
    
    payload = {
        "video_title": topic["title"],
        "segments": topic["segments"]
    }
    
    try:
        resp = requests.post(API_URL, json=payload, timeout=300)
        if resp.status_code == 200:
            result = resp.json()
            print(f"✅ 成功: {result.get('output_video', '未知')}")
            return result
        else:
            print(f"❌ 失败: HTTP {resp.status_code}")
            print(resp.text[:200])
            return {"error": resp.text}
    except Exception as e:
        print(f"❌ 错误: {e}")
        return {"error": str(e)}


def main():
    print(f"准备生成 {len(ML_TOPICS)} 个机器学习知识点视频")
    print(f"API: {API_URL}")
    
    results = []
    for i, topic in enumerate(ML_TOPICS, 1):
        print(f"\n[{i}/{len(ML_TOPICS)}]")
        result = generate_video(topic)
        results.append({
            "title": topic["title"],
            "result": result
        })
        time.sleep(2)  # 避免过载
    
    # 汇总结果
    print(f"\n{'='*50}")
    print("生成完成！")
    print(f"{'='*50}")
    
    success = sum(1 for r in results if r["result"].get("status") == "completed")
    print(f"成功: {success}/{len(results)}")
    
    for r in results:
        status = "✅" if r["result"].get("status") == "completed" else "❌"
        video = r["result"].get("output_video", "无")
        print(f"{status} {r['title']}: {video}")


if __name__ == "__main__":
    main()
