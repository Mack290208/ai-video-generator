from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _format_timestamp(seconds: float) -> str:
    """把秒数格式化为 SRT 时间戳：HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3600 * 1000)
    minutes, rem = divmod(rem, 60 * 1000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


# 中英文常见的断句标点（保留到当前小句末尾）
_SENTENCE_ENDINGS = "。！？!?；;"
_SOFT_BREAKS = "，,：:、"


def split_to_cues(text: str, min_chars: int = 8, max_chars: int = 22) -> list[str]:
    """
    把一段旁白切成若干短句，作为字幕 cue。
    规则：
      - 先按句号/问号/叹号这种强结束标点切
      - 如果单句太长（> max_chars），再按逗号等软标点切
      - 相邻过短的片段尝试合并到不小于 min_chars
    返回去除前后空白后的字符串列表（已丢掉末尾标点）。
    """
    text = (text or "").strip()
    if not text:
        return []

    # 用正则按标点切分（保留标点归属前一句）
    pattern = f"([{re.escape(_SENTENCE_ENDINGS)}])"
    parts = re.split(pattern, text)
    # re.split 会产出: ["内容", "。", "内容", "！", "内容"]
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

    # 对过长的再用逗号等软标点切
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
                # 如果加上这段会超长，先把之前的推出去
                if len(cur) + len(piece) > max_chars and cur.strip():
                    refined.append(cur.strip(_SOFT_BREAKS + " "))
                    cur = piece
                else:
                    cur += piece
        if cur.strip():
            refined.append(cur.strip(_SOFT_BREAKS + " "))

    # 合并过短的相邻片段
    merged: list[str] = []
    for piece in refined:
        if merged and len(merged[-1]) < min_chars:
            merged[-1] = merged[-1] + piece
        else:
            merged.append(piece)

    # 清理最终每一条末尾多余标点（SRT 中可留可不留，这里保留让阅读更自然）
    return [c.strip() for c in merged if c.strip()]


def build_srt_from_segments(audio_results: list[dict[str, Any]]) -> str:
    """
    生成逐句字幕 SRT：
      - 对每个 segment，按标点切成若干 cue
      - 在该 segment 的时间区间内，按字数比例给每个 cue 分配时长
      - 不同 segment 按播放顺序累计起始时间
    """
    lines: list[str] = []
    cursor = 0.0
    counter = 1

    for item in audio_results:
        # 优先用 subtitle_text（保留专业符号，如 α / θ），
        # 没有就回落 narration_text（TTS 专用的拼音版本）
        text_for_subtitle = (
            item.get("subtitle_text")
            or item.get("narration_text")
            or ""
        ).strip()
        duration = item.get("audio_duration_seconds")
        if not text_for_subtitle or not duration:
            continue

        seg_start = cursor
        seg_end = cursor + float(duration)
        seg_len = float(duration)

        cues = split_to_cues(text_for_subtitle)
        if not cues:
            cursor = seg_end
            continue

        # 按字符数比例分配时间
        total_chars = sum(len(c) for c in cues) or 1
        t = seg_start
        for idx, cue in enumerate(cues):
            share = len(cue) / total_chars
            cue_dur = seg_len * share
            cue_start = t
            # 最后一个 cue 直接对齐到 segment 结束，避免累计误差
            cue_end = seg_end if idx == len(cues) - 1 else t + cue_dur

            lines.append(str(counter))
            lines.append(f"{_format_timestamp(cue_start)} --> {_format_timestamp(cue_end)}")
            lines.append(cue)
            lines.append("")

            t = cue_end
            counter += 1

        cursor = seg_end

    return "\n".join(lines) + "\n"


def write_srt_file(audio_results: list[dict[str, Any]], output_path: str | Path) -> dict[str, Any]:
    """
    生成 SRT 并写入文件。
    返回 {path, bytes, total_duration_seconds, segment_count, cue_count}
    """
    srt_text = build_srt_from_segments(audio_results)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(srt_text, encoding="utf-8-sig")

    total = 0.0
    for item in audio_results:
        d = item.get("audio_duration_seconds") or 0.0
        total += float(d)

    # cue_count = SRT 中的条目数（空行数-ish）
    cue_count = sum(1 for line in srt_text.splitlines() if line.strip().isdigit())

    return {
        "path": str(output_path),
        "bytes": len(srt_text.encode("utf-8")),
        "total_duration_seconds": round(total, 3),
        "segment_count": sum(1 for i in audio_results if i.get("narration_text") and i.get("audio_duration_seconds")),
        "cue_count": cue_count,
    }
