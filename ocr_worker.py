# -*- coding: utf-8 -*-
"""
ocr_worker.py — OCR 子进程 worker
在独立进程中运行 PaddleOCR，避免和 PyTorch 冲突。
通过 stdin/stdout JSON 通信。
"""
import sys, json, cv2, numpy as np

# Disable oneDNN
import os
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_enable_pir_api'] = '0'

import paddle
paddle.set_flags({'FLAGS_use_mkldnn': False})

from paddleocr import PaddleOCR
ocr = PaddleOCR(lang='ch')

# Signal ready
print("READY", flush=True)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    if line == "QUIT":
        break
    
    # Read frame path
    frame_path = line
    frame = cv2.imread(frame_path)
    if frame is None:
        print(json.dumps({"error": "cannot read frame"}), flush=True)
        continue
    
    results = ocr.predict(frame)
    boxes = []
    for result in results:
        # PaddleOCR v3+ returns structured results
        if hasattr(result, 'rec_texts') and hasattr(result, 'dt_polys'):
            texts = result.rec_texts
            polys = result.dt_polys
            scores = result.rec_scores if hasattr(result, 'rec_scores') else [1.0] * len(texts)
            for poly, text, score in zip(polys, texts, scores):
                xs = [int(p[0]) for p in poly]
                ys = [int(p[1]) for p in poly]
                boxes.append({
                    "text": text,
                    "x": min(xs), "y": min(ys),
                    "w": max(xs) - min(xs), "h": max(ys) - min(ys),
                    "confidence": float(score)
                })
        elif isinstance(result, dict):
            # Old format fallback
            pass
    
    print(json.dumps({"boxes": boxes}, ensure_ascii=False), flush=True)
