# AI 助教视频工坊 🎬

> 一键生成专业教学视频，支持 AI 智能规划、多种动画模板、语音合成

## ✨ 功能特点

### 🎯 核心功能
- **一键生成**：输入主题，AI 自动生成完整教学视频
- **智能规划**：LLM 自动选择模板、生成演讲稿
- **专业动画**：16+ 个 Manim 动画模板，覆盖机器学习核心概念
- **语音合成**：GPT-SoVITS 神里绫华音色
- **精准字幕**：WhisperX 语音对齐，字幕同步

### 🤖 AI 功能
- **方案A**：LLM 自动生成 storyboard（推荐）
- **方案B**：丰富的 Manim 模板库
- **方案C**：LLM 直接生成 Manim 代码（Fallback）

### 🎨 模板库
| 模板 | 说明 | 适用场景 |
|------|------|----------|
| `intro_v2` | 片头动画 | 视频开头 |
| `outro` | 片尾动画 | 视频结尾 |
| `bullet_summary` | 要点总结 | 知识点回顾 |
| `concept_compare` | 概念对比 | A vs B 对比 |
| `curve_descent` | 曲线下降 | 优化过程 |
| `data_flow` | 数据流图 | 流程展示 |
| `formula_evolve` | 公式推导 | 数学推导 |
| `lr_comparison` | 学习率对比 | 参数对比 |
| `scatter_classify` | 散点分类 | 分类可视化 |
| `neural_network` | 神经网络 | 网络结构 |
| `decision_tree` | 决策树 | 树分裂过程 |
| `confusion_matrix` | 混淆矩阵 | 评估指标 |
| `knn_demo` | KNN 演示 | K近邻算法 |
| `overfitting` | 过拟合 | 训练/验证曲线 |

## 🚀 快速开始

### 1. 环境要求
- Python 3.10+
- FFmpeg
- MiKTeX（用于数学公式渲染）

### 2. 安装依赖
```bash
pip install -r requirements.txt
cd .venv_manim
pip install manim
```

### 3. 配置 LLM API

编辑 `.env` 文件：

```env
# 方案1: DeepSeek（推荐）
DEEPSEEK_API_KEY=your_api_key_here

# 方案2: MiMo（小米大模型）
MIMO_API_KEY=your_api_key_here
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2-pro

# 方案3: OpenAI 兼容 API
OPENAI_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-ai/DeepSeek-V3
```

### 4. 启动服务
```bash
# 一键启动（推荐）
python launcher.py

# 或手动启动
python server.py
```

### 5. 访问界面
打开浏览器访问：http://localhost:8000/ui

## 📖 使用指南

### 方式1：AI 自动生成（推荐）
1. 点击「AI 对话」
2. 输入主题，如"梯度下降算法"
3. 等待 AI 生成 storyboard
4. 检查并调整段落
5. 点击「生成视频」

### 方式2：手动编辑
1. 点击「选择主题」加载预设
2. 或点击「添加段落」手动创建
3. 选择模板、填写演讲稿
4. 调整参数
5. 点击「生成视频」

### 方式3：导入 JSON
1. 准备 storyboard JSON 文件
2. 点击「导入 Storyboard」
3. 检查并调整
4. 点击「生成视频」

## 🔧 配置说明

### 环境变量
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `MIMO_API_KEY` | MiMo API Key | - |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key | - |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.siliconflow.cn/v1` |
| `LLM_MODEL` | LLM 模型名称 | `deepseek-ai/DeepSeek-V3` |
| `TTS_PROVIDER` | TTS 提供商 | `gpt-sovits` |
| `GPT_SOVITS_BASE_URL` | GPT-SoVITS 地址 | `http://127.0.0.1:9880` |

### 画质选项
- `low`：480p 15fps（快速预览）
- `medium`：480p 15fps（默认）
- `high`：720p 30fps（最终输出）

## 📁 项目结构

```
├── server.py                    # FastAPI 入口
├── run_full_pipeline_v2.py      # 完整pipeline一键运行
├── run_from_storyboard.py       # 分镜驱动生成
├── llm_chat_service.py          # LLM对话服务
├── llm_storyboard_service.py    # LLM分镜生成
├── llm_codegen_service.py       # LLM代码生成
├── services/                    # 核心服务
│   ├── tts_service.py
│   ├── manim_service.py
│   ├── subtitle_service.py
│   ├── composition_service.py
│   └── whisper_align_service.py
├── templates/                   # 16个Manim动画模板
│   ├── intro_v2.py              # 片头
│   ├── neural_network.py        # 神经网络
│   ├── decision_tree.py         # 决策树
│   ├── confusion_matrix.py      # 混淆矩阵
│   ├── knn_demo.py              # KNN演示
│   ├── overfitting.py           # 过拟合
│   └── ...                      # 更多模板
├── scripts/                     # 生成脚本 & 工具
│   ├── approach1_storyboard.py  # 方案A：分镜批量
│   ├── approach3_*.py           # 方案C：全脚本
│   ├── batch_generate.py        # 批量生成
│   └── rebuild_*.py             # 重建工具
├── tests/                       # 测试套件
├── docs/                        # 文档
│   ├── MiMo_API配置指南.md
│   └── 第一版功能清单.md
├── frontend/                    # Web前端
├── components/ / layouts/       # Manim组件
└── manim_scenes/                # 场景文件
```

## 🧪 测试

### 测试 LLM 连接
```bash
python test_llm_api.py
```

### 测试所有功能
```bash
python test_all.py
```

### 批量生成示例
```bash
python batch_generate.py
```

## ❓ 常见问题

### Q1: TTS 服务未启动
**A**: 确保 GPT-SoVITS 已启动：
```bash
cd GPT-SoVITS-v2pro-20250604
python api_v2.py
```

### Q2: Manim 渲染失败
**A**: 检查 MiKTeX 是否安装：
```bash
miktex --version
```

### Q3: LLM API 调用失败
**A**: 检查 `.env` 文件中的 API Key 是否正确

### Q4: 视频预览不显示
**A**: 检查浏览器控制台，确保 `/outputs` 静态文件可访问

## 📝 开发说明

### 添加新模板
1. 在 `templates/` 目录创建新文件
2. 实现 `construct()` 方法
3. 使用 `TitleBar` 创建标题
4. 重启服务自动注册

### 自定义 LLM
修改 `llm_storyboard_service.py` 中的 `_get_llm_caller()` 函数

### 修改画质
编辑 `storyboard_pipeline.py` 中的 `quality` 参数

## 📄 许可证

MIT License

## 🙏 致谢

- [Manim Community](https://www.manim.community/) - 动画引擎
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) - 语音合成
- [WhisperX](https://github.com/m-bain/whisperX) - 语音对齐
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架

## 📞 联系方式

如有问题，请提交 Issue 或联系开发者。

---

**最后更新**: 2026-05-28
**版本**: v1.0
