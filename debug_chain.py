"""快速检查合成链路的中间产物。"""
import tempfile, shutil
from pathlib import Path
from services.composition_service import _pad_or_trim_video, _concat_videos, probe_duration
from services.video_service import find_ffmpeg

ffm = find_ffmpeg()

SEGS = [
    ("intro",      r"C:\Users\hymac\Desktop\临时python骨架穿透文件\outputs\manim\videos\intro\720p30\smoke_pipeline_seg_01_intro.mp4", 7.20),
    ("gd",         r"C:\Users\hymac\Desktop\临时python骨架穿透文件\outputs\manim\videos\gradient_descent\720p30\smoke_pipeline_seg_02_gradient_descent.mp4", 23.12),
    ("outro",      r"C:\Users\hymac\Desktop\临时python骨架穿透文件\outputs\manim\videos\outro\720p30\smoke_pipeline_seg_03_outro.mp4", 19.11),
]

debug_dir = Path(r"C:\Users\hymac\Desktop\临时python骨架穿透文件\outputs\debug_chain")
debug_dir.mkdir(parents=True, exist_ok=True)

print("=== 原始 ===")
for name, p, _ in SEGS:
    print(f"  {name}: {probe_duration(p):.2f}s  size={Path(p).stat().st_size}")

print("\n=== 对齐后 ===")
aligned = []
for name, p, target in SEGS:
    out = debug_dir / f"aligned_{name}.mp4"
    _pad_or_trim_video(Path(p), target, out, ffm, fps=30)
    d = probe_duration(out)
    print(f"  {name}: {d:.2f}s  size={out.stat().st_size}  target={target}")
    aligned.append(out)

print("\n=== concat 后 ===")
concat_out = debug_dir / "concat.mp4"
_concat_videos(aligned, concat_out, ffm)
print(f"  concat: {probe_duration(concat_out):.2f}s  size={concat_out.stat().st_size}")
