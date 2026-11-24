---
name: handoff
description: 将当前会话压缩为极简结构化交接文档（.agents/HANDOFF.md，<800 tokens），结合真实 git 状态、项目里程碑与 Ultra 模型分层建议实现开新会话零失忆冷启动。当用户说“执行 handoff”、“存档交接”或准备切换新窗口时使用。
---

# Handoff 执行指令

当用户触发本技能时，严格执行以下步骤：

1. **采集真实工作区状态（只读核查，严禁凭记忆盲写）**：
   - 运行 `git status -sb` 与 `git diff --stat` 获取工作区未提交改动快照。
   - 若项目存在 `docs/SESSION_PLAN.md`，对齐当前所处的 Milestone / Linear Issue 编号（如 `MIC-156`）。
2. **按「下一步任务类型」给出新会话模型档位建议（Direct 直连，不开 Orchestrator）**：
   - 全栈功能 / 前端 UI / 架构实现 → 推荐 `Gemini 4 Neon (High)` 或 `Neon (Medium)`（Direct）
   - 批量脚本 / 数据洗标 / 常规样式与测试修补 → 推荐 `Gemini 4 Hydrogen (High)`（Direct，省一半配额）
   - 硬核数学几何 / 棘手并发或底层 Bug 攻坚 → 推荐 `Gemini 4 Carbon (High)` 或 `Neon (XHigh)`（Direct 短会话）
3. **写入 `.agents/HANDOFF.md`（直接覆盖旧文件）**：
   - **总字数严格控制在 800 tokens 以内**，严禁粘贴大段历史源码或客套话。
   - 必须严格按以下模板输出：

```markdown
# Session Handoff
- **Updated**: <YYYY-MM-DD HH:MM>
- **Active Milestone / Issue**: <如 M1 / MIC-156，无则填 N/A>
- **Recommended Next Model**: <按上方分层规则给出具体单模型 + Direct 直连说明>
- **Git Working Tree**: <clean，或简列已修改/未跟踪的关键路径与文件数>

## 1. 当前目标 (Goal)
<1-2 句话说清最终要达成的可验证交付物>

## 2. 已完成与变更文件 (Completed & Verified)
- `<path/to/file>`：<做了什么改动>
- **已验证通过**：<实际运行过的命令与结果；未实测项明确标 UNPROVEN>

## 3. 关键约束与避坑 (Constraints & Decisions)
- <已锁定的技术选型、不可破坏的接口契约、本轮踩过的坑>

## 4. 下一步精确指令 (Next Exact Step)
1. <新会话第一句应该立刻执行的具体动作>
2. <紧接着的验证命令与通过标准>
```

4. **极简收尾**：写入完成后，在对话中仅回复：
   `✅ Handoff 已写入 .agents/HANDOFF.md。请开新会话（建议模型见交接单，保持 Direct 直连）并发送：@.agents/HANDOFF.md 继续`
