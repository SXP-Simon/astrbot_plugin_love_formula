# 更新日志 (CHANGELOG)


## [v1.0.9] - fix(MessageHandler): 去重检查

*   **🐛 Bug 修复**: fix(MessageHandler): 去重检查，通过 DB 索引检查 ID，确保每条消息在生命周期内只被计算一次

---

<details>
<summary>📋 点击查看历史更新日志</summary>

## [v1.0.8] - 节流和阻止默认 LLM 接管

*   **🛠️ 健壮性增强**: 命令触发后立即回复响应用户，并且节流处理
*   **🐛 Bug 修复**: fix(cmd_love_profile): 在 cmd_love_profile 入口处调用 event.should_call_llm(True)，阻止默认 LLM 接管 (@zouyonghe)

</details>
