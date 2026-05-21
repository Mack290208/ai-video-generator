# 模板工厂使用手册

> 版本：v2 模板工厂（2026-05-15）
> 适用：AI 助教视频项目 / Mack & 紬

模板工厂的目标：**老师写教学提示词 → LLM 选模板 + 填参数 → 系统出片**。
本文档既是开发参考，也是 LLM 路由器的 system prompt 素材。

---

## 整体设计

```
老师提示词
    │
    ▼
┌────────────────────────────────────────┐
│ 教学策划 Agent（LLM）                  │
│ 输入：提示词 + 模板 catalog            │
│ 输出：分镜 JSON（segments[]）          │
│   每段 = {                             │
│     narration  / subtitle  / template  │
│     params: { ... }                    │
│   }                                    │
└────────────────────────────────────────┘
    │
    ▼
manim_service.render_manim_scene(template, params)
    │
    ▼
TTS / 字幕 / 合成
    │
    ▼
最终 mp4
```

LLM 不写 manim 代码，只填 JSON。模板代码由我们维护。

---

## 当前可用模板（v2，4 个）

### 0. ✅ `concept_compare` — 双栏文字概念对比【2026-05-16 通过】

- **何时用**：A vs B 类纯文字概念对照
  - 信息增益 vs 基尼系数
  - L1 正则 vs L2 正则
  - 监督学习 vs 无监督学习
  - 偏差 vs 方差 / Bagging vs Boosting
- **不要用**：需要数学曲线对比（用 `lr_comparison`）；纯单栏要点（用 `bullet_summary`）；多于两类（暂不支持）
- **关键参数**：`title`, `left_title`, `right_title`, `left_formula`/`right_formula`（LaTeX 可选）, `left_point_1..3`/`right_point_1..3`, `left_color`/`right_color`, `duration`
- **画面**：标题在顶部，中央细分隔线，左右两列各：小标题（彩色）+ 公式（可选）+ 1~3 条要点（黑底白字 FadeIn）
- **示例**：见 `templates/concept_compare.py` 里的 `TEMPLATE_META.example_params`

### 0b. ✅ `formula_evolve` — 公式逐步推导【2026-05-16 通过】

- **何时用**：一步一步推导出结论
  - 损失函数推导（MSE 最优解 θ* = (XᵀX)⁻¹ Xᵀy）
  - Sigmoid / Softmax 求导
  - 反向传播链式求导
  - 贝叶斯定理展开
- **不要用**：超过 5 步的超长推导（建议拆为两个模板段）；需画图 / 坐标系（用 `curve_descent`）
- **关键参数**：`title`, `step_1..5`（纯 LaTeX）, `caption_1..5`（中文说明）, `final_emphasis`, `duration`
- **⚠重要约束**：`step_X` 只能是纯 LaTeX 数学表达式，**不能含中文**（LaTeX 编译会报 Unicode error）。中文说明全部放到 `caption_X` 里。
- **布局**：最后一步 caption 底部 ≥ -2.5，距字幕区有 0.35 安全余量（不会被硬烧字幕遮挡）
- **示例**：见 `templates/formula_evolve.py` 里的 `TEMPLATE_META.example_params`

### 0c. ✅ `scatter_classify` — 二维散点 + 决策边界【2026-05-16 通过】

- **何时用**：二分类问题的几何可视化
  - 感知机 / 逻辑回归 / 线性 SVM 的线性可分边界
  - 核 SVM / 神经网络 的非线性边界（circle / parabola）
  - KNN / 决策树边界的几何含义
- **不要用**：多分类（⚠ 只支持两类）；高维特征；需要公式推导（用 `formula_evolve`）
- **关键参数**：`title`, `subtitle`, `class_a_label`/`class_b_label`, `class_a_points`/`class_b_points`（“x,y; x,y; ...” 分号分隔）, `boundary_kind` (linear/circle/parabola), `boundary_a`/`b`/`c`, `show_regions`, `duration`
- **坐标范围固定**：x ∈ [-5, 5]，y ∈ [-3, 3]
- **边界参数说明**：
  - `linear`：y = a*x + b（c 不用）
  - `circle`：圆心 (a, b) 半径 c
  - `parabola`：y = a*(x-b)² + c
- **show_regions 限制**：目前只有 `linear` 会染色两侧区域（circle/parabola 暂不染，不会报错）
- **示例**：见 `templates/scatter_classify.py` 里的 `TEMPLATE_META.example_params`

### 0d. ✅ `data_flow` — 神经网络前向数据流【2026-05-16 通过】

- **何时用**：多层节点 + 全连接箭头 + 脉冲动画的拓扑展示
  - MLP / 全连接网络结构
  - 前向传播过程可视化
  - 深度学习入门：从输入到输出的数据流
  - 反向传播的对照引子（先看正向）
- **不要用**：RNN / Transformer / CNN（拓扑不一样）；需要画具体权重值；层数 > 5 或单层节点 > 6（画面塞不下）
- **关键参数**：`title`, `subtitle`, `layer_sizes`（“3,4,4,2” 逗号分隔）, `layer_labels`（分号分隔）, `pulse_count`, `show_arrows`, `duration`
- **脉冲逻辑**：每条全连接边都发一颗黄点（src×dst 条），所有边同时亮起来，是"真正的前向传播"可视化，没有脉冲“瞬移"或"分裂"假象
- **示例**：见 `templates/data_flow.py` 里的 `TEMPLATE_META.example_params`

### 1. `intro_v2` — 课程开场

- **何时用**：每节课的第一段，标题 + 副标题 + 装饰线
- **不要用**：需要多行内容时（用 `bullet_summary`）
- **关键参数**：`title`, `subtitle`, `duration`
- **示例**：
  ```json
  {
    "template": "intro_v2",
    "params": {
      "title": "机器学习课堂",
      "subtitle": "今天我们来讲：梯度下降",
      "duration": 5.0,
      "show_decoration": true
    }
  }
  ```

### 2. `curve_descent` — 沿曲线迭代下降

- **何时用**：演示一个参数沿损失曲面一步步逼近极值
  - 梯度下降（凸函数）
  - 随机梯度下降
  - 牛顿法（写 `func_kind` 扩展时）
  - 学习率单独演示（不对比）
- **不要用**：要对比两套参数（用 `lr_comparison`）；多变量优化（暂不支持）
- **关键参数**：
  - `title`, `func_label`（LaTeX 公式）
  - `func_kind`：`quadratic_centered_at_2` / `quadratic_centered_at_0`
  - `start_x`, `lr`, `steps`
  - `var`：参数名，默认 `\theta`
- **画面布局**：左侧坐标系 + 曲线 + 迭代点；右侧信息栏（公式、更新规则、α、当前值、收敛提示）
- **示例**：
  ```json
  {
    "template": "curve_descent",
    "params": {
      "title": "梯度下降",
      "func_label": "L(\\theta) = (\\theta - 2)^2",
      "rule_label": "\\theta_{t+1} = \\theta_t - \\alpha \\cdot \\nabla L(\\theta_t)",
      "start_x": -2.5,
      "lr": 0.25,
      "steps": 8
    }
  }
  ```

### 3. `lr_comparison` — 学习率（超参数）对比

- **何时用**：左右分屏，**两个不同超参数**在同一损失函数下的下降效果
  - α 太小 vs 合适 / 合适 vs 太大
  - 有动量 vs 无动量（重写 `_build_func` 后）
  - 不同初始点
- **不要用**：单一参数演示（用 `curve_descent`）；超过两种对比（暂不支持）
- **关键参数**：
  - `title`, `func_label`
  - `lr_left`, `lr_right`
  - `lr_left_label`, `lr_right_label`（出现在两个坐标系下方）
  - `start_x`, `steps`
- **示例**：
  ```json
  {
    "template": "lr_comparison",
    "params": {
      "title": "学习率的影响",
      "func_label": "L(\\theta) = (\\theta - 2)^2",
      "lr_left": 0.05,
      "lr_left_label": "α=0.05 (太小)",
      "lr_right": 0.7,
      "lr_right_label": "α=0.7  (合适)",
      "steps": 8
    }
  }
  ```

### 4. `bullet_summary` — 要点总结 / 列表页

- **何时用**：一个标题 + 1~5 条编号要点逐条出现
  - 课程结尾的"本节回顾"
  - "三个性质 / 四个步骤" 这类静态枚举
  - 概念定义页
- **不要用**：需要画面动画（用其它专用模板）；推导链路（未来加 `formula_evolve`）
- **关键参数**：`title`, `point_1` ~ `point_5`, `duration`
- **配色规则（自动）**：第 1 黄 / 第 2 蓝 / 第 3 绿 / 第 4-5 白
- **示例**：
  ```json
  {
    "template": "bullet_summary",
    "params": {
      "title": "本节回顾",
      "point_1": "梯度下降沿负梯度方向更新参数",
      "point_2": "学习率 α 控制每一步的更新幅度",
      "point_3": "α 太小收敛慢，太大会震荡发散"
    }
  }
  ```

---

## LLM 路由规则（system prompt 用）

### 选择模板的判断顺序

1. 是开场/标题页吗？→ `intro_v2`
2. 是结尾总结/罗列要点吗？→ `bullet_summary`
3. 涉及参数或函数对比（左右分屏）吗？→ `lr_comparison`
4. 演示一个变量沿曲面变化吗？→ `curve_descent`
5. 都不匹配？→ 暂时降级到 `bullet_summary`（罗列文字），并在响应里 flag 出来供后续加新模板

### 不要做的事

- 不要让 LLM 自己写 Manim 代码
- 不要传 schema 里没有的参数（会被 service 透传，可能引发错误）
- LaTeX 公式记得双反斜杠转义（`\\theta`，不是 `\theta`）

### 输出格式（严格 JSON）

```json
{
  "video_title": "梯度下降一节课",
  "segments": [
    {
      "kind": "intro" | "main" | "comparison" | "outro",
      "narration": "TTS 念给学生听的口语版本（α 改成阿尔法等）",
      "subtitle":  "字幕显示版本（保留专业符号 α / θ）",
      "template": "<模板 id>",
      "params": { ... }
    }
  ]
}
```

`narration` 与 `subtitle` 分离的原因：GPT-SoVITS 不会念希腊字母和数学符号。

---

## 扩展模板的步骤

每加一个新模板：

1. `templates/<new_template>.py`：
   - 一个 `manim.Scene` 子类
   - `PARAM_SCHEMA` dict（必须）
   - `TEMPLATE_META` dict（推荐：summary / use_cases / not_for / example_params）
2. 复用 `components/` 里的原子件（避免重复造轮子）
3. 不要硬编码坐标，引用 `layouts.constants`
4. 跑 `test_v2_new_templates.py` 形式的烟雾测试
5. 更新本文档

未来计划的模板（占位）：
- `formula_evolve`：推导链路（公式逐步变形）
- `data_flow`：神经网络前向 / 反向数据流
- `scatter_classify`：二维点 + 决策边界（SVM/KNN）
- `histogram_evolve`：概率分布演化
- `matrix_op`：矩阵运算可视化

---

## 当前模板覆盖率估计

ML 入门一学期约 30~50 个核心知识点。预计：

| 模板 | 估计覆盖 |
|---|---|
| intro_v2 + bullet_summary | 几乎所有节首尾 |
| curve_descent | 优化算法相关（GD / SGD / Momentum / Adam 部分） |
| lr_comparison | 超参数对比类（学习率、batch、动量系数） |
| 待加 5~6 个 | 网络结构、概率论、矩阵代数、决策边界 |

→ **15~20 个模板预计能覆盖 90% 入门课内容**。


---

## ⏱️ 给 LLM 的时长估算公式（A2 阶段加入）

生成 storyboard 时**必须**用这个公式预估每段 narration 的时长，避免再次出现 LLM 估 60s、实际 88s（偏 47%）这种超车。

### 公式

```
中文 narration 预估时长（秒）
    = 中文可说字数 / 5.5  +  标点停顿

可说字数：CJK 中文字符 + ASCII 字母数字（标点、空格不计）
标点停顿：。？！? ! .  → 每个 +0.40s
          ，、；, ;    → 每个 +0.20s
最小时长：1.50s （避免极短句）
语速来源：神里绫华 e10 音色、speed_factor=1.0 的实测反推（5-15 决策树视频）
```

### 实测验证

| narration（节选） | 字数 | 停顿 | 预估 | 实测 | 误差 |
|---|---|---|---|---|---|
| 决策树 seg1 intro（约 26 字） | 26 | 0.6 | 5.33s | 5.64s | -5.5% |
| 总长度（5 段共 ~484 字） | 484 | 11 | ~88.0s | 88.44s | -0.5% |

公式精度优于 ±10%，远好于 LLM 自由估算（±47%）。

### 用法约束

1. **生成 storyboard 之前**先用公式预估每段，让总和接近 `target_seconds`
2. 总预估偏 target > ±15% 时，调整 narration 长短（增减句子）后重估
3. 输出的 storyboard JSON 顶层**必须**包含：
   ```json
   "duration_estimate_seconds": 88.4
   ```
   driver 会拿这个值跟实测对比，可以暴露 LLM 估算偏差并迭代。
4. 字段名固定为 `duration_estimate_seconds`，不要换名字。

### 给 driver 的实现参考

`services/duration_estimator.py` 已经实现了同一个公式，LLM 不需要自己写，只要按字面应用即可，必要时可以让 driver 跑 `estimate_storyboard_seconds(narrations)` 双校验。
