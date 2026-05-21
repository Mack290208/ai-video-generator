"""
duration_estimator.py — 中文旁白时长估算

经验来源（A2 阶段）：
  - 5-15 决策树视频实跑：5 段共 484 字中文 -> 实测 88.44s
  - 反推语速 ≈ 5.5 字/秒（神里绫华 e10 音色，speed_factor=1.0）

公式：
  时长(秒) ≈ 中文字符数 / 5.5 + 末尾标点停顿

末尾标点停顿（经验值）：
  。？！  -> +0.40s（句末停顿）
  ，、；  -> +0.20s（句中停顿）
  其他    -> +0.0s

兜底：min 时长 1.5s（避免 LLM 写出极短旁白时落到太接近 0）

公式输入纯字符串即可，不依赖任何上下文，方便：
  - LLM 在生成 storyboard 时自检
  - run_from_storyboard 在跑前打印预估
  - 单元测试
"""
from __future__ import annotations

import re
from typing import Iterable

# ---- 经验常数 ----
DEFAULT_CHARS_PER_SECOND = 5.5
SENTENCE_END_PUNCT = "。？！?!."
PHRASE_PUNCT = "，、；,;"
SENTENCE_END_PAUSE = 0.40
PHRASE_PAUSE = 0.20
MIN_DURATION = 1.5


# 仅统计"会被读出来"的字符：中文字符 + ASCII 字母数字
# （希腊字母、数学符号在 narration 里通常已经被 LLM 替换成中文，所以可以忽略）
_COUNTABLE_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbfA-Za-z0-9]")


def count_speakable_chars(text: str) -> int:
    """统计旁白里"会被 TTS 读出"的字符数。

    规则：
      - 中文字符（CJK 基本 + 扩展 A）算 1
      - ASCII 字母 / 数字算 1
      - 标点、空白、特殊符号不计入字数（但会用于停顿统计）
    """
    if not text:
        return 0
    return len(_COUNTABLE_RE.findall(text))


def count_pause_seconds(text: str) -> float:
    """根据标点累加停顿秒数。"""
    if not text:
        return 0.0
    total = 0.0
    for ch in text:
        if ch in SENTENCE_END_PUNCT:
            total += SENTENCE_END_PAUSE
        elif ch in PHRASE_PUNCT:
            total += PHRASE_PAUSE
    return total


def estimate_narration_seconds(
    text: str,
    chars_per_second: float = DEFAULT_CHARS_PER_SECOND,
    min_seconds: float = MIN_DURATION,
) -> float:
    """估算一段中文旁白的时长（秒）。"""
    chars = count_speakable_chars(text)
    pause = count_pause_seconds(text)
    raw = chars / max(0.1, chars_per_second) + pause
    return round(max(min_seconds, raw), 2)


def estimate_storyboard_seconds(
    narrations: Iterable[str],
    chars_per_second: float = DEFAULT_CHARS_PER_SECOND,
) -> dict:
    """估算整段 storyboard 的总时长 + 每段时长。

    返回：
      {
        "total_seconds": 88.44,
        "per_segment": [5.6, 16.4, ...],
        "chars_per_second": 5.5,
      }
    """
    per = [
        estimate_narration_seconds(t, chars_per_second=chars_per_second)
        for t in narrations
    ]
    return {
        "total_seconds": round(sum(per), 2),
        "per_segment": per,
        "chars_per_second": chars_per_second,
    }


# ---------------- 自检（python duration_estimator.py 直接跑可看示例）----------------
if __name__ == "__main__":
    # 取 5-15 决策树视频里的真实 narration 抽样
    samples = [
        ("seg1 intro", "大家好，今天我们来讲一个机器学习中非常重要的算法：决策树。"),
        ("seg5 short", "好的，这就是决策树的全部内容啦。"),
        ("超短句", "好。"),
    ]
    for name, txt in samples:
        chars = count_speakable_chars(txt)
        pause = count_pause_seconds(txt)
        secs = estimate_narration_seconds(txt)
        print(f"{name:14s}  chars={chars:3d}  pause={pause:4.2f}s  -> est={secs:5.2f}s")
