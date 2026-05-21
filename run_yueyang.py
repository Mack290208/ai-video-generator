# -*- coding: utf-8 -*-
"""用 Mack 的音色朗读《岳阳楼记》，语速 1.15x。"""
from __future__ import annotations
import json, time, wave, sys
from pathlib import Path
import urllib.request

SERVER = "http://127.0.0.1:8000/generate-video"
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "audio"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FINAL = OUT_DIR / "yueyang_full.wav"

SEGMENTS = [
    ("第一段·缘起",
     "庆历四年春，滕子京谪守巴陵郡。越明年，政通人和，百废具兴，乃重修岳阳楼，增其旧制，刻唐贤今人诗赋于其上，属予作文以记之。"),
    ("第二段·巴陵胜状",
     "予观夫巴陵胜状，在洞庭一湖。衔远山，吞长江，浩浩汤汤，横无际涯；朝晖夕阴，气象万千。此则岳阳楼之大观也，前人之述备矣。然则北通巫峡，南极潇湘，迁客骚人，多会于此，览物之情，得无异乎？"),
    ("第三段·淫雨霏霏",
     "若夫淫雨霏霏，连月不开，阴风怒号，浊浪排空；日星隐曜，山岳潜形；商旅不行，樯倾楫摧；薄暮冥冥，虎啸猿啼。登斯楼也，则有去国怀乡，忧谗畏讥，满目萧然，感极而悲者矣。"),
    ("第四段·春和景明",
     "至若春和景明，波澜不惊，上下天光，一碧万顷；沙鸥翔集，锦鳞游泳；岸芷汀兰，郁郁青青。而或长烟一空，皓月千里，浮光跃金，静影沉璧，渔歌互答，此乐何极！登斯楼也，则有心旷神怡，宠辱偕忘，把酒临风，其喜洋洋者矣。"),
    ("第五段·古仁人之心",
     "嗟夫！予尝求古仁人之心，或异二者之为，何哉？不以物喜，不以己悲；居庙堂之高则忧其民，处江湖之远则忧其君。是进亦忧，退亦忧。然则何时而乐耶？其必曰：先天下之忧而忧，后天下之乐而乐乎！噫！微斯人，吾谁与归？"),
    ("落款",
     "时六年九月十五日。"),
]

def main():
    payload = {
        "request_id": f"yueyang_{int(time.time())}",
        "title": "岳阳楼记",
        "topic": "古文朗读",
        "text_split_method": "cut5",
        "speed": 1.15,  # 全局稍快
        "segments": [{"title": t, "narration": n} for t, n in SEGMENTS],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(SERVER, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    print(f"[*] sending {len(SEGMENTS)} segments @ 1.15x ...", flush=True)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60*20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"[*] server returned in {time.time()-t0:.1f}s, status={data.get('status')}", flush=True)

    errs = data.get("tts_errors", [])
    for e in errs:
        print(f"   [!] seg {e['segment_index']}: {e['error']}")

    results = sorted(data.get("audio_results", []), key=lambda x: x["segment_index"])
    if not results:
        print("[!] no audio produced", file=sys.stderr); sys.exit(1)

    total = sum(r.get("audio_duration_seconds") or 0 for r in results)
    print(f"[*] concatenating {len(results)} wavs, total ~= {total:.1f}s")

    with wave.open(results[0]["audio_path"], "rb") as w0:
        params = w0.getparams()
    with wave.open(str(FINAL), "wb") as out:
        out.setparams(params)
        for r in results:
            with wave.open(r["audio_path"], "rb") as src:
                out.writeframes(src.readframes(src.getnframes()))
    print(f"[OK] wrote {FINAL} ({FINAL.stat().st_size/1024/1024:.2f} MB)")

if __name__ == "__main__":
    main()
