# 双轨高阶简历矩阵与面试防线手册（M3 定稿版）

- **线上零延迟展示 URL**：https://frostales-code.github.io/spatial-ai-portfolio/
- **可打印 A4 交付物目录**：
  - AI PM 主力版简历：[`docs/deliverables/AI_PM_Resume.pdf`](deliverables/AI_PM_Resume.pdf)（源文件：[`AI_PM_Resume.html`](deliverables/AI_PM_Resume.html)）
  - AIGC / 空间智能研发备选版：[`docs/deliverables/AI_Builder_Resume.pdf`](deliverables/AI_Builder_Resume.pdf)（源文件：[`AI_Builder_Resume.html`](deliverables/AI_Builder_Resume.html)）
  - 产品方法论一页纸：[`docs/deliverables/Product_Methodology_OnePager.pdf`](deliverables/Product_Methodology_OnePager.pdf)（源文件：[`Product_Methodology_OnePager.html`](deliverables/Product_Methodology_OnePager.html)）
- **180 秒实操剧本**：[`docs/THREE_MINUTE_DEMO_SCRIPT.md`](THREE_MINUTE_DEMO_SCRIPT.md)

> 注：两份 PDF 简历顶部个人信息栏保留清晰的占位符（`[姓名]` / `[+86 手机号]` / `[个人邮箱]` / `[院校名称]` 等），投递前直接编辑对应 HTML 并使用无头浏览器重出 PDF 即可，绝不含任何虚构身份信息。

---

## 一、主推战略（80% 精力）：AI 产品经理（AI PM）STAR 核心叙事

### 项目一：Spatial AI 双引擎（AetherVault + TectonicLoop）
- **情境（S）**：空间与创意 AIGC 长期陷入双重断层——参考灵感散落跨媒介且多图直喂必发“物体泄漏与串色”，生成的商业立面渲染图既缺乏建造逻辑也无法给甲方核出精确造价。
- **任务（T）**：主导从产品定义、AI/Non-AI 架构边界划分、交互原型到 EDD 评测闭环的端到端交付，保证无登录、0 秒冷启动上线供多端随时试玩。
- **行动与产品决策（A）**：
  1. **克制的 AI vs 非 AI 分工**：VLM 仅用于冷启动离线 8 轴结构化打标（Prompt Cache 命中率 **49.25%**，冷启动压低至 **¥0.00596/图**，Batch 等效 **¥0.00298/图**）；前端检索全部下沉至浏览器内 **&lt;20ms 纯矢量显著性加权欧氏距离**（零后端 Token 损耗）。
  2. **Scope-Isolated Prompt AST 编译与对照实验**：构建三正交槽位（光学镜头 / 材质构造 / 光影氛围）防泄漏编译器及 6 组多图直喂 vs AST 实拍对比。
  3. **80/20 物理投影与 Zero-LLM Decimal 造价闭环**：用单应性平面正投 `H/H⁻¹` 替代高成本 3D BIM（竖向消隐误差 **0.000°**，非掩码重照明 **PSNR ≥ 38 dB**）；继承 `02-aurora` `Decimal` 口径设计 30 SKU × 8 条构造排雷规则与三档 VE 对比，缺价必诚实抛 `UNKNOWN_PRICE_MISSING`。
- **结果（R）**：
  - `AetherVault` 达成 **80/80 Pydantic 契约 100% 通过**，显著性排序 Spearman **ρ = 0.611**（较均匀欧氏 `0.540` 提升 **+13.1%**）；
  - `TectonicLoop` 交付 **3 套商业实景 × 3 档预算对照 + 8 幅 SVG 节点大样**；线上站点静态负载仅 **5.28 MB**，桌面端与 `390×844` 移动端均为 **0 报错 / 0 溢出**。

### 项目二：Super Agent Workbench & AP Platform（`03-super-agent`）+ Aurora 物料引擎（`02-aurora`）
- **叙事定位**：证明复杂多 Agent 系统编排能力与高严谨度工业数据闭环（与 TectonicLoop 形成前后端方法论呼应，避免业务同质化）。
- **核心亮点**：透明阶段状态机与人类高风险确认门禁（HITL）、多通道自主检索+识图、60fps 几何算量、**253 例基线自动化回归**验证，及直连可读文档与 Rhino 8 交付产物。

---

## 二、面试高频追问标准防御口径（Q&A Defense Playbook）

1. **Q1：为什么不在每次拖拽滑块时让大模型实时重新重排或出图？**  
   - *答*：交互体验的“跟手性”阈值在 `<100ms` 内，调 LLM 既浪费每轮 1-3 元人民币的无效成本又带来秒级卡顿。我在架构里明确规定：**VLM 只负责一次性离线语义投影（¥0.00596/图）；线上的连续探索必须降维成前端纯矢量计算（<20ms 实测 <1ms）**，只有在确认组合槽位后才进入 AST 编译。
2. **Q2：Prompt AST 怎么证明真的比“直接给生图模型喂多张参考图”更好？**  
   - *答*：不能凭感觉。我在作品集里专门做了 6 组可控变量对比（如 `CMP_01` 咖啡亭 × CNC 旋钮）：多图直喂会把工业合成器按键直接贴到房屋墙体并导致锈蚀串色；而 AST 强制作用域隔离后，只借取工业设备的紧固构造语法而不泄漏实体造型，且全部配图都可在首页 Curtain Slider 里左右拖拽逐像素对照。
3. **Q3：为什么 TectonicLoop 的建筑规范排雷与造价不算 LLM Agent？如何处理缺失价格？**  
   - *答*：甲方签合同最怕“幻觉算错钱”或“现浇越限没人拦”。施工边界规范和材料摊销损耗天然是强确定性规则——我们直接复用 `02-aurora` 验证过的 `Decimal` 算法内核配 8 条强制排雷规则。更关键的是一条产品红线：定额缺失时系统严禁编造 `0`，而是显式返回 `UNKNOWN_PRICE_MISSING` 阻断报价汇总，把工程风险前置给人工核价。
4. **Q4：三维建筑体量为什么不做完整 BIM/IFC 解析而用 H/H⁻¹ 单应性投影？**  
   - *答*：典型的 **80/20 产品取舍**。面向商业门店与街区快改（90% 高频立面更新场景），全量 3D 重建链路冗长、导入门槛极高且容易因照片遮挡崩坏；而只要立面主体近似共面，用 `H/H⁻¹` 四点标定即可在 2D 透视图与正交分缝 CAD 之间建立 0.000° 误差映射，极低成本完成“生图效果 → 施工立面图 → 分区面积计算”的三位一体。
5. **Q5：如果没有 GPU 或后端离线，线上给 HR/面试官发的作品集链接会失效吗？**  
   - *答*：不会。架构设计之初即确立了 **双模同构（Dual-Mode）** 规范：GitHub Pages 公网版本以 `Instant Showcase` 模式加载经过全量预校验的 `5.28 MB` 静态 WebP 与 JSON 资产，且 TS 前端复刻了完整的加权矢量重排、AST 编译器和 `Decimal` VE 计算核；即便无网络请求 `/api/`，页面依然具备 100% 核心交互，绝不转圈等待或白屏。
6. **Q6：你如何沉淀可复用的 AI 评测（EDD）标准而非“跑通一次 Demo”？**  
   - *答*：每个能力都拆出了硬性自动化门禁指标：结构化入库看 Pydantic **80/80** 通过率、向量检索看 Spearman **ρ = 0.611** 增益、重绘看非掩码区 **PSNR ≥ 38 dB**、经济账看实测 **¥0.00596/图** 与 **49.25%** 缓存命中，全工程由 Pytest、Subpath Vite 构建、`impeccable detect` 静态审计与无头浏览器响应式验收兜底，而非靠主观截屏评价。
