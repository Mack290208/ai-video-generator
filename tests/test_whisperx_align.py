"""
test_whisperx_align.py
测试 WhisperX 强制对齐功能
"""
import os
import sys
from pathlib import Path

# 设置 HuggingFace 镜像（中国网络）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from services.whisper_align_service import WhisperXAligner, WordToken


def test_whisperx_basic():
    """测试 WhisperXAligner 能否正常加载和对齐。"""
    print("=" * 50)
    print("测试 WhisperXAligner 基本功能")
    print("=" * 50)

    # 1. 测试模型加载
    print("\n[1/3] 创建 WhisperXAligner...")
    aligner = WhisperXAligner(language="zh", device="cpu")
    print(f"    模型名称: {aligner.model_name}")

    # 2. 找一个测试音频文件
    audio_dir = BASE_DIR / "outputs" / "audio"
    test_wav = None
    if audio_dir.exists():
        wav_files = list(audio_dir.glob("*.wav"))
        if wav_files:
            test_wav = wav_files[0]
            print(f"\n[2/3] 找到测试音频: {test_wav.name}")

    if not test_wav or not test_wav.exists():
        print("\n[2/3] 没有找到测试音频，跳过对齐测试")
        print("    提示: 先运行一次 run_from_storyboard.py 生成音频文件")
        return True

    # 3. 测试对齐
    print("\n[3/3] 测试强制对齐...")
    test_text = "这是一个测试句子，用来验证 WhisperX 对齐功能。"

    try:
        words = aligner.align_text_to_audio(test_wav, test_text)
        print(f"    对齐成功！返回 {len(words)} 个字符/词")

        # 显示前10个字符的时间戳
        for i, w in enumerate(words[:10]):
            print(f"        [{i}] '{w.text}'  {w.start:.3f}s ~ {w.end:.3f}s")

        if len(words) > 10:
            print(f"        ... 还有 {len(words) - 10} 个字符")

        return True

    except Exception as e:
        print(f"    对齐失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_import():
    """测试 WhisperX 能否正常导入。"""
    print("\n" + "=" * 50)
    print("测试 WhisperX 导入")
    print("=" * 50)

    try:
        import whisperx
        print("    [OK] whisperx 导入成功")

        # 检查关键函数
        assert hasattr(whisperx, 'load_align_model'), "缺少 load_align_model"
        assert hasattr(whisperx, 'align'), "缺少 align"
        assert hasattr(whisperx, 'load_audio'), "缺少 load_audio"
        print("    [OK] 关键函数存在")

        return True
    except Exception as e:
        print(f"    [FAIL] 导入失败: {e}")
        return False


if __name__ == "__main__":
    print("WhisperX 集成测试脚本\n")

    success = True
    success = test_import() and success
    success = test_whisperx_basic() and success

    print("\n" + "=" * 50)
    if success:
        print("[PASS] 所有测试通过！")
    else:
        print("[FAIL] 部分测试失败")
    print("=" * 50)

    sys.exit(0 if success else 1)
