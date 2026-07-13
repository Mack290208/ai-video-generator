# MiMo API 配置指南

## 🚀 快速配置步骤

### 1. 获取 MiMo API Key

**方式一：小米开放平台**
- 访问 https://open.xiaomi.com
- 注册/登录小米开发者账号
- 在 AI 服务中申请 MiMo API 权限

**方式二：联系小米 AI 团队**
- 如果你是小米合作伙伴或学生，可以联系小米 AI 团队获取测试 Key
- 邮箱：ai-support@xiaomi.com（示例）

### 2. 配置 .env 文件

编辑 `C:\Users\hymac\Desktop\临时python骨架穿透文件\.env`：

```env
# MiMo API 配置
MIMO_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2-pro

# 注释掉其他 LLM 配置
# DEEPSEEK_API_KEY=...
# OPENAI_API_KEY=...
```

### 3. 测试 API 连接

```bash
cd C:\Users\hymac\Desktop\临时python骨架穿透文件
python test_llm_api.py
```

### 4. 重启服务

```bash
# 关闭当前服务
# 重新运行启动器
python C:\Users\hymac\Desktop\launcher.py
```

---

## 📝 MiMo API 信息

- **模型名称**: `mimo-v2-pro`
- **API 格式**: OpenAI 兼容
- **端点**: `https://api.xiaomimimo.com/v1/chat/completions`
- **支持功能**: 
  - 对话生成
  - JSON 输出
  - 长文本处理

---

## 🔧 常见问题

### Q1: API Key 无效
**A**: 检查以下几点：
- API Key 是否正确复制（没有多余空格）
- 是否在有效期内
- 是否有调用权限

### Q2: 连接超时
**A**: 可能是网络问题：
- 检查网络连接
- 尝试使用 VPN（如果需要）
- 增加超时时间

### Q3: 模型不存在
**A**: 确认模型名称：
- 使用 `mimo-v2-pro`（推荐）
- 或 `mimo-v2`（基础版）

---

## 💡 备选方案

如果 MiMo API 暂时无法获取，可以使用：

### 方案1: DeepSeek（推荐备选）
```env
DEEPSEEK_API_KEY=your_key_here
```
- 访问 https://platform.deepseek.com
- 提供免费额度

### 方案2: 硅基流动（已有配置）
```env
OPENAI_API_KEY=sk-mnrzgtkvgwjxkkhsynvkuqsnzcnrdrarfbebctmwjnrkbczt
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-ai/DeepSeek-V3
```
- 当前配置文件中已有
- 可以直接使用

---

## 🎯 推荐配置顺序

1. **首选**: MiMo API（小米大模型，国内最快）
2. **备选**: DeepSeek API（免费额度）
3. **兜底**: 硅基流动（已配置）

---

## 📞 获取帮助

如果遇到问题：
1. 检查 `.env` 文件格式是否正确
2. 运行 `python test_llm_api.py` 测试连接
3. 查看控制台错误信息
4. 联系小米 AI 团队技术支持

---

**最后更新**: 2026-05-28
**版本**: v1.0
