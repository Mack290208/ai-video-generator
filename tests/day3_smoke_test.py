# -*- coding: utf-8 -*-
"""
Day 3 冒烟测试：直接打 /generate-video，验证全链路。
- 需要先启动 server.py（端口 8000）
- 需要 GPT-SoVITS api_v2.py 在 127.0.0.1:9880 跑着
"""

import json
import time
import requests

SERVER = "http://127.0.0.1:8000"


def test_health():
    r = requests.get(f"{SERVER}/health", timeout=10)
    print("=== /health ===")
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    print()


def test_generate_video():
    """模拟 Dify 调用：3 段梯度下降教学脚本。"""
    payload = {
        "request_id": f"day3_smoke_{int(time.time())}",
        "topic": "岳阳楼记",
        "title": "神里凌华音色读岳阳楼记",
        "segments": [
            {
                "id": "seg1",
                "title": "第一段",
                "narration": "庆历四年春，滕子京谪守巴陵郡。越明年，政通人和，百废具兴，乃重修岳阳楼，增其旧制，刻唐贤今人诗赋于其上，属予作文以记之。"
            },
            {
                "id": "seg2",
                "title": "第二段",
                "narration": "予观夫巴陵胜状，在洞庭一湖。衔远山，吞长江，浩浩汤汤，横无际涯，朝晖夕阴，气象万千。此则岳阳楼之大观也，前人之述备矣。然则北通巫峡，南极潇湘，迁客骚人，多会于此，览物之情，得无异乎？"
            },
        ]
    }

    r = requests.post(f"{SERVER}/generate-video", json=payload, timeout=600)
    print("=== /generate-video ===")
    print("status_code:", r.status_code)
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print()

    # 打印摘要
    if r.status_code == 200:
        ok_count = data.get("segments_tts_generated", 0)
        total = data.get("segments_received", 0)
        print(f"✅ 结果：{ok_count}/{total} 段音频生成成功")
        for item in data.get("audio_results", []):
            print(f"  - seg_{item['segment_index']:02d}: "
                  f"{item['audio_duration_seconds']}s  {item['audio_path']}")


if __name__ == "__main__":
    test_health()
    test_generate_video()
