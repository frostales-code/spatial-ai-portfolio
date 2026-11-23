# 下一步会话开工蓝图：进入 Milestone M1 (`MIC-156` ~ `MIC-158`)

> **当前进展**：Milestone `M0`（`MIC-154`, `MIC-155`）已完成并验证通过；领航目录、Linear `P-MIC-5` 看板及上游双模脚手架均已就位。  
> **下一会话唯一重心**：按 **AI PM 优先原则**，用一周时间彻底把 **Project A (`AetherVault`)** 从“纯文字沙盒”升级为“带 80 张跨界美图、2 轮二分校准和生图对比证据的真实交互工作台”。

---

## M1 分步执行顺序

### Step 1 (`MIC-156`)：跨界美图策展与 8 轴五点黄金锚点定标
1. 联动 `P-MIC-4 (Aesthetic KB)`（或使用开源免版权图库 / 自生成样本）在 `D:\Projects\spatial-ai-portfolio\data\curated_80\` 准备 **80 张跨 5 门类**高清缩略图（建筑空间、精密工业产品、高定/电影摄影、东方器物手作、构成主义插画）。
2. 在 `pipeline/anchor_specs.py` 编写 **8 轴 × 5 档（`-1.0, -0.5, 0.0, +0.5, +1.0`）黄金参照判据** 与 VLM Few-Shot Calibration Prompt。
3. 记录并估算单图入库端云分层成本账本（确保控制在 `<= ¥0.008 / 张`）。

### Step 2 (`MIC-157`)：批量打标管线与 6 组 AST 编译生图对照
1. 编写 `pipeline/anchor_scorer.py`（从环境变量读取 API Key，本地提取主色 HEX + Batch VLM 批量输出 4 层正交 JSON `aethervault_assets_v1.json`）。
2. 使用 `pipeline/aethervault_schema.py` 的 `compile_conflict_free_ast` 生成 6 组经典跨界混搭 Prompt，实测生成 **「多图直接混合串色崩坏 vs AetherVault AST 正交编译成图」** 对比图组。

### Step 3 (`MIC-158`)：升级 Project A 旗舰 React 交互沙盒 (`web/`)
1. 在 `D:\Projects\spatial-ai-portfolio\web` 安装前端依赖（`npm.cmd install`）并构建 `AetherVaultWorkspace` 组件。
2. 保留 [legacy-prototype/ai-thesis-v0.html](file:///D:/Projects/spatial-ai-portfolio/legacy-prototype/ai-thesis-v0.html) 的 Architectural Dark 瑞士暗色工业美学，重点实现四大升级：
   - 8 轴交互雷达图 + 滑块实时驱动 80 张真图流 `<20ms` 重排（调用 `src/engine/salienceMetric.ts`）；
   - **Visual A/B Calibration（2 轮视觉二分校准浮层）**：点击模糊意图后弹出两组微调视觉分叉卡，2 次点击收敛权重；
   - **正交三槽位混音台 + 编译生图实测对比抽屉**：清晰对比直接喂多图与 AST 编译出图的光学、材质、光感保真度。

## 开工前环境自检命令

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "c:\Users\Frost\OneDrive\Desktop\Personal AI Proj\04-spatial-ai-portfolio\scripts\bridge.ps1" status
powershell -NoProfile -ExecutionPolicy Bypass -File "c:\Users\Frost\OneDrive\Desktop\Personal AI Proj\04-spatial-ai-portfolio\scripts\bridge.ps1" smoke-math
```
