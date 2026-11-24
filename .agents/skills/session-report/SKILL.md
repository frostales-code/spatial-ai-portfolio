---
name: session-report
description: 基于真实会话轨迹（transcript.jsonl）生成零盲猜的上下文水位、Prompt Cache 命中率、膨胀源与 Ultra 配额效率诊断报告，归档至 .agents/reports/。当用户说“执行 session-report”、“会话体检”或排查额度消耗异常时使用。
---

# Session Report 执行指令（实测遥测驱动，严禁盲猜）

当用户触发本技能时，严格执行以下步骤：

1. **运行本地只读遥测审计脚本（不把原始日志读入上下文）**：
   ```powershell
   python ".agents/skills/session-report/scripts/audit_session.py" --conversation-id "<当前 Conversation ID>"
   ```
   - 从脚本输出的 JSON 中直接获取**实测 (`measured`)** 的 `latest_prompt_tokens`、`weighted_cache_hit_pct`、`cold_cache_events`、`top_heavy_tool_results`、`top_slow_tool_steps` 与 `verdict`。
2. **生成归档报告 `.agents/reports/report-YYYYMMDD-HHMM.md`**：
   包含以下 4 个核心模块（所有数字必须引用自脚本实测结果，严禁估算编造）：
   - **1. 任务完成度矩阵**：列出本会话原定目标、已完成并实测项、待办/阻塞项。
   - **2. 上下文膨胀源审计（Top 5）**：列出 `top_heavy_tool_results`（工具名、字符/估算 Token 数）与 `top_slow_tool_steps`，明确标出 `should_subagent = true`（本应委派给 `research` Subagent 隔离的大文件读取或长输出）。
   - **3. 缓存健康度与 Ultra 配额风险评估**：
     - 当前上下文水位（对比 `150k–180k` 换仓甜点线、`200k` 长上下文分水岭、`512k` 平台压缩上限）；
     - 累计加权缓存命中率与本轮命中率，列出每一次 `cold_cache_events` 的精确步骤与归因（闲置 >4.5m 超时 vs 中途切模型 / Orchestrator 双角色轮切碎缓存）；
     - 模型配额效率提示（结合 `quota_notes`：如 Carbon `2026-12-01` 恢复 `$4/$20` 标准重型权重、Neon Direct 主力性价比、Hydrogen 跑量优势、`XHigh` 100 倍思考税）。
   - **4. 明确行动建议**：从 `继续当前会话` / `立即执行 handoff 切新会话` / `锁定 Direct 单模型（Neon High 或 Hydrogen High）` 中给出唯一明确结论及下一步动作。
3. **精简回复**：向用户展示生成的报告可点击链接及 3 行核心摘要（当前水位、加权缓存命中率、行动建议）；同时可附上 [Context Monitor](sidecar://antigravity-context-monitor/context_monitor/) 快捷入口供实时对照。
