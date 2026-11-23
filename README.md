# Spatial AI 双引擎作品集 · AetherVault & TectonicLoop

> **Dual-Mode Showcase + Compound AI Pipeline**  
> **Upstream Aesthetics (`AetherVault`, 0→1)** ↔ **Downstream Constructability & VE (`TectonicLoop`, 1→N)**

## 快速导航与工作区入口

- [**项目工作区规范 (`AGENTS.md`)**](file:///D:/Projects/spatial-ai-portfolio/AGENTS.md)
- [**M1 开工主蓝图 (`docs/SESSION_PLAN.md`)**](file:///D:/Projects/spatial-ai-portfolio/docs/SESSION_PLAN.md) ← **新开 Session 先读这份**
- [**三位一体总计划 (`docs/MASTER_PLAN.md`)**](file:///D:/Projects/spatial-ai-portfolio/docs/MASTER_PLAN.md)
- [**简历、3 分钟演示与面试防御库 (`docs/RESUME_AND_INTERVIEW_PLAYBOOK.md`)**](file:///D:/Projects/spatial-ai-portfolio/docs/RESUME_AND_INTERVIEW_PLAYBOOK.md)
- **Linear 全链路看板 (`P-MIC-5`)**：https://linear.app/merle/project/spatial-ai-双引擎作品集-aethervault-and-tectonicloop-2cd268daef88

## 架构设计：双模同构（Dual-Mode Architecture）

本仓库采用同一套前后端数据契约，支持两种运行模式：

1. **`⚡ Instant Showcase Mode`（默认公开线上版 · 零延迟 / 零 GPU 依赖）**
   - 前端 `web/` 直接加载经离线管线标定与预烘焙的 JSON 数据包与对比图像，保证招聘官与设计师点开网页后在 `0ms~20ms` 内流畅体验 8 维光谱重排、2 轮二分校准、Before/After 立面重绘窗帘滑块及 VE 任务书导出。
2. **`🧪 Live Engine & Eval Mode`（本地演示与技术面试深挖版）**
   - 通过 `server/`（FastAPI on `127.0.0.1:8780`）调用 `pipeline/` 中的确定性内核与多模态工作流：
     - `aethervault_schema.py`：8 维连续光谱本体、显著度门控距离 $D(\mathbf{q}, \mathbf{x})$、无冲突 Prompt AST 编译器；
     - `tectonic_state.py`：构件级图文孪生状态树、建构禁忌排雷器（Constructability Linter）、Zero-LLM `Decimal` 精确算账内核；
     - `homography_seam.py`：基于 `numpy` DLT 的单应性矩阵 $H / H^{-1}$ 正交模数网格透视逆投影与洞口避让算法；
   - 并通过 `eval/` 跑出可复现的 EDD 量化基准报告。

## 目录结构

```text
spatial-ai-portfolio/
├── AGENTS.md                    # Antigravity 项目级规范与 AI PM 优先准则
├── docs/                        # SESSION_PLAN / MASTER_PLAN / 简历防御库 / 原始 PRD
├── legacy-prototype/
│   └── ai-thesis-v0.html        # 早期单文件概念交互原型归档
├── pipeline/                    # 核心算法、领域本体与确定性规则内核
│   ├── __init__.py
│   ├── aethervault_schema.py    # 8 维光谱 + 显著度门控 + AST 编译器
│   ├── tectonic_state.py        # 图文状态树 + 排雷器 + Zero-LLM Decimal 算账
│   └── homography_seam.py       # H / H^-1 透视模数网格与灭点几何校验
├── server/                      # FastAPI Live Engine 接口 (127.0.0.1:8780)
│   ├── __init__.py
│   └── main.py
├── eval/                        # EDD 量化评测基准规范与脚本
│   └── README.md
├── web/                         # Vite + React 19 + TS + Tailwind 前端 (127.0.0.1:5174)
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/engine/salienceMetric.ts
├── pyproject.toml
└── README.md
```

## 本地启动与安全守则

- **Web 前端**：在 `web/` 下运行 `npm.cmd run dev`（绑定 `http://127.0.0.1:5174`）
- **Live API 后端**：在根目录运行 `uvicorn server.main:app --host 127.0.0.1 --port 8780`
- **安全与凭据**：严禁将任何 API Key / Token 写入源码或配置文件；外部 VLM / 生图调用统一从本机环境变量（如 `GEMINI_API_KEY`、`OPENAI_API_KEY`）读取。
