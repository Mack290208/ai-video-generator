# -*- coding: utf-8 -*-
"""用神里绫华 v4 模型朗读岳阳楼记。"""
from __future__ import annotations
import json, time, wave, sys, urllib.request, urllib.parse
from pathlib import Path

SOVITS_BASE = "http://127.0.0.1:9880"
SERVER = "http://127.0.0.1:8000/generate-video"
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "audio"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FINAL = OUT_DIR / "yueyang_ayaka.wav"

MODEL_DIR = Path(r"C:\Users\hymac\Desktop\神里绫华_ZH\v4\神里绫华_ZH")
GPT_CKPT = MODEL_DIR / "神里绫华_ZH-e10.ckpt"
SOVITS_PTH = MODEL_DIR / "神里绫华_ZH_e10_s670_l32.pth"
REF_WAV = MODEL_DIR / "reference_audios" / "中文" / "emotions" / "【默认】看来，你们能理解我的心情了，既然这样，不知能否再考虑一下….wav"
PROMPT_TEXT = "看来，你们能理解我的心情了，既然这样，不知能否再考虑一下"

SEGMENTS = [
    ("缘起", "庆历四年春，滕子京谪守巴陵郡。越明年，政通人和，百废具兴，乃重修岳阳楼，增其旧制，刻唐贤今人诗赋于其上，属予作文以记之。"),
    ("巴陵胜状", "予观夫巴陵胜状，在洞庭一湖。衔远山，吞长江，浩浩汤汤，横无际涯；朝晖夕阴，气象万千。此则岳阳楼之大观也，前人之述备矣。然则北通巫峡，南极潇湘，迁客骚人，多会于此，览物之情，得无异乎？"),
    ("淫雨霏霏", "若夫淫雨霏霏，连月不开，阴风怒号，浊浪排空；日星隐曜，山岳潜形；商旅不行，樯倾楫摧；薄暮冥冥，虎啸猿啼。登斯楼也，则有去国怀乡，忧谗畏讥，满目萧然，感极而悲者矣。"),
    ("春和景明", "至若春和景明，波澜不惊，上下天光，一碧万顷；沙鸥翔集，锦鳞游泳；岸芷汀兰，郁郁青青。而或长烟一空，皓月千里，浮光跃金，静影沉璧，渔歌互答，此乐何极！登斯楼也，则有心旷神怡，宠辱偕忘，把酒临风，其喜洋洋者矣。"),
    ("古仁人之心", "嗟夫！予尝求古仁人之心，或异二者之为，何哉？不以物喜，不以己悲；居庙堂之高则忧其民，处江湖之远则忧其君。是进亦忧，退亦忧。然则何时而乐耶？其必曰：先天下之忧而忧，后天下之乐而乐乎！噫！微斯人，吾谁与归？"),
    ("落款", "时六年九月十五日。"),
]

def get(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.status, r.read().decode("utf-8", errors="replace")

def main():
    # ---- 1. 热切换模型 ----
    print("[1/3] switching GPT + SoVITS weights to 神里绫华 ...", flush=True)
    s1, b1 = get(f"{SOVITS_BASE}/set_gpt_weights?weights_path={urllib.parse.quote(str(GPT_CKPT))}")
    print(f"  /set_gpt_weights -> {s1} {b1[:200]}")
    s2, b2 = get(f"{SOVITS_BASE}/set_sovits_weights?weights_path={urllib.parse.quote(str(SOVITS_PTH))}")
    print(f"  /set_sovits_weights -> {s2} {b2[:200]}")
    if s1 != 200 or s2 != 200:
        print("[!] weight switch failed, abort.", file=sys.stderr)
        sys.exit(1)

    # ---- 2. 合成 ----
    payload = {
        "request_id": f"ayaka_yy_{int(time.time())}",
        "title": "岳阳楼记(神里绫华)",
        "topic": "古文朗读",
        "text_split_method": "cut1",   # 按凑四句切，比 cut5 更稳
        "speed": 1.15,
        "ref_audio_path": str(REF_WAV),
        "prompt_text": PROMPT_TEXT,
        "segments": [{"title": t, "narration": n} for t, n in SEGMENTS],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(SERVER, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    print(f"[2/3] synthesizing {len(SEGMENTS)} segments @ 1.15x cut1 ...", flush=True)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60*30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"  server returned in {time.time()-t0:.1f}s, status={data.get('status')}")
    for e in data.get("tts_errors", []):
        print(f"   [!] seg {e['segment_index']}: {e['error']}")

    results = sorted(data.get("audio_results", []), key=lambda x: x["segment_index"])
    if not results:
        sys.exit(1)

    # ---- 3. 拼接 ----
    print("[3/3] concatenating ...", flush=True)
    for r in results:
        print(f"  seg {r['segment_index']:>2}  {r['audio_duration_seconds']:>6}s  {r['segment_title']}")
    with wave.open(results[0]["audio_path"], "rb") as w0:
        params = w0.getparams()
    with wave.open(str(FINAL), "wb") as out:
        out.setparams(params)
        for r in results:
            with wave.open(r["audio_path"], "rb") as src:
                out.writeframes(src.readframes(src.getnframes()))
    total = sum(r.get("audio_duration_seconds") or 0 for r in results)
    print(f"[OK] {FINAL}  ({FINAL.stat().st_size/1024/1024:.2f} MB, {total:.1f}s)")

if __name__ == "__main__":
    main()
