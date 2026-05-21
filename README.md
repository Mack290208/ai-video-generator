# AI 助教视频自动生成系统

基于 LLM + Manim + GPT-SoVITS 的 AI 课程视频自动生成 pipeline。

## 功能

- 📝 LLM 自动生成课程脚本（分段式：intro / 核心内容 / outro）
- 🎬 Manim 数学动画自动生成
- 🎙️ GPT-SoVITS 语音合成（TTS）
- 📝 WhisperX 字幕对齐
- 🎥 FFmpeg 最终合成（画面 + 旁白 + 字幕）

## 技术栈

- **动画引擎:** Manim 0.20.1
- **TTS:** GPT-SoVITS（神里绫华 e10 音色权重）
- **字幕:** WhisperX
- **后端:** FastAPI
- **LLM:** OpenAI-compatible API

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API key

# 运行完整 pipeline
python run_full_pipeline_v2.py
```

## 项目结构

```
├── components/          # 核心组件（TTS、Manim、字幕等）
├── layouts/             # 布局模板
├── manim_scenes/        # Manim 场景文件
├── services/            # 服务层
├── templates/           # 模板工厂
├── server.py            # FastAPI 服务端
├── run_full_pipeline_v2.py  # 完整 pipeline 运行脚本
└── requirements.txt     # Python 依赖
```

## 里程碑

- ✅ 端到端 pipeline 跑通（intro + 核心内容 + outro）
- ✅ 模板工厂 v2（intro_v2 / curve_descent / lr_comparison / bullet_summary）
- ✅ 第一次完全由 LLM 决策生成视频（决策树，88s 成片）
- 🔄 WhisperX 字幕对齐集成（进行中）

## License

MIT
