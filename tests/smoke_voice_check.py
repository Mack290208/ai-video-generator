import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

1|"""快速 TTS 烟雾：1 句话验证服务 + 神里音色 + 权重正常"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from services.tts_service import GPTSoVITSTTSService, TTSConfig

cfg = TTSConfig.from_env()
tts = GPTSoVITSTTSService(cfg)

out = ROOT / "outputs" / "audio" / "_smoke_voice_check.wav"
out.parent.mkdir(parents=True, exist_ok=True)

text = "大家好，今天我们来上一节关于神经网络入门的课。"
print(f"[smoke] 合成: {text}")
r = tts.synthesize_to_file(text=text, output_path=out)
print(f"[OK] {out.name}")
print(f"     duration = {r.get('duration_seconds'):.2f}s")
print(f"     fallback = {r.get('used_fallback', False)}")
print(f"     attempts = {r.get('attempts')}")
print(f"     path     = {out}")
