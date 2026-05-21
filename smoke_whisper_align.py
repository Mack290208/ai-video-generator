"""smoke 测试 whisper 对齐：拿误差最大的 seg_05 (formula_evolve, 28.88s) 做对齐验证。"""
import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.whisper_align_service import (
    WhisperAligner,
    align_cues_to_words,
    split_to_cues,
    write_aligned_srt,
)

WAV = Path("outputs/audio/nn_intro_long_seg_05.wav")
NARRATION = (
    "那神经网络是怎么学习的呢？关键在于损失函数。损失函数衡量预测值和真实值的差距。"
    "我们以最常见的均方误差为例，看一下怎么求出最优参数。从损失函数定义出发，"
    "求导整理之后，可以解出参数的最优解。这就是损失函数的最优化过程。"
)

print(f"[smoke] wav exists: {WAV.exists()}, size={WAV.stat().st_size if WAV.exists() else 'N/A'}")
print(f"[smoke] narration chars: {len(NARRATION)}")
print(f"[smoke] cues split:")
for c in split_to_cues(NARRATION):
    print(f"    [{len(c):2d}] {c}")
print()

print("[smoke] loading faster-whisper small (CPU int8)...")
t0 = time.time()
aligner = WhisperAligner(model_size="small", device="cpu", compute_type="int8")
aligner._ensure_model()
print(f"  model loaded in {time.time() - t0:.1f}s")

print("[smoke] transcribing...")
t1 = time.time()
words = aligner.transcribe_words(WAV, language="zh", initial_prompt=NARRATION[:200])
elapsed = time.time() - t1
print(f"  done in {elapsed:.1f}s -> {len(words)} words (RTF={elapsed/28.88:.2f}x)")

print()
print("[smoke] first 12 words:")
for w in words[:12]:
    print(f"  {w.start:6.2f} - {w.end:6.2f}  '{w.text}'")
print(f"  ... last word ends at {words[-1].end:.2f}s (audio duration ~28.88s)")

print()
print("[smoke] aligned cues:")
cues = align_cues_to_words(NARRATION, words, seg_offset=0.0, seg_duration=28.88)
for c in cues:
    flag = "OK" if c.get("aligned") else "FB"
    print(f"  [{flag}] {c['start']:6.2f} -> {c['end']:6.2f}  '{c['text']}'")

# 写出 SRT 看看
out_srt = Path("outputs/subtitles/seg_05_aligned.srt")
info = write_aligned_srt(cues, out_srt)
print()
print(f"[smoke] wrote {info}")
