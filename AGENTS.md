# Spatial AI 双引擎作品集 · Antigravity 独立开发工作区规则

本工作区（`D:\Projects\spatial-ai-portfolio`）是 **AetherVault（[0→1] 正交美学光谱编译器）** 与 **TectonicLoop（[1→N] 物理建构排雷与造价反向闭环）** 的主工程开发根目录。

## 1. 核心定位与产品哲学（AI PM 优先，兼顾 AI 应用研发）

- **主投 AI 产品经理（AI PM）**：所有设计与功能交付优先服务于痛点清晰度、**AI 与非 AI 边界克制**（`<20ms` 纯向量重排、单应性几何投影 $H/H^{-1}$ 与 Zero-LLM `Decimal` 算账）、**GUI + LUI 融合交互**、**单图冷启动成本压控（`<= ¥0.008/图`）**、**EDD 量化跑分**与 **Bad Case 归因**。
- **核心投递门禁（M3 · 2026-12-13）**：第 3 周末完成公网零延迟 Showcase 上线并定稿 AI PM 主力简历。
- **80/20 实用工程严谨度**：不做过度防御性企业合规包袱（无登录鉴权/无复杂三维 BIM 全量解析），把算力与工时砸在美感、解耦逻辑和实测指标上；未知单价必须诚实报 `UNKNOWN_PRICE_MISSING`，绝不置 `0`。

## 2. 双模同构架构（Dual-Mode Architecture）

1. **`⚡ Instant Showcase Mode`（默认公开线上版）**：
   - `web/` 直接读取预烘焙的跨界美学数据包（80 张精选样张）与 3 套商业立面重绘实景对比图，保证 0 秒冷启动、60fps 交互。
2. **`🧪 Live Engine & Eval Mode`（本地演示与离线评测版）**：
   - 本地 FastAPI（`127.0.0.1:8780`）调用 `pipeline/` 执行实时解析与算账；`eval/` 跑出四大自动化 Benchmark 报告。

## 3. Linear 同步与领航协同

- **Linear 项目**：`P-MIC-5` — [Spatial AI 双引擎作品集 · AetherVault & TectonicLoop](https://linear.app/merle/project/spatial-ai-双引擎作品集-aethervault-and-tectonicloop-2cd268daef88)
- **Linear 文档**：[三位一体总蓝图：AI PM 优先开发路线、3分钟演示剧本与简历防御手册](https://linear.app/merle/document/三位一体总蓝图ai-pm-优先开发路线3分钟演示剧本与简历防御手册-2d46a79b0ba3)
- **当前接续范围**：`MIC-156` ~ `MIC-168`（`M0` 已在 `MIC-154`/`MIC-155` 收口；开工请先读 [docs/SESSION_PLAN.md](file:///D:/Projects/spatial-ai-portfolio/docs/SESSION_PLAN.md)）。
- **既有个案资产联动**：上游联动 `P-MIC-4`（Aesthetic KB）参考图与色板底座；下游复用 `02-aurora` 的 `Decimal` 损耗算账逻辑与 `03-super-agent` 的 Diff Slider 交互基因。

## 4. Windows 环境与安全铁律

- **运行环境**：Windows + PowerShell；Node 统一使用 `npm.cmd`（前端 `web/` 绑定 `127.0.0.1:5174`）；Python 3.12+ 后端绑定 `127.0.0.1:8780`。
- **严禁写入密钥**：任何源码、JSON 数据包、日志或文档中**严禁**出现 API Key / Token；外部 VLM 或生图调用一律读取本机环境变量（`OPENAI_API_KEY`、`GEMINI_API_KEY` 等）。
- **沟通语言**：默认使用简体中文，引用文件附可点击 `file:///` 链接。
