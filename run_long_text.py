# -*- coding: utf-8 -*-
"""
调用 Day 2 的 /generate-video 用 Mack 的音色合成「决策树教学稿」长文本。
完成后把所有段落按序拼接为一个大 wav。
"""
from __future__ import annotations
import json
import sys
import time
import wave
from pathlib import Path
import urllib.request

SERVER = "http://127.0.0.1:8000/generate-video"
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "audio"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FINAL = OUT_DIR / "decision_tree_full.wav"

SEGMENTS = [
    # 开场
    ("开场·引子",
     "大家好！今天我们要聊的是机器学习里最接地气的模型之一——决策树。"),
    ("开场·生活比喻",
     "想象一下，你早上起床要决定今天穿什么衣服：先看窗外下雨没？如果下雨，再想气温多少度？如果低于10摄氏度，就穿羽绒服；如果15到20摄氏度，就穿夹克；如果不下雨，再看有没有太阳。这一连串如果……就……的判断，本质上就是一棵决策树。"),
    ("开场·核心价值",
     "决策树的魅力就在于：它像人类做决策一样思考，而且结果能画成一棵树，连非技术人员都能看懂。比如银行判断是否给客户放贷，用决策树可以清晰展示：如果年收入大于20万，且信用分大于700，就批准；否则拒绝。这种可解释性，是很多黑盒模型比不了的。"),
    ("开场·三层拆解",
     "今天我们会从三个层次拆解决策树：第一，直观理解，决策树是什么？怎么用？第二，核心算法，如何让计算机自动长出一棵好树？第三，实战避坑，怎么防止树过拟合？怎么用它解决实际问题？"),

    # 第一部分
    ("第一部分·什么是决策树",
     "决策树是一种树形结构的监督学习模型，主要用于分类和回归。它的核心是分而治之：通过对特征的递归判断，把数据不断分成更小的子集，直到子集里的样本足够纯净。"),
    ("第一部分·相亲例子",
     "举个生活例子：假设你要去相亲，朋友给你做了个是否建议见面的决策树。根节点第一个判断是：年龄小于等于30岁吗？如果是，再问收入有没有到15k。如果收入够，就建议见面；如果不够，再看学历是不是硕士及以上。如果年龄大于30岁，就直接看是否有房。这样一层层判断下去，就得到最终结论。"),
    ("第一部分·关键概念",
     "这棵树里有几个关键概念：根节点，是第一个判断条件，所有决策的起点；内部节点，是中间的判断条件；叶节点，是最终的决策结果，不再有分支；分支，是每个判断的是或否两条路径。"),
    ("第一部分·适用问题",
     "决策树能解决两类问题：分类任务，比如垃圾邮件检测、疾病诊断；回归任务，比如房价预测、销量预测。今天我们重点讲分类决策树，回归树思路类似，只是判断纯度的指标不同。"),

    # 第二部分
    ("第二部分·两个核心问题",
     "手动画相亲树很简单，但计算机怎么从一堆数据里自动生成最优决策树？关键在于两个问题：第一，选哪个特征做第一个判断，也就是根节点？第二，选完根节点后，下一个内部节点又选什么特征？这就需要引入纯度的概念：我们希望每次分裂之后，子节点的样本尽可能纯净。"),

    # 第三部分
    ("第三部分·过拟合",
     "假设我们训练一棵决策树，让它完美拟合训练数据，每个叶节点只有一个样本，训练准确率100%。但这样的树拿到新数据上，准确率可能暴跌——这就是过拟合。它记住了噪声，却没学到规律。比如用身份证号分裂的树，训练时能精准区分每个样本，但新样本的身份证号和训练集完全不同，自然无法预测。"),
    ("第三部分·预剪枝",
     "剪枝是通过去掉部分分支，降低模型复杂度，提高泛化能力。分为两种：预剪枝是在树生长过程中提前停止生长，比如限制树的深度最多5层、叶节点至少要10个样本才能分裂。它的优点是简单高效，缺点是可能欠拟合，过早停止错过好的分裂。"),
    ("第三部分·后剪枝",
     "后剪枝则是先让树完全生长，直到所有叶节点纯净，再从底向上判断：如果把某个内部节点换成叶节点，验证集准确率提升，就剪掉该节点的所有分支。后剪枝的泛化能力通常比预剪枝更好，但计算成本也更高。"),

    # 第四部分
    ("第四部分·鸢尾花介绍",
     "下面我们用一个实战例子来理解决策树。鸢尾花数据集是经典分类数据集，包含150个样本、4个特征：花萼长度、花萼宽度、花瓣长度、花瓣宽度，一共3个类别：山鸢尾、变色鸢尾、维吉尼亚鸢尾。"),
    ("第四部分·结果解读",
     "训练完成后，训练集准确率0.98，测试集准确率高达1.00。决策树生成的规则非常简洁：如果花瓣长度小于等于2.45厘米，就判为山鸢尾；否则再看花瓣宽度，小于等于1.75厘米是变色鸢尾，大于1.75厘米是维吉尼亚鸢尾。可以看到，树只用到了花瓣长度和花瓣宽度两个特征，就完成了三分类，非常漂亮。"),

    # 第五部分
    ("第五部分·优点",
     "决策树有三大优点：第一，可解释性强，规则清晰，可以可视化，特别适合医疗、金融这种需要说清楚原因的场景；第二，数据预处理简单，不需要归一化或标准化；第三，支持混合特征，可以同时处理离散特征和连续特征。"),
    ("第五部分·缺点",
     "缺点也很明显：第一，不稳定，数据微小变化可能导致树结构巨变；第二，容易过拟合，树太深时会记住噪声，需要剪枝；第三，不适合非线性边界的复杂关系，因为决策树本质是轴平行分割，对斜线边界效果较差。"),
    ("第五部分·应用场景",
     "典型应用场景包括：金融风控，银行用决策树判断是否批准贷款，规则透明、监管友好；医疗诊断，根据症状和检查指标辅助判断疾病类型；推荐系统，根据用户画像特征决定推荐策略。"),

    # 总结
    ("总结与展望",
     "今天我们学了决策树的核心逻辑：本质是通过特征递归分裂，把样本分到纯净子集；关键是用信息增益或基尼指数选择分裂特征，用剪枝防止过拟合；局限在于单棵树能力有限，但它是随机森林、GBDT等集成模型的基石。留一道思考题：如果让你用决策树判断明天是否下雨，你会选哪些特征呢？湿度、气压、风速、历史天气……都可以考虑。希望这节课能帮你理解决策树的前世今生，下次遇到分类问题，不妨先试试这个看得懂的模型。"),
]


def main() -> None:
    payload = {
        "request_id": f"dt_long_{int(time.time())}",
        "title": "决策树完整教学",
        "topic": "机器学习 / 决策树",
        "text_split_method": "cut0",  # 句子我已经切好了，让 SoVITS 不要再切
        "segments": [{"title": t, "narration": n} for t, n in SEGMENTS],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        SERVER, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    print(f"[*] sending {len(SEGMENTS)} segments to {SERVER} ...", flush=True)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60 * 30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"[*] server returned in {time.time()-t0:.1f}s, status={data.get('status')}", flush=True)

    errors = data.get("tts_errors", [])
    if errors:
        print(f"[!] {len(errors)} segment(s) failed:")
        for e in errors:
            print(f"   - seg {e.get('segment_index')}: {e.get('error')}")

    results = data.get("audio_results", [])
    if not results:
        print("[!] no audio produced, abort concat.", file=sys.stderr)
        sys.exit(1)

    # 按 segment_index 排序后拼接
    results.sort(key=lambda x: x["segment_index"])
    wavs = [Path(r["audio_path"]) for r in results]
    total_dur = sum(r.get("audio_duration_seconds") or 0 for r in results)
    print(f"[*] concatenating {len(wavs)} wavs, total duration ~= {total_dur:.1f}s", flush=True)

    # 用标准库 wave 拼接（所有 sovits 输出同采样率/位深/通道）
    with wave.open(str(wavs[0]), "rb") as w0:
        params = w0.getparams()
    with wave.open(str(FINAL), "wb") as out:
        out.setparams(params)
        for w in wavs:
            with wave.open(str(w), "rb") as src:
                out.writeframes(src.readframes(src.getnframes()))
    print(f"[OK] wrote {FINAL} ({FINAL.stat().st_size/1024/1024:.2f} MB)")

    # 写一份清单
    manifest = OUT_DIR / f"{payload['request_id']}_manifest.json"
    manifest.write_text(json.dumps({
        "title": payload["title"],
        "total_duration": total_dur,
        "final_wav": str(FINAL),
        "segments": [
            {"index": r["segment_index"], "title": r["segment_title"],
             "duration": r["audio_duration_seconds"], "file": r["audio_file"]}
            for r in results
        ]
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] manifest -> {manifest}")


if __name__ == "__main__":
    main()
