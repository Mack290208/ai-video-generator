# -*- coding: utf-8 -*-
"""
llm_chat_service.py
AI 对话服务 - 支持与用户讨论视频制作方案

功能：
1. 普通对话：讨论视频内容、模板选择、结构安排
2. Storyboard 生成：当用户确认方案后，生成 storyboard
"""
import json
import os
from typing import Optional

# 对话系统提示词
CHAT_SYSTEM_PROMPT = """你是一个专业的教学视频制作助手，名叫「小助教」。你的任务是帮助老师规划和制作教学视频。

## 你的能力

1. **讨论视频内容**：帮助老师梳理知识点、确定讲解重点
2. **推荐模板**：根据内容特点推荐合适的动画模板
3. **规划结构**：设计视频的段落结构和时长分配
4. **优化表达**：改进讲解文案，使其更适合口语表达

## 可用模板

- **intro_v2**：片头动画（3-5秒）
- **outro**：片尾动画（3秒）
- **bullet_summary**：要点总结列表
- **concept_compare**：概念双栏对比（A vs B）
- **curve_descent**：曲线下降动画（优化过程）
- **data_flow**：数据流图（神经网络层结构）
- **formula_evolve**：公式推导过程
- **lr_comparison**：学习率对比
- **scatter_classify**：散点分类可视化
- **neural_network**：神经网络结构图
- **decision_tree**：决策树分裂过程
- **confusion_matrix**：混淆矩阵
- **knn_demo**：KNN 分类演示
- **overfitting**：过拟合现象

## 对话流程

1. **了解需求**：询问老师要讲什么知识点
2. **讨论方案**：推荐模板、讨论结构、优化文案
3. **确认方案**：当老师说"生成"、"确认"、"可以了"时，整理方案
4. **生成 Storyboard**：调用生成函数

## 回复风格

- 友好、专业、耐心
- 主动提问，了解需求
- 给出具体建议，不要空泛
- 当不确定时，询问更多细节

## 重要规则

**你是聊天助手，不是代码执行器。**

### 核心原则：
1. **先聊天讨论**：了解需求、推荐方案、优化结构
2. **等待明确指令**：只有用户说「帮我生成」「开始生成」「确认生成」时才触发生成
3. **不要自作主张**：不要在用户还在讨论时就急着生成

### 生成条件（必须同时满足）：
- 用户消息包含「帮我生成」「开始生成」「确认生成」等明确指令
- 你已经和用户讨论过视频方案

### 如果用户只是讨论需求：
- 回答问题、给出建议
- 推荐模板、优化结构
- 不要生成 storyboard

请用中文回复。"""


def get_chat_llm_call(provider: Optional[str] = None):
    """获取聊天用的 LLM 调用函数（不强制 JSON 格式）"""
    import os
    
    # 检测可用的 provider
    if provider == "mimo" or (provider is None and os.getenv("MIMO_API_KEY") and os.getenv("MIMO_API_KEY") != "your_mimo_api_key_here"):
        return _mimo_chat_call
    elif provider == "deepseek" or (provider is None and os.getenv("DEEPSEEK_API_KEY") and os.getenv("DEEPSEEK_API_KEY") != "your_deepseek_api_key_here"):
        return _deepseek_chat_call
    else:
        return _default_chat_call


def _deepseek_chat_call(messages: list) -> str:
    """DeepSeek 聊天调用（不强制 JSON 格式）"""
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
            "max_tokens": 2048
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _mimo_chat_call(messages: list) -> str:
    """MiMo 聊天调用（不强制 JSON 格式）"""
    import requests
    
    api_key = os.getenv("MIMO_API_KEY")
    base_url = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    model = os.getenv("MIMO_MODEL", "mimo-v2-pro")
    
    if not api_key:
        raise RuntimeError("未设置 MIMO_API_KEY")
    
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
            "max_tokens": 2048
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _default_chat_call(messages: list) -> str:
    """默认聊天调用（不强制 JSON 格式）"""
    import requests
    
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")
    
    if not api_key:
        raise RuntimeError("未配置 LLM API")
    
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
            "max_tokens": 2048
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def chat_with_ai(
    message: str,
    history: list[dict[str, str]],
    provider: Optional[str] = None
) -> dict:
    """
    与 AI 对话
    
    Args:
        message: 用户消息
        history: 对话历史 [{"role": "user/assistant", "content": "..."}]
        provider: LLM 提供商
    
    Returns:
        {
            "response": "AI 回复",
            "should_generate": bool,  # 是否应该生成 storyboard
            "topic": str or None  # 如果要生成，主题是什么
        }
    """
    # 构建消息列表
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    
    # 添加历史对话
    for msg in history[-10:]:  # 只保留最近10条
        messages.append(msg)
    
    # 添加当前消息
    messages.append({"role": "user", "content": message})
    
    # 检查用户是否明确要求生成
    should_generate = _check_should_generate(message, "")
    topic = _extract_topic(message, "") if should_generate else None
    
    # 如果用户明确要求生成，直接返回，不调用 LLM
    if should_generate and topic:
        return {
            "response": f"好的，我来为你生成「{topic}」的教学视频 storyboard！",
            "should_generate": True,
            "topic": topic
        }
    
    # 否则，调用 LLM 进行聊天
    llm_func = get_chat_llm_call(provider)
    
    try:
        response = llm_func(messages)
        
        return {
            "response": response,
            "should_generate": False,
            "topic": None
        }
    except Exception as e:
        return {
            "response": f"抱歉，我遇到了一些问题：{str(e)}",
            "should_generate": False,
            "topic": None
        }


def _check_should_generate(user_msg: str, ai_response: str) -> bool:
    """检查是否应该生成 storyboard"""
    # 用户明确要求生成的关键词
    strong_generate_keywords = [
        "帮我生成", "生成 storyboard", "生成storyboard",
        "开始生成", "就这个方案", "确认生成",
        "可以生成了", "生成视频"
    ]
    
    # 检查用户消息中是否包含强生成关键词
    user_msg_lower = user_msg.lower()
    for keyword in strong_generate_keywords:
        if keyword in user_msg_lower:
            return True
    
    # 如果用户只是说"生成"但没有具体上下文，不触发
    # 只有当用户明确说"帮我生成关于XXX的"才触发
    if "帮我生成" in user_msg and ("视频" in user_msg or "storyboard" in user_msg):
        return True
    
    return False


def _extract_topic(user_msg: str, ai_response: str) -> str:
    """从对话中提取主题"""
    import re
    
    # 优先匹配带书名号/引号的主题
    bracket_match = re.search(r'[\u300c\u300e](.+?)[\u300d\u300f]', user_msg)
    if bracket_match:
        topic = bracket_match.group(1).strip()
        # 去掉可能的修饰词
        for suffix in ['教学视频', '视频', 'storyboard']:
            if topic.endswith(suffix):
                topic = topic[:-len(suffix)].strip()
        if topic:
            return topic
    
    # 常见模式匹配
    patterns = [
        r"关于(.+?)的(?:教学)?(?:视频|storyboard)",
        r"生成(.+?)的(?:教学)?(?:视频|storyboard)",
        r"讲(.+?)的(?:教学)?(?:视频|storyboard)",
        r"关于(.+?)[\s，。,.]",
        r"主题[是为：:]\s*(.+?)[\s，。,.]",
        r"要讲(.+?)[\s，。,.]",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, user_msg)
        if match:
            return match.group(1).strip()
    
    # 最后兜底：去掉常见动词，提取剩余部分
    cleaned = user_msg
    for word in ['帮我生成', '生成', '关于', '帮我', '的', '教学视频', 'storyboard', '视频']:
        cleaned = cleaned.replace(word, ' ')
    cleaned = ' '.join(cleaned.split()).strip()
    return cleaned if cleaned else user_msg.strip()


def generate_storyboard_from_chat(
    topic: str,
    history: list[dict[str, str]],
    provider: Optional[str] = None
) -> dict:
    """
    从对话上下文生成 storyboard
    
    Args:
        topic: 视频主题
        history: 对话历史
        provider: LLM 提供商
    
    Returns:
        storyboard 字典
    """
    from llm_storyboard_service import generate_storyboard_with_llm
    
    # 构建上下文提示
    context = ""
    if history:
        # 提取最近的讨论内容
        recent_messages = history[-6:]  # 最近3轮对话
        context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
    
    # 生成 storyboard
    enhanced_topic = topic
    if context:
        enhanced_topic = f"{topic}\n\n讨论背景：\n{context}"
    
    return generate_storyboard_with_llm(enhanced_topic, provider=provider)
