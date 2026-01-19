# 恋爱公式 V2.1: 基于 LLM 的即时群聊深度分析方案

## 1. 核心目标 (Objective)
在现有基于统计学（Love Formula）的分析基础上，引入基于**真实聊天历史**的语义分析。
利用 LLM 阅读目标用户最近的群聊记录，捕捉其“语气”、“语境”和“社交微表情”，生成更具灵魂的**“Deep Dive / 灵魂回响”**分析报告，并展示在现有报告的下方。

## 2. 架构设计 (Architecture)

### 2.1 数据获取层 (Data Acquisition)
**原则**: 插件**不维护**任何群聊历史数据库，完全依赖 OneBot V11 接口实时获取。

*   **组件名**: `OneBotAdapter`
*   **配置**: 新增配置项 `analyze_history_count` (默认 20，允许用户自定义)。
*   **目标 API**: `get_group_msg_history` / `get_history_msg`。
*   **处理逻辑**:
    1.  **实时获取**: 调用 API 拉取最近的 `analyze_history_count` 条群消息。
    2.  **连续窗口**: 保留完整的连续对话像，**不进行基于回复关系的过度过滤**。这样做是为了捕捉非显式回复（无 Reply ID）但语义相关的“回应”。
    3.  **数据清洗**:
        *   将数据转换为简单的对话脚本格式。
        *   标记出 **目标用户 (Target)** 和 **其他群友 (Other)**。
        *   脱敏：过滤掉 Base64 图片、XML 卡片等冗余数据，仅保留文本内容和必要的表情描述。

    *格式示例*:
    ```text
    [2023-10-27 10:00:01] <UserA (Target)>: 今天好想吃火锅啊
    [2023-10-27 10:00:15] <UserB>: +1
    [2023-10-27 10:00:20] <UserC>: 就知道吃
    ```

### 2.2 LLM 分析层 (Analysis Layer)
更新 `LLMAnalyzer` 以支持“上下文感知模式”。

*   **输入**:
    *   统计数据 (原有: Simp, Vibe, Ick, Nostalgia)
    *   **新增: 聊天上下文片段 (Context Snippets)**
        ```text
        [User]: 早上好 (08:00)
        [Other]: 没人理你 (08:05)
        [User]: 呜呜呜 (08:06)
        ```
*   **Prompt 优化**:
    *   增加角色设定: "你不仅是数据裁判官，还是一位擅长解读微表情的心理侧写师。"
    *   任务: "结合数据和最近的发言，分析该用户的**当前心理状态** (如：急于求成、从容不迫、强颜欢笑)。"

### 2.3 渲染层 (Presentation Layer)
在现有 `template.html` 基础上扩展底部区域。

*   **新区域**: `DeepDiveSection` ("灵魂回响" / "Soul Echoes")
*   **布局**: 全宽卡片，位于“演化算式”和“行为诊断”下方。
*   **样式风格**:
    *   保持 `galgame` 主题风格。
    *   使用深色半透明背景或“机密档案”风格，突出“深度分析”的差异感。
    *   包含“关键词云”或“情绪波形”意象 (通过 CSS 实现)。

## 3. 实现步骤 (Implementation Steps)

### Phase 1: API 联调与数据获取
1.  在 `src/handlers` 中创建 `HistoryFetcher`。
2.  实现调用 OneBot API 获取群消息逻辑。
3.  处理数据清洗与格式化。

### Phase 2: LLM Prompt 工程
1.  修改 `llm_analyzer.py` 的 prompt 模板。
2.  增加 `real_chat_context` 字段的注入。
3.  测试 LLM 对聊天记录的理解能力，确保不产生幻觉。

### Phase 3: 前端 UI 扩展
1.  修改 `template.html` (已扩宽至 1000px，空间充足)。
2.  增加 `.deep-dive-card` 样式。
3.  设计“情绪气泡”或“金句摘录”的展示形式。

## 4. UI 设计预览 (UI Prototype)

```html
<!-- 新增区域概念 -->
<div class="deep-dive-card">
    <div class="dd-header">
        <span class="dd-icon">👁️</span>
        <span class="dd-title">深层心理侧写 (Deep Psyche Profile)</span>
    </div>
    <div class="dd-content">
        <div class="dd-keywords">
            <span class="tag">#强颜欢笑</span>
            <span class="tag">#边缘试探</span>
            <span class="tag">#期待回应</span>
        </div>
        <div class="dd-text">
            "虽然纯爱值仅有 18%，但从最近的发言记录来看，你正在小心翼翼地试探群内的底线。
             那句 '呜呜呜' 虽然看似玩笑，实则暴露了你对 Vibe (存在感) 的极度渴求。
             建议：别再用表情包掩饰尴尬了，直球攻击或许更有效。"
        </div>
    </div>
</div>
```

## 5. 风险与对策
*   **API 缺失**: 如果 OneBot 实现不支持历史记录 API，我们将回退到仅使用当前 Session 缓存的最近消息 (可能需要维护一个轻量级的 `recent_msgs` 队列)。
*   **隐私问题**: 确保发送给 LLM 的数据经过匿名化处理，且不包含图片/文件内容。
