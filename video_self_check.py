# -*- coding: utf-8 -*-
"""
video_self_check.py — 教学视频自检工具（PaddleOCR 版）
======================================================
用 PaddleOCR 精确识别每帧中的文字位置和内容，检测：

  1. 文字重叠 — 不同文字块的 bounding box 有实质交叉
  2. 文字越界 — 文字区域超出安全画面边界
  3. 字幕遮挡 — Manim 内容文字侵入字幕区，或与 SRT 字幕距离太近

与纯 CV 版的区别：
  - OCR 精确识别每个字的位置和内容，不再是模糊的大框
  - 能区分"标签在框内"（正常）和"文字互相穿插"（异常）
  - 能检测 Manim 内容文字和 SRT 字幕的距离

用法：
    python video_self_check.py video.mp4              # 检查单个
    python video_self_check.py --all                   # 检查桌面所有西瓜书视频
    python video_self_check.py --all --html            # 生成 HTML 报告
    python video_self_check.py v1.mp4 v2.mp4           # 检查多个
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

# ============================================================
# 画面常量
# ============================================================
VIDEO_W = 1280
VIDEO_H = 720

# 字幕区上边界（y 像素）— y > 此值的区域留给 SRT 字幕
# Manim SUBTITLE_TOP_Y = -2.8 → y_pixel = 720*(1-1.2/8) ≈ 612
SUBTITLE_TOP_PX = int(VIDEO_H * (1 - (-2.8 + 4.0) / 8.0))  # ≈ 612

# 安全边距（像素）
EDGE_MARGIN_PX = 15

# SRT 字幕忽略区 — 画面底部此区域内的文字视为 SRT 字幕
SRT_SUBTITLE_IGNORE_Y = 600

# 两个文字块重叠的最小交集面积（像素²）
# 低于此值的视为紧贴但不重叠
OVERLAP_MIN_AREA = 500

# 文字块包含判定阈值 — 小框面积的 N% 在大框内则视为"标签在框中"
CONTAINMENT_THRESHOLD = 0.6


# ============================================================
# 数据结构
# ============================================================
@dataclass
class OCRTextBox:
    """OCR 检测到的文字区域。"""
    text: str         # 识别出的文字内容
    x: int            # 左上角 x
    y: int            # 左上角 y
    w: int            # 宽
    h: int            # 高
    confidence: float # 识别置信度
    frame_idx: int = 0
    timestamp: float = 0.0

    @property
    def x2(self): return self.x + self.w
    @property
    def y2(self): return self.y + self.h
    @property
    def area(self): return self.w * self.h
    @property
    def cx(self): return self.x + self.w / 2
    @property
    def cy(self): return self.y + self.h / 2


@dataclass
class Issue:
    kind: str        # "overlap" | "out_of_bounds" | "subtitle_block"
    severity: str    # "error" | "warning"
    timestamp: float
    frame_idx: int
    description: str
    boxes: List[OCRTextBox] = field(default_factory=list)
    snapshot_path: Optional[str] = None


@dataclass
class CheckResult:
    video_path: str
    duration: float
    frames_checked: int
    issues: List[Issue] = field(default_factory=list)

    @property
    def error_count(self): return sum(1 for i in self.issues if i.severity == "error")
    @property
    def warning_count(self): return sum(1 for i in self.issues if i.severity == "warning")
    @property
    def passed(self): return self.error_count == 0


# ============================================================
# PaddleOCR 初始化（延迟加载）
# ============================================================
_ocr_instance = None

def get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        print("  [OCR] 初始化 PaddleOCR...")
        import os
        os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
        import torch  # 必须在 paddle 之前导入，否则 DLL 冲突
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang='ch')
    return _ocr_instance


def ocr_detect_text(frame: np.ndarray, frame_idx: int = 0, timestamp: float = 0.0) -> List[OCRTextBox]:
    """用 PaddleOCR 检测单帧中的所有文字。"""
    ocr = get_ocr()
    results = ocr.ocr(frame, cls=True)
    
    boxes = []
    if not results or not results[0]:
        return boxes
    
    for line in results[0]:
        # line = [coordinates, (text, confidence)]
        coords = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        text = line[1][0]
        confidence = line[1][1]
        
        # 计算 bounding box
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        x_min, x_max = int(min(xs)), int(max(xs))
        y_min, y_max = int(min(ys)), int(max(ys))
        
        boxes.append(OCRTextBox(
            text=text,
            x=x_min, y=y_min,
            w=x_max - x_min, h=y_max - y_min,
            confidence=confidence,
            frame_idx=frame_idx,
            timestamp=timestamp,
        ))
    
    return boxes


# ============================================================
# 检测逻辑
# ============================================================

def check_overlaps(boxes: List[OCRTextBox]) -> List[Tuple[OCRTextBox, OCRTextBox, int]]:
    """检测文字块之间的重叠。返回 (box1, box2, overlap_area)。"""
    overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            b1, b2 = boxes[i], boxes[j]
            
            # 跳过 SRT 字幕区域的文字
            if b1.y > SRT_SUBTITLE_IGNORE_Y and b2.y > SRT_SUBTITLE_IGNORE_Y:
                continue
            
            # 计算交集
            ix = max(0, min(b1.x2, b2.x2) - max(b1.x, b2.x))
            iy = max(0, min(b1.y2, b2.y2) - max(b1.y, b2.y))
            inter_area = ix * iy
            
            if inter_area < OVERLAP_MIN_AREA:
                continue
            
            # 排除"小框大部分在大框内"（标签在框/背景内的正常布局）
            smaller_area = min(b1.area, b2.area)
            if smaller_area > 0 and inter_area >= smaller_area * CONTAINMENT_THRESHOLD:
                continue
            
            overlaps.append((b1, b2, inter_area))
    
    return overlaps


def check_out_of_bounds(boxes: List[OCRTextBox]) -> List[OCRTextBox]:
    """检测文字是否超出安全区域。"""
    oob = []
    for box in boxes:
        if box.y > SRT_SUBTITLE_IGNORE_Y:
            continue  # 忽略 SRT 字幕
        edges = []
        if box.x < EDGE_MARGIN_PX: edges.append("左")
        if box.x2 > VIDEO_W - EDGE_MARGIN_PX: edges.append("右")
        if box.y < EDGE_MARGIN_PX: edges.append("上")
        if edges:
            oob.append(box)
    return oob


def check_subtitle_block(boxes: List[OCRTextBox]) -> List[Tuple[OCRTextBox, float]]:
    """检测 Manim 内容文字是否侵入字幕区。

    返回 (box, intrusion_px) 列表。
    OCR 能精确识别文字，所以只报告真正低于字幕线的内容文字，
    排除 SRT 字幕本身。
    """
    blocked = []
    for box in boxes:
        # 跳过 SRT 字幕本身（在画面最底部）
        if box.y > SRT_SUBTITLE_IGNORE_Y:
            continue
        # 检查文字底部是否超过字幕区上界
        if box.y2 > SUBTITLE_TOP_PX:
            intrusion = box.y2 - SUBTITLE_TOP_PX
            # 要求实质性入侵（>5px），排除 OCR 微小误差
            if intrusion > 5:
                blocked.append((box, intrusion))
    return blocked


def analyze_frame(frame: np.ndarray, frame_idx: int, timestamp: float) -> Tuple[List[Issue], List[OCRTextBox]]:
    """分析单帧，返回 (issues, all_boxes)。"""
    issues = []
    boxes = ocr_detect_text(frame, frame_idx, timestamp)
    
    if not boxes:
        return issues, boxes
    
    # 1. 重叠检测
    for b1, b2, area in check_overlaps(boxes):
        issues.append(Issue(
            kind="overlap",
            severity="error" if area > 2000 else "warning",
            timestamp=timestamp,
            frame_idx=frame_idx,
            description=(
                f'文字重叠 ({area}px²): '
                f'"{b1.text}" [{b1.x},{b1.y} {b1.w}x{b1.h}] ∩ '
                f'"{b2.text}" [{b2.x},{b2.y} {b2.w}x{b2.h}]'
            ),
            boxes=[b1, b2],
        ))
    
    # 2. 越界检测
    for box in check_out_of_bounds(boxes):
        issues.append(Issue(
            kind="out_of_bounds",
            severity="warning",
            timestamp=timestamp,
            frame_idx=frame_idx,
            description=f'文字越界: "{box.text}" [{box.x},{box.y} {box.w}x{box.h}]',
            boxes=[box],
        ))
    
    # 3. 字幕遮挡检测
    for box, intrusion in check_subtitle_block(boxes):
        issues.append(Issue(
            kind="subtitle_block",
            severity="error" if intrusion > 30 else "warning",
            timestamp=timestamp,
            frame_idx=frame_idx,
            description=(
                f'文字侵入字幕区 {intrusion:.0f}px: '
                f'"{box.text}" [{box.x},{box.y} {box.w}x{box.h}]'
            ),
            boxes=[box],
        ))
    
    return issues, boxes


def draw_debug_frame(frame: np.ndarray, boxes: List[OCRTextBox], issues: List[Issue]) -> np.ndarray:
    """在帧上绘制检测结果。"""
    debug = frame.copy()
    
    # 字幕区边界
    cv2.line(debug, (0, SUBTITLE_TOP_PX), (VIDEO_W, SUBTITLE_TOP_PX), (0, 0, 200), 2)
    cv2.putText(debug, "SUBTITLE ZONE", (10, SUBTITLE_TOP_PX + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 200), 1)
    
    # 安全边距
    cv2.rectangle(debug, (EDGE_MARGIN_PX, EDGE_MARGIN_PX),
                  (VIDEO_W - EDGE_MARGIN_PX, VIDEO_H - EDGE_MARGIN_PX),
                  (128, 128, 128), 1)
    
    # 问题框集合
    issue_box_set = set()
    for issue in issues:
        for box in issue.boxes:
            issue_box_set.add((box.x, box.y, box.w, box.h))
    
    # 画所有文字框
    for box in boxes:
        is_issue = (box.x, box.y, box.w, box.h) in issue_box_set
        color = (0, 0, 255) if is_issue else (0, 200, 0)
        cv2.rectangle(debug, (box.x, box.y), (box.x2, box.y2), color, 2)
        # 标注文字内容
        label = box.text[:15]
        cv2.putText(debug, label, (box.x, box.y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
    
    # 问题摘要
    y_off = 25
    for issue in issues:
        color = (0, 0, 255) if issue.severity == "error" else (0, 165, 255)
        cv2.putText(debug, f"[{issue.kind}] {issue.description[:70]}", (10, y_off),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        y_off += 18
    
    return debug


# ============================================================
# 视频检查
# ============================================================

def check_video(
    video_path: str | Path,
    sample_interval: float = 2.0,
    save_snapshots: bool = False,
    snapshot_dir: Optional[str | Path] = None,
) -> CheckResult:
    """检查单个视频。"""
    video_path = Path(video_path)
    cap = cv2.VideoCapture(str(video_path))
    
    if not cap.isOpened():
        result = CheckResult(video_path=str(video_path), duration=0, frames_checked=0)
        result.issues.append(Issue(kind="error", severity="error", timestamp=0, frame_idx=0,
                                    description=f"无法打开视频: {video_path}"))
        return result
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    sample_step = max(1, int(fps * sample_interval))
    sample_positions = list(range(0, total_frames, sample_step))
    
    if save_snapshots:
        snapshot_dir = Path(snapshot_dir) if snapshot_dir else video_path.parent / "self_check_snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    result = CheckResult(video_path=str(video_path), duration=duration, frames_checked=0)
    
    for pos in sample_positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ret, frame = cap.read()
        if not ret:
            continue
        
        timestamp = pos / fps
        result.frames_checked += 1
        
        h, w = frame.shape[:2]
        if w != VIDEO_W or h != VIDEO_H:
            frame = cv2.resize(frame, (VIDEO_W, VIDEO_H))
        
        issues, boxes = analyze_frame(frame, pos, timestamp)
        
        if issues:
            result.issues.extend(issues)
            if save_snapshots and snapshot_dir:
                debug = draw_debug_frame(frame, boxes, issues)
                snap_name = f"{video_path.stem}_f{pos:06d}_{timestamp:.1f}s.jpg"
                snap_path = Path(snapshot_dir) / snap_name
                cv2.imwrite(str(snap_path), debug)
                for issue in issues:
                    if not issue.snapshot_path:
                        issue.snapshot_path = str(snap_path)
    
    cap.release()
    return result


def check_all_desktop_videos(sample_interval: float = 2.0) -> List[CheckResult]:
    """检查桌面上所有西瓜书视频。"""
    desktop = Path.home() / "Desktop"
    videos = sorted(desktop.glob("西瓜书_*.mp4"))
    
    if not videos:
        # 也检查 视频未检测 文件夹
        folder = desktop / "视频未检测"
        if folder.exists():
            videos = sorted(folder.glob("*.mp4"))
    
    if not videos:
        print("没有找到视频文件")
        return []
    
    print(f"找到 {len(videos)} 个视频，开始检查...\n")
    results = []
    for i, vpath in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] {vpath.name} ...", end=" ", flush=True)
        t0 = time.time()
        r = check_video(vpath, sample_interval=sample_interval, save_snapshots=True)
        elapsed = time.time() - t0
        status = "✓ PASS" if r.passed else "✗ FAIL"
        issue_str = f" ({r.error_count} err, {r.warning_count} warn)" if r.issues else ""
        print(f"{status}{issue_str} [{elapsed:.1f}s]")
        results.append(r)
    return results


def _deduplicate_issues(issues: List[Issue]) -> List[Issue]:
    """去重：同一种类 + 同一文字内容的问题只报一次。"""
    if not issues:
        return issues
    groups: dict = {}
    for issue in issues:
        # 用文字内容做 key（比坐标更稳定）
        key = (issue.kind, issue.description[:40])
        groups.setdefault(key, []).append(issue)
    
    deduped = []
    for key, group in groups.items():
        first = group[0]
        if len(group) == 1:
            deduped.append(first)
        else:
            t_start = group[0].timestamp
            t_end = group[-1].timestamp
            deduped.append(Issue(
                kind=first.kind, severity=first.severity,
                timestamp=t_start, frame_idx=first.frame_idx,
                description=(
                    f"{first.description} | "
                    f"在 {t_start:.0f}s~{t_end:.0f}s 出现 {len(group)} 次"
                ),
                boxes=first.boxes, snapshot_path=first.snapshot_path,
            ))
    return deduped


def print_report(results: List[CheckResult], compact: bool = True):
    """打印报告。"""
    print()
    print("=" * 70)
    print("  视频自检报告 (PaddleOCR)")
    print("=" * 70)
    
    total_errors = total_warnings = passed = 0
    for r in results:
        total_errors += r.error_count
        total_warnings += r.warning_count
        if r.passed:
            passed += 1
        
        status = "✓ PASS" if r.passed else "✗ FAIL"
        name = Path(r.video_path).name
        print(f"\n  {status}  {name}")
        print(f"         时长: {r.duration:.1f}s | 检查帧数: {r.frames_checked}")
        
        if r.issues:
            display = _deduplicate_issues(r.issues) if compact else r.issues
            for issue in display:
                icon = "❌" if issue.severity == "error" else "⚠️"
                print(f"         {icon} [{issue.kind}] @{issue.timestamp:.0f}s: {issue.description[:120]}")
    
    print()
    print("-" * 70)
    print(f"  总计: {len(results)} 个视频 | {passed} 通过 | {len(results)-passed} 有问题")
    print(f"  问题: {total_errors} 错误 | {total_warnings} 警告")
    print("-" * 70)
    
    if total_errors > 0:
        print("\n  ⚠ 有错误的视频需要修复！")
    elif total_warnings > 0:
        print("\n  ℹ 有警告建议人工确认。")
    else:
        print("\n  🎉 所有视频检查通过！")


# ============================================================
# Pipeline 集成
# ============================================================

def quick_check(video_path: str | Path, verbose: bool = True) -> bool:
    """快速检查单个视频，返回 True = 通过。"""
    result = check_video(video_path, sample_interval=2.0, save_snapshots=True)
    if verbose:
        issues = _deduplicate_issues(result.issues)
        if not issues:
            print(f"    ✓ 视频自检通过: {Path(video_path).name}")
        else:
            for issue in issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                print(f"    {icon} [{issue.kind}] @{issue.timestamp:.0f}s: {issue.description[:100]}")
            if not result.passed:
                print(f"    ✗ 视频自检未通过 ({result.error_count} errors)")
    return result.passed


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="教学视频自检工具 (PaddleOCR) — 检测文字重叠/越界/字幕遮挡",
    )
    parser.add_argument("video", nargs="*", help="检查视频文件（支持多个）")
    parser.add_argument("--all", action="store_true", help="检查所有西瓜书视频")
    parser.add_argument("--dir", type=str, help="检查指定目录下所有 .mp4")
    parser.add_argument("--interval", type=float, default=2.0, help="抽帧间隔秒数（默认2.0）")
    parser.add_argument("--html", action="store_true", help="生成 HTML 报告")
    parser.add_argument("--snapshots", action="store_true", help="保存问题帧截图")
    parser.add_argument("--output", type=str, help="HTML 报告输出路径")
    args = parser.parse_args()
    
    if not args.video and not args.all and not args.dir:
        parser.print_help()
        sys.exit(1)
    
    results = []
    if args.all:
        results = check_all_desktop_videos(args.interval)
    elif args.dir:
        videos = sorted(Path(args.dir).glob("*.mp4"))
        for v in videos:
            results.append(check_video(v, args.interval, args.snapshots))
    elif args.video:
        for v in args.video:
            results.append(check_video(v, args.interval, args.snapshots))
    
    if results:
        print_report(results)


if __name__ == "__main__":
    main()
