---
trigger: always_on
---

# Context Hygiene, Prompt Cache & Ultra Quota Rules

1. **只读重探索强制隔离（Subagent 分流）**：
   - 凡涉及全仓库搜索、阅读超过 `300` 行的源码、排查大段报错日志，或检视大型产线/前端数据包（如 `data/**/*.json`、`web/public/data/*.json`），必须委派给只读 `research` Subagent 执行（纯检索/文件扫描任务可显式传 `Model: "flash"` 走轻量配额池）。
   - 主会话仅接收不超过 `20` 行的结构化结论（文件路径、行号、核心逻辑）。
2. **禁止重复贴全量代码**：
   - 修改文件优先使用精准 `edit_file` 局部替换，不在对话回复正文中输出超过 `50` 行的完整代码块。
3. **单模型缓存锁 & 严禁双角色轮切碎缓存**：
   - 同一会话内保持 **Direct 单模型直连**，不主动建议中途切换模型，避免使用 Orchestrator ↔ Executor 双角色轮切（系统提示词前缀切换会导致 `cache_read_tokens = 0`，丧失 95% 热缓存折扣并触发全量冷启动重算）。
   - **Ultra 配额模型分层准则**（推荐新会话或 Handoff 时遵循）：
     - **日常全栈 / 前端 UI / 架构主力**：`Gemini 4 Neon (High)` 或 `Neon (Medium)`（Direct 直连，1M 平价且综合性价比最高；避免常驻开启 `XHigh`，因思考输出算力权重是热缓存读取的 100 倍）。
     - **大规模跑量 / 数据清洗 / 常规 CRUD**：`Gemini 4 Hydrogen (High)`（Direct 直连，物理算力消耗约为 Neon 的一半，5 小时池续航翻倍）。
     - **疑难算法 / 复杂根因攻坚**：`Gemini 4 Carbon (High)`（`2026-12-01` 起恢复 `$4/$20` 重型档）或 `Neon (XHigh)`，仅限独立短会话攻坚，解完即归档。
4. **主动换仓甜点线（`150k–180k`）**：
   - 尽管 Gemini 4 平台压缩上限为 `512k`，为规避 `200k` 长上下文计费拐点与闲置超时重算风险，当上下文逼近 `150k–180k` 或阶段闭环完成时，主动提示用户执行 `handoff`（或先执行 `session-report` 审计再 `handoff`）。
