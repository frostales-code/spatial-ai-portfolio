# Spatial AI 双引擎作品集 · AetherVault & TectonicLoop

**线上零延迟展示 URL**：https://frostales-code.github.io/spatial-ai-portfolio/  
**开源工程仓库**：https://github.com/frostales-code/spatial-ai-portfolio

---

## 核心产品与技术定位

本仓库是 **Spatial AI 双引擎作品集** 的全栈工程与评测中心，针对创意与空间设计生成工作流中「灵感只可意会且多图混用串色」与「渲染效果图脱离造价与结构约束」两大痛点，分别给出边界克制的双引擎解决方案：

1. **AetherVault（`[0→1]` 正交美学光谱编译器）**：
   - 策展跨建筑、工业、平面、器物与摄影 5 门类（各 16 件）的 **80 件设计标本**与 **8 轴×5 点黄金锚点**；
   - VLM 仅用于冷启动离线打标（Prompt Cache 命中率 **49.25%**，实测单图成本 **¥0.00596/图**，Batch 等效 **¥0.00298/图**，Pydantic 契约 **80/80** 通过）；
   - 前端交互使用 **&lt;20ms 纯矢量显著性加权欧氏重排**（Spearman **ρ = 0.611** vs 均匀欧氏基线 0.540）配合「光学镜头 / 材质构造 / 光影氛围」三槽隔离 **Prompt AST 编译器**，含 **6 组可控对照对比**验证防泄漏效果。
2. **TectonicLoop（`[1→N]` 物理建构排雷与 VE 造价反向闭环）**：
   - 整合 `02-aurora` Zero-LLM 金融级 `Decimal` 计价核与 `03-super-agent` 透明阶段闸门方法论，构建 **30 项真实构件定额 SKU**、**8 条物理排雷规则**与 **8 幅 SVG 节点构造大样**；
   - 放弃高开销三维 BIM 重建，使用 **80/20 `H/H⁻¹` 单应性平面投影**（竖向消隐角偏差实测 **0.000°**，非掩码局部重照明 **PSNR ≥ 38 dB**）；
   - 覆盖 **3 组商业实景案例 × 3 档造价分层**（`Tier 0 概念原图` / `Tier 1 平衡造价` / `Tier 2 降本快装`），缺失单价强制报 `UNKNOWN_PRICE_MISSING`，绝不幻觉臆造 0 值，支持一键导出甲方 VE 任务书。

---

## 双模同构架构（Dual-Mode Architecture）

| 运行模式 | 默认入口 | 技术特性 | 适用场景 |
| :--- | :--- | :--- | :--- |
| **Instant Showcase Mode** | 公网 GitHub Pages（`5.28 MB` 静态负载） | 0 秒冷启动、无登录、60fps 交互；内置向量重排、AST 编译、单应性拼缝与 TS `Decimal` 造价全离线引擎 | 简历投递、HR/面试官手机端与电脑端零门槛即时体验 |
| **Live Engine & Eval Mode** | `127.0.0.1:8780`（FastAPI） | 实时调用 Python `pipeline/` 解析与定额内核，运行四大自动化 Benchmark 回归 | 现场技术深挖演示、新增样本/定额本地实测 |

---

## 核心目录导览

- `web/`：**Next.js 15 App Router**（静态导出）+ **shadcn/ui**（Radix UI + `next-themes` 深浅双主题）+ **Three.js**（AetherVault 80 标本 3D 美学流形 & TectonicLoop 3D 立面单应性投影）+ **Recharts** 交互评测看板 + Framer Motion
- `pipeline/`：Python 3.12 离线/在线核心管线（策展打标、AST 对照集生成、30 SKU 定额库、8 规则排雷、单应性 `H/H⁻¹` 投影与静态 Manifest 打包器）
- `server/`：本地 FastAPI `Live Engine` API 服务（绑定 `127.0.0.1:8780`）
- `tests/`：M1/M2 全链路自动化回归测试集
- `docs/`：PRD、黄金锚点规范、3 分钟演示剧本及 A4 单页简历/方法论一页纸交付物（见 [`docs/deliverables/`](docs/deliverables)）

---

## 本地启动与回归测试

```powershell
# 1. 启动前端（127.0.0.1:5174）
cd web
npm.cmd install
npm.cmd run dev

# 2. 启动本地实时引擎（可选，127.0.0.1:8780，API Key 通过本机环境变量注入）
python -m uvicorn server.main:app --host 127.0.0.1 --port 8780

# 3. 构建统一静态 Showcase 清单并执行子路径/全量回归
python -m pipeline.build_showcase_manifest
python -m pytest tests/test_m1_curation_and_anchors.py tests/test_m1_scorer_and_comparisons.py tests/test_m2_tectonic_pipeline.py
```
