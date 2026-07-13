"""
test_tts_resilience.py — 验证 A1 改造：TTS 重试 + 健康检查 + 静默 fallback

两个测试：
  1. happy path：服务活着，正常合成
  2. fallback path：故意指到死端口，验证重试穷尽后写出静默 wav，pipeline 不挂
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from __future__ import annotations

import sys
import wave
import contextlib
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from services.tts_service import GPTSoVITSTTSService, TTSConfig


OUT_DIR = BASE_DIR / "outputs" / "audio_test_resilience"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_wav_duration(p: Path) -> float:
    with contextlib.closing(wave.open(str(p), "rb")) as wf:
        return wf.getnframes() / float(wf.getframerate())


def test_happy_path() -> bool:
    print("\n=== Test 1: happy path（服务活着，正常合成）===")
    cfg = TTSConfig.from_env()
    print(f"  base_url        = {cfg.base_url}")
    print(f"  retry_attempts  = {cfg.retry_attempts}")
    print(f"  health_check    = {cfg.health_check_enabled}")
    print(f"  silence_fallbk  = {cfg.silence_fallback}")

    tts = GPTSoVITSTTSService(cfg)
    out = OUT_DIR / "happy.wav"
    if out.exists():
        out.unlink()

    try:
        r = tts.synthesize_to_file(
            text="这是一个测试用的短句，验证正常路径下的合成。",
            output_path=out,
        )
    except Exception as e:
        print(f"  [FAIL] 合成抛错: {e}")
        return False

    print(f"  -> duration       = {r.get('duration_seconds')}s")
    print(f"  -> used_fallback  = {r.get('used_fallback')}")
    print(f"  -> attempts       = {r.get('attempts')}")
    if r.get("used_fallback"):
        print(f"  [FAIL] 服务活着却走了 fallback")
        return False
    if not out.exists() or out.stat().st_size < 1024:
        print(f"  [FAIL] 输出文件不存在或太小")
        return False
    print(f"  [OK] happy path 通过")
    return True


def test_fallback_path() -> bool:
    print("\n=== Test 2: fallback path（指到死端口，验证静默 wav fallback）===")

    cfg = TTSConfig.from_env()
    cfg.base_url = "http://127.0.0.1:65500"  # 几乎肯定无人监听
    cfg.retry_attempts = 3
    cfg.retry_backoff_seconds = 0.3  # 加速测试
    cfg.timeout_seconds = 3
    cfg.silence_fallback = True
    cfg.silence_fallback_seconds = 2.0
    print(f"  base_url        = {cfg.base_url}（故意指错）")
    print(f"  retry_attempts  = {cfg.retry_attempts}")
    print(f"  silence_fb_secs = {cfg.silence_fallback_seconds}")

    tts = GPTSoVITSTTSService(cfg)
    out = OUT_DIR / "fallback.wav"
    if out.exists():
        out.unlink()

    try:
        r = tts.synthesize_to_file(
            text="这条文本应该永远到不了，因为端口是死的。",
            output_path=out,
        )
    except Exception as e:
        print(f"  [FAIL] 应该走静默 fallback，却抛错了: {e}")
        return False

    if not out.exists():
        print(f"  [FAIL] 没写出文件")
        return False

    dur = get_wav_duration(out)
    print(f"  -> file_duration  = {dur:.2f}s")
    print(f"  -> used_fallback  = {r.get('used_fallback')}")
    print(f"  -> attempts       = {len(r.get('attempts', []))} 次（期望 3）")

    if not r.get("used_fallback"):
        print(f"  [FAIL] used_fallback 应为 True")
        return False
    if len(r.get("attempts", [])) != 3:
        print(f"  [FAIL] 重试次数不对")
        return False
    if abs(dur - cfg.silence_fallback_seconds) > 0.2:
        print(f"  [FAIL] 静默时长偏差过大")
        return False
    print(f"  [OK] fallback path 通过")
    return True


def main() -> int:
    results = []
    results.append(("happy_path", test_happy_path()))
    results.append(("fallback_path", test_fallback_path()))

    print("\n" + "=" * 50)
    print("总结：")
    all_ok = True
    for name, ok in results:
        flag = "OK  " if ok else "FAIL"
        print(f"  [{flag}] {name}")
        all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
