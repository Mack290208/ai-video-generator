# -*- coding: utf-8 -*-
"""
llm_storyboard_service.py
根据用户输入的主题，调用 LLM 自动生成完整的 storyboard JSON

支持多种 LLM 提供商：
- MiMo（小米大模型）
- DeepSeek
- OpenAI 兼容 API
"""
import json
import os
from typing import Any, Optional

# 模板目录（供 LLM 参考）
TEMPLATE_CATALOG = {
    "bullet_summary": {
        "summary": "要点总结列表，适合总结、回顾、知识点罗列",
        "params": ["title", "points", "duration"],
        "example": {
            "title": "梯度下降要点",
            "points": ["计算梯度方向", "更新参数", "重复迭代"],
            "duration": 8.0
        }
    },
    "neural_network": {
        "summary": "神经网络结构图，展示多层感知机的层结构和连接",
        "params": ["title", "layers", "layer_labels", "duration"],
        "example": {
            "title": "神经网络结构",
            "layers": [3, 5, 4, 2],
            "layer_labels": ["输入层", "隐藏层1", "隐藏层2", "输出层"],
            "duration": 10.0
        }
    },
    "decision_tree": {
        "summary": "决策树分裂过程可视化，展示特征选择和节点分裂",
        "params": ["title", "feature", "threshold", "left_label", "right_label", "depth", "duration"],
        "example": {
            "title": "决策树分类",
            "feature": "花瓣长度",
            "threshold": "2.5cm",
            "left_label": "山鸢尾",
            "right_label": "其他",
            "depth": 2,
            "duration": 10.0
        }
    },
    "confusion_matrix": {
        "summary": "混淆矩阵可视化，展示分类结果和评估指标",
        "params": ["title", "labels", "values", "duration"],
        "example": {
            "title": "混淆矩阵",
            "labels": ["猫", "狗", "鸟"],
            "values": [50, 3, 2, 5, 45, 1, 1, 2, 48],
            "duration": 8.0
        }
    },
    "knn_demo": {
        "summary": "KNN 分类算法可视化，展示 K 近邻投票过程",
        "params": ["title", "k", "n_points", "n_classes", "duration"],
        "example": {
            "title": "KNN 分类演示",
            "k": 3,
            "n_points": 20,
            "n_classes": 3,
            "duration": 10.0
        }
    },
    "overfitting": {
        "summary": "过拟合可视化，展示训练误差和验证误差的变化趋势",
        "params": ["title", "epochs", "complexity", "duration"],
        "example": {
            "title": "过拟合现象",
            "epochs": 50,
            "complexity": 3,
            "duration": 10.0
        }
    },
    "concept_compare": {
        "summary": "概念双栏对比，适合 A vs B 类型的对比",
        "params": ["title", "left_title", "right_title", "left_formula", "right_formula", 
                   "left_point_1", "left_point_2", "left_point_3", "right_point_1", "right_point_2", "right_point_3"],
        "example": {
            "title": "信息增益 vs 基尼系数",
            "left_title": "信息增益",
            "right_title": "基尼系数",
            "left_formula": "H(D) - H(D|A)",
            "right_formula": "1 - \\sum p_i^2",
            "left_point_1": "基于熵的概念",
            "right_point_1": "计算更简单",
            "duration": 10.0
        }
    },
    "curve_descent": {
        "summary": "曲线下降动画，适合展示优化过程、损失函数下降",
        "params": ["title", "func_label", "rule_label", "start_x", "lr", "steps", "duration"],
        "example": {
            "title": "梯度下降过程",
            "func_label": "L(\\theta) = (\\theta - 2)^2",
            "rule_label": "\\theta_{new} = \\theta - \\alpha \\cdot \\nabla L",
            "start_x": -2.5,
            "lr": 0.25,
            "steps": 8,
            "duration": 12.0
        }
    },
    "data_flow": {
        "summary": "数据流图，适合展示数据处理流程、模型架构",
        "params": ["title", "nodes", "duration"],
        "example": {
            "title": "神经网络数据流",
            "nodes": ["输入层", "隐藏层", "输出层"],
            "duration": 8.0
        }
    },
    "formula_evolve": {
        "summary": "公式推导演变，适合逐步展示公式推导过程",
        "params": ["title", "steps", "duration"],
        "example": {
            "title": "线性回归公式推导",
            "steps": ["y = wx + b", "L = (y - \\hat{y})^2", "\\frac{\\partial L}{\\partial w} = -2x(y - \\hat{y})"],
            "duration": 12.0
        }
    },
    "lr_comparison": {
        "summary": "学习率对比曲线，适合对比不同参数的效果",
        "params": ["title", "lrs", "duration"],
        "example": {
            "title": "不同学习率对比",
            "lrs": [0.01, 0.1, 0.5],
            "duration": 10.0
        }
    },
    "scatter_classify": {
        "summary": "散点分类可视化，适合展示分类算法效果",
        "params": ["title", "n_points", "n_classes", "duration"],
        "example": {
            "title": "KNN分类效果",
            "n_points": 50,
            "n_classes": 3,
            "duration": 8.0
        }
    },
    "intro_v2": {
        "summary": "片头动画",
        "params": ["title", "subtitle", "duration"],
        "example": {
            "title": "机器学习基础",
            "subtitle": "第三讲：梯度下降",
            "duration": 5.0
        }
    },
    "outro": {
        "summary": "片尾动画",
        "params": ["title", "duration"],
        "example": {
            "title": "感谢观看",
            "duration": 3.0
        }
    }
}


def build_system_prompt() -> str:
    """构建系统提示词 - 优化版，让参数更精准"""
    template_info = json.dumps(TEMPLATE_CATALOG, ensure_ascii=False, indent=2)
    
    return f"""你是一个专业的机器学习教学视频策划师。你的任务是根据用户输入的主题，生成一个完整的视频 storyboard JSON。

## 可用模板及参数说明

{template_info}

## 模板选择指南

根据内容类型选择最合适的模板：

| 内容类型 | 推荐模板 | 示例场景 |
|---------|---------|---------|
| 概念对比 | concept_compare | 信息增益vs基尼系数、L1vsL2正则化 |
| 优化过程 | curve_descent | 梯度下降、损失函数收敛 |
| 数据流程 | data_flow | 神经网络前向传播、数据预处理流程 |
| 公式推导 | formula_evolve | 线性回归公式、反向传播推导 |
| 总结要点 | bullet_summary | 知识点回顾、课程总结 |
| 分类可视化 | scatter_classify | KNN分类、SVM决策边界 |
| 神经网络 | neural_network | MLP结构、全连接网络 |
| 决策树 | decision_tree | ID3/C4.5分裂过程 |
| 混淆矩阵 | confusion_matrix | 分类模型评估指标 |
| KNN算法 | knn_demo | K近邻投票过程 |
| 过拟合 | overfitting | 训练/验证误差曲线对比 |

## 参数精准填写规则

1. **数值参数**：
   - learning_rate: 0.001-1.0 之间，常用 0.01, 0.1, 0.5
   - epochs/steps: 10-100 之间，常用 20, 50, 100
   - k (KNN): 1-10 之间，常用 3, 5, 7
   - n_points: 10-100，常用 20, 50
   - n_classes: 2-5，常用 2, 3

2. **字符串参数**：
   - title: 简洁明了，5-15字
   - formula: 使用 LaTeX 格式，如 "L(\\theta) = (\\theta - 2)^2"
   - labels: 中文标签数组，如 ["猫", "狗", "鸟"]

3. **时长估算**：
   - 中文语速约 3-4 字/秒
   - 每段演讲稿 30-80 字 → duration 8-20 秒
   - intro/outro 固定 3-5 秒

## 输出格式

输出严格的 JSON，不要有其他文字：

```json
{{
  "video_title": "视频标题",
  "duration_target_seconds": 60,
  "segments": [
    {{
      "template": "模板名称",
      "narration": "演讲稿内容（口语化，30-80字）",
      "subtitle": "字幕内容（可选，与narration相同则省略）",
      "params": {{
        "title": "段落标题",
        "duration": 10.0,
        "其他参数": "根据模板填写"
      }}
    }}
  ]
}}
```

## 演讲稿写作规范

1. **口语化**：避免书面语，用"我们""大家""你"等称呼
2. **解释性**：先解释概念，再展示可视化
3. **过渡自然**：段落之间有过渡语句
4. **时长匹配**：字数与 duration 匹配（3-4字/秒）

## 结构要求

- 以 intro_v2 开头（3-5秒）
- 以 outro 结尾（3秒）
- 中间 3-5 个教学段落
- 总时长 60-120 秒
- 每个段落有明确的教学目标

请直接输出 JSON，不要有其他文字。"""


def generate_storyboard_with_llm(
    topic: str,
    provider: Optional[str] = None,
    llm_func=None
) -> dict:
    """
    使用 LLM 生成 storyboard
    
    Args:
        topic: 用户输入的主题
        provider: LLM 提供商 ("mimo", "deepseek", "openai", None=自动检测)
        llm_func: 自定义 LLM 调用函数
    
    Returns:
        storyboard 字典
    """
    if llm_func is None:
        # 自动检测或使用指定的 provider
        llm_func = _get_llm_caller(provider)
    
    system_prompt = build_system_prompt()
    user_prompt = f"请为以下主题生成教学视频 storyboard：\n\n{topic}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        response = llm_func(messages)
        # 提取 JSON
        storyboard = _extract_json(response)
        return storyboard
    except Exception as e:
        return {"error": f"LLM 生成失败: {e}"}


def _get_llm_caller(provider: Optional[str] = None):
    """获取 LLM 调用函数"""
    if provider == "mimo" or (provider is None and os.getenv("MIMO_API_KEY")):
        return _mimo_llm_call
    elif provider == "deepseek" or (provider is None and os.getenv("DEEPSEEK_API_KEY")):
        return _deepseek_llm_call
    else:
        return _default_llm_call


def _mimo_llm_call(messages: list) -> str:
    """MiMo API 调用（小米大模型）"""
    import requests
    
    api_key = os.getenv("MIMO_API_KEY")
    base_url = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    model = os.getenv("MIMO_MODEL", "mimo-v2-pro")
    
    if not api_key:
        raise RuntimeError(
            "未设置 MIMO_API_KEY。请配置 MiMo API Key\n"
            "访问 https://open.xiaomi.com 或联系小米 AI 团队获取"
        )
    
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _deepseek_llm_call(messages: list) -> str:
    """DeepSeek API 调用"""
    import requests
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY")
    
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"}
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _default_llm_call(messages: list) -> str:
    """默认 LLM 调用（OpenAI 兼容 API，包括硅基流动）"""
    import requests
    
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")
    
    if not api_key:
        raise RuntimeError(
            "未配置 LLM API。请设置以下环境变量之一：\n"
            "  - MIMO_API_KEY (小米 MiMo)\n"
            "  - DEEPSEEK_API_KEY (DeepSeek)\n"
            "  - OPENAI_API_KEY (OpenAI 兼容)"
        )
    
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    """从 LLM 响应中提取 JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 ```json ... ``` 代码块
    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试提取 { ... } 块
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"无法从 LLM 响应中提取 JSON: {text[:200]}...")


# 测试
if __name__ == "__main__":
    # 测试 prompt 生成
    print("=== System Prompt 预览 ===")
    print(build_system_prompt()[:1000])
    print("...")
    print()
    print("=== 模板数量 ===")
    print(f"共 {len(TEMPLATE_CATALOG)} 个模板")
