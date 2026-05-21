"""
services/whisper_align_service.py
---------------------------------
用 faster-whisper 对每段 TTS 旁白做"反向对齐"：
  - 输入：wav 文件 + 我们已知的 narration 文本
  - 输出：word-level (start, end) 时间戳列表

然后把 narration 按标点切成 cue，**字幕文本永远以 narration 为准**，
只是把每条 cue 的起点时间锚定到 whisper 找到的真实词时间。

v2 改进（2026-05-16）：
  - 字幕文本严格 = narration 切的 cue（不再丢字符）
  - cue.start 用首字符在 word 序列里"窗口匹配"找到，而非按指针推进
  - 找不到就用上一条 end + 估算位置兜底（whisper 漏字也不会错位）
  - 最后一条 cue 始终延伸到音频末尾（避免末尾被压缩）
  - cue.end = next.start，连接式，整段不留空隙

模型选择：默认 small，中文足够准。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_SENTENCE_ENDINGS = "。！？!?；;"
_SOFT_BREAKS = "，,：:、"


@dataclass
class WordToken:
    text: str
    start: float
    end: float


# ============================================================
# 1. faster-whisper 转录
# ============================================================
class WhisperAligner:
    """faster-whisper 包装。延迟加载模型。"""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None  # type: ignore[assignment]

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel  # 延迟导入

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    def transcribe_words(
        self,
        wav_path: str | Path,
        language: str = "zh",
        initial_prompt: str | None = None,
    ) -> list[WordToken]:
        """对 wav 做 word-level 转录。中文一般 1 word = 1 字。"""
        self._ensure_model()
        wav_path = str(Path(wav_path))

        segments, _info = self._model.transcribe(  # type: ignore[union-attr]
            wav_path,
            language=language,
            word_timestamps=True,
            beam_size=5,
            initial_prompt=initial_prompt,
            vad_filter=False,
        )

        words: list[WordToken] = []
        for seg in segments:
            if not seg.words:
                continue
            for w in seg.words:
                if w.start is None or w.end is None:
                    continue
                text = (w.word or "").strip()
                if not text:
                    continue
                words.append(WordToken(text=text, start=float(w.start), end=float(w.end)))
        return words


# ============================================================
# 2. 文本切 cue + 时间对齐
# ============================================================
_PUNCT_AND_SPACE = set("。！？!?；;，,：:、 \t\n\r\u3000\"'\u2018\u2019\u201c\u201d《》()()【】[]")


def _normalize_for_match(s: str) -> str:
    """去掉标点和空格，并把繁体映射到简体（仅用于对齐匹配）。"""
    cleaned = "".join(ch for ch in s if ch not in _PUNCT_AND_SPACE)
    return _trad_to_simp(cleaned)



try:
    from opencc import OpenCC as _OpenCC
    _t2s = _OpenCC("t2s")
    def _trad_to_simp_impl(s: str) -> str:
        return _t2s.convert(s)
except Exception:
    def _trad_to_simp_impl(s: str) -> str:
        return s


def _trad_to_simp(s: str) -> str:
    """Map traditional chars to simplified (for matching only). Uses opencc."""
    try:
        return _trad_to_simp_impl(s)
    except Exception:
        return s

def split_to_cues(
    text: str, min_chars: int = 8, max_chars: int = 22
) -> list[str]:
    """按句号 / 问号 / 叹号切，长句再用逗号切，短句合并。"""
    text = (text or "").strip()
    if not text:
        return []

    pattern = f"([{re.escape(_SENTENCE_ENDINGS)}])"
    parts = re.split(pattern, text)
    primary: list[str] = []
    buf = ""
    for p in parts:
        if not p:
            continue
        if p in _SENTENCE_ENDINGS:
            buf += p
            if buf.strip():
                primary.append(buf.strip())
            buf = ""
        else:
            buf += p
    if buf.strip():
        primary.append(buf.strip())

    refined: list[str] = []
    soft_pattern = f"([{re.escape(_SOFT_BREAKS)}])"
    for chunk in primary:
        if len(chunk) <= max_chars:
            refined.append(chunk)
            continue
        sub = re.split(soft_pattern, chunk)
        cur = ""
        for piece in sub:
            if not piece:
                continue
            if piece in _SOFT_BREAKS:
                cur += piece
                if len(cur) >= max_chars:
                    refined.append(cur.strip(_SOFT_BREAKS + " "))
                    cur = ""
            else:
                if len(cur) + len(piece) > max_chars and cur.strip():
                    refined.append(cur.strip(_SOFT_BREAKS + " "))
                    cur = piece
                else:
                    cur += piece
        if cur.strip():
            refined.append(cur.strip(_SOFT_BREAKS + " "))

    merged: list[str] = []
    for piece in refined:
        if merged and len(merged[-1]) < min_chars:
            merged[-1] = merged[-1] + piece
        else:
            merged.append(piece)

    return [c.strip() for c in merged if c.strip()]


def align_cues_to_words(
    narration: str,
    words: list[WordToken],
    seg_offset: float = 0.0,
    seg_duration: float | None = None,
    min_chars: int = 8,
    max_chars: int = 22,
) -> list[dict[str, Any]]:
    """
    把 narration 切成 cue，用 words 时间戳锚定起点。

    新策略 v3 (2026-05-16 night)：
      第一遍：尝试在 word 序列里给每个 cue 锚定首字符 -> aligned cues
      第二遍：未锚定的 cue 在两个相邻 anchor 之间按字符比例插值
      第三遍：cue.end = next.start；最后一条 → seg_end
      第四遍：min_cue_duration 保护（在 write_aligned_srt 里）

    关键：字幕文本永远完整 = narration 切的 cue。时间是兜底估算，但绝不丢字。
    """
    cues_text = split_to_cues(narration, min_chars=min_chars, max_chars=max_chars)
    if not cues_text:
        return []

    seg_end = (
        seg_offset + float(seg_duration)
        if seg_duration is not None
        else seg_offset + (words[-1].end if words else sum(len(c) for c in cues_text) * 0.18)
    )
    seg_len = max(0.1, seg_end - seg_offset)

    cue_norms = [_normalize_for_match(c) for c in cues_text]
    cue_lens = [len(n) for n in cue_norms]
    total_chars = sum(cue_lens) or 1

    # 累积字符位置 (用于按字符比例插值)
    cum_chars = [0]
    for n in cue_lens:
        cum_chars.append(cum_chars[-1] + n)

    # word 序列首字符
    word_first_chars: list[tuple[str, int]] = []
    for wi, w in enumerate(words):
        norm = _normalize_for_match(w.text)
        if norm:
            word_first_chars.append((norm[0], wi))

    have_words = bool(word_first_chars)

    # ============ 第一遍：anchor pass ============
    # 对每条 cue 尝试找到首字符
    anchors: list[float | None] = [None] * len(cues_text)
    word_cursor = 0
    for ci, (cue_text, norm, ncue) in enumerate(zip(cues_text, cue_norms, cue_lens)):
        if ncue <= 0 or not have_words:
            continue
        first_ch = norm[0]
        # 估算位置
        char_progress = cum_chars[ci] / total_chars
        est_word_idx = int(char_progress * len(word_first_chars))

        # 大窗口：从 word_cursor 到 est+25
        window_lo = word_cursor
        window_hi = min(len(word_first_chars), max(est_word_idx + 25, word_cursor + 25))
        for k in range(window_lo, window_hi):
            ch, wi = word_first_chars[k]
            if ch == first_ch:
                anchors[ci] = words[wi].start + seg_offset
                word_cursor = k + 1
                break

    # ============ 第二遍：插值未锚定的 cue ============
    # 在两个相邻锚点之间按字符比例分配时间
    # 边界: 最前 = seg_offset；最后 = seg_end (强制)
    # 第一条如果没锚定，用 seg_offset 起点
    if anchors[0] is None:
        anchors[0] = seg_offset

    # 假设最后有一个虚拟锚点 = seg_end (位置 = total_chars)
    # 找到所有真实锚点 + 起点
    real_indices: list[int] = [i for i, a in enumerate(anchors) if a is not None]
    real_times: list[float] = [anchors[i] for i in real_indices]

    # 在每对锚点之间，按字符比例分配
    starts: list[float] = [0.0] * len(cues_text)
    aligned_flags: list[bool] = [a is not None for a in anchors]

    # 先填 anchored 的
    for i, t in zip(real_indices, real_times):
        starts[i] = t

    # 在每两个锚点之间插值
    for ai in range(len(real_indices) - 1):
        lo_i = real_indices[ai]
        hi_i = real_indices[ai + 1]
        lo_t = real_times[ai]
        hi_t = real_times[ai + 1]
        if hi_i == lo_i + 1:
            continue
        # 在 lo_i+1 ... hi_i-1 之间按字符比例分配
        # 累积字符 cum_chars[lo_i+1] (相对) 到 cum_chars[hi_i] (相对)
        char_lo = cum_chars[lo_i + 1]   # 第一个被插值 cue 的起点字符位
        char_hi = cum_chars[hi_i]       # hi_i cue 的起点字符位
        char_span = max(1, char_hi - char_lo)
        time_span = max(0.1, hi_t - lo_t)
        for j in range(lo_i + 1, hi_i):
            ratio = (cum_chars[j] - char_lo) / char_span
            starts[j] = lo_t + ratio * time_span

    # 最后一个锚点之后的 cue（如果有）：用 seg_end 作虚拟锚定
    last_real = real_indices[-1] if real_indices else 0
    if last_real < len(cues_text) - 1:
        lo_i = last_real
        lo_t = real_times[-1] if real_times else seg_offset
        hi_t = seg_end
        char_lo = cum_chars[lo_i + 1]
        char_hi = cum_chars[len(cues_text)]
        char_span = max(1, char_hi - char_lo)
        time_span = max(0.1, hi_t - lo_t)
        for j in range(lo_i + 1, len(cues_text)):
            ratio = (cum_chars[j] - char_lo) / char_span
            starts[j] = lo_t + ratio * time_span

    # ============ 第三遍：构造 cue 字典 ============
    out: list[dict[str, Any]] = []
    for ci, cue_text in enumerate(cues_text):
        if cue_lens[ci] <= 0:
            continue
        out.append({
            "text": cue_text,
            "start": starts[ci],
            "end": 0.0,  # 占位
            "aligned": aligned_flags[ci],
        })

    # 确保单调递增
    for i in range(1, len(out)):
        if out[i]["start"] <= out[i - 1]["start"] + 0.05:
            out[i]["start"] = out[i - 1]["start"] + 0.3

    # end = next.start; last → seg_end
    for i in range(len(out) - 1):
        out[i]["end"] = out[i + 1]["start"]
    if out:
        out[-1]["end"] = seg_end

    # end <= start 修正
    for cue in out:
        if cue["end"] <= cue["start"]:
            cue["end"] = cue["start"] + 0.3

    return out


# ============================================================
# 3. 整段流程
# ============================================================
def align_segments(
    audio_results: list[dict[str, Any]],
    aligner: WhisperAligner,
    language: str = "zh",
    verbose: bool = True,
) -> list[dict[str, Any]]:
    """对每段 wav 做对齐，返回带全局 offset 的 cue 列表。"""
    cursor = 0.0
    all_cues: list[dict[str, Any]] = []

    for i, item in enumerate(audio_results, start=1):
        wav_path = item.get("audio_path")
        duration = float(item.get("audio_duration_seconds") or 0.0)
        text_for_subtitle = (
            item.get("subtitle_text")
            or item.get("narration_text")
            or ""
        ).strip()

        if not wav_path or not duration or not text_for_subtitle:
            cursor += duration
            continue

        if verbose:
            print(f"    - seg {i}: aligning {Path(wav_path).name} ({duration:.2f}s)")

        try:
            words = aligner.transcribe_words(
                wav_path,
                language=language,
                initial_prompt=text_for_subtitle[:200] if text_for_subtitle else None,
            )
            if verbose:
                print(f"        -> whisper got {len(words)} words")
        except Exception as e:
            if verbose:
                print(f"        !! whisper failed: {e}; fallback to char-ratio")
            words = []

        cues = align_cues_to_words(
            narration=text_for_subtitle,
            words=words,
            seg_offset=cursor,
            seg_duration=duration,
        )
        for c in cues:
            c["seg_idx"] = i
            all_cues.append(c)

        cursor += duration

    return all_cues


# ============================================================
# 4. SRT 写入
# ============================================================
def _format_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3600 * 1000)
    minutes, rem = divmod(rem, 60 * 1000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_aligned_srt(
    cues: list[dict[str, Any]],
    output_path: str | Path,
    min_cue_duration: float = 1.2,
    chars_per_second: float = 6.5,
) -> dict[str, Any]:
    """
    写 SRT。
    每条 cue 最少持续：max(min_cue_duration, len(text) / chars_per_second)。
    若延长会越过下一条 cue.start，则不超过下一条 cue.start。
    最后一条 cue 的 end 不变（已在 align 阶段对齐到 seg_end）。
    """
    cleaned: list[dict[str, Any]] = []
    for cue in cues:
        text = (cue.get("text") or "").strip()
        if not text:
            continue
        start = float(cue.get("start") or 0.0)
        end = float(cue.get("end") or start + 0.5)
        if end <= start:
            end = start + 0.3
        cleaned.append({"text": text, "start": start, "end": end, "aligned": cue.get("aligned", False)})

    # 动态最小 cue 时长：每条 cue 至少需要 len(text) / chars_per_second 秒
    # 不够就向后级联推迟下一条 cue.start（最后一条不要被无限延长）
    n = len(cleaned)
    for i in range(n):
        cur = cleaned[i]
        dur = cur["end"] - cur["start"]
        text_len = sum(1 for ch in cur["text"] if ch not in _PUNCT_AND_SPACE)
        needed = max(min_cue_duration, text_len / chars_per_second)
        if dur >= needed:
            continue
        target_end = cur["start"] + needed
        if i + 1 < n:
            # 推迟下一条，但不能晚于"下下条 start - 它自己的最小时长"
            shift = target_end - cleaned[i + 1]["start"]
            if shift > 0:
                cleaned[i + 1]["start"] += shift
                if cleaned[i + 1]["end"] < cleaned[i + 1]["start"] + 0.3:
                    cleaned[i + 1]["end"] = cleaned[i + 1]["start"] + 0.3
        else:
            # 最后一条：不能超过 seg_end，已经是 seg_end，不延长
            target_end = cur["end"]
        cur["end"] = max(cur["end"], target_end)

    lines: list[str] = []
    counter = 1
    for cue in cleaned:
        lines.append(str(counter))
        lines.append(f"{_format_timestamp(cue['start'])} --> {_format_timestamp(cue['end'])}")
        lines.append(cue["text"])
        lines.append("")
        counter += 1

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")

    aligned_count = sum(1 for c in cues if c.get("aligned"))
    return {
        "path": str(output_path),
        "cue_count": counter - 1,
        "aligned_cues": aligned_count,
        "fallback_cues": (counter - 1) - aligned_count,
    }
