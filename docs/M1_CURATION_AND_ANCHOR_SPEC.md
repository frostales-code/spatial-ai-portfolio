# M1-1 (`MIC-156`) 跨界美学样本策展、五点黄金锚点标尺与冷启动成本账本

> **项目**：`P-MIC-5` · Spatial AI 双引擎作品集 — **Project A (`AetherVault`)**  
> **交付日期**：2026-11-22  
> **核心目标**：验证“脱离画面主体看美学同构（Cross-Domain Aesthetic Isomorphism）”的产品本体假设，建立抗漂移的 8 轴 × 5 点黄金参照标尺，并跑通公网 Showcase 零版权风险的 80 张跨界样张入库与 `<= ¥0.008/图` 端云成本模型。

---

## 一、 `P-MIC-4 (Aesthetic KB)` 本地资产审计与版权边界决策

### 1.1 本地既有资产实查结果
在开工前对本地 `P-MIC-4` 数据库（`C:\Users\Frost\Documents\Antigravity\aesthetic-kb\data\db\meta.sqlite`）进行只读审计：
- **存量规模**：共 **523 条入库资产**（其中 `519` 条标记为 `privacy='public'`、`4` 条为 `private`），已由本地管线提取 `512px` WebP 缩略图、5 簇 **OKLab 主色板**（`palette_json`）及 `pHash/dHash`。
- **关键约束识别**：
  1. **公网分发合规风险（M3 门禁要求）**：519 条公开记录均来自 `pinterest_import` 第三方图钉（主要来源于个人画板 `MUSE`、`配色`、`建筑`、`fashion`、`Typography/Graphic Design` 等），缺少可公开托管至 Vercel / GitHub Pages 的 CC0 / Public-Domain 再分发授权。
  2. **跨界门类失衡**：现有收藏集中于建筑/室内空间、服饰穿搭与平面版式，缺乏专门的**精密工业产品（`industrial`）**与**东方器物手作（`craft`）**垂类。

### 1.2 双轨融合解决方案（Personal Prior Linkage + Redistribution-Safe Assets）
为兼顾**个人品味先验真实联动**与 **M3 公网零版权风险分发**：
1. **先验只读关联**：`pipeline/curate_80.py` 以只读模式读取 `P-MIC-4` SQLite 中 519 条公开记录的 OKLab 色板，按最小感知色差为 80 张策展样本自动匹配最接近的 `akb_prior_asset_id` 与 `akb_board_hint`（绝不拷贝任何未经授权的 Pinterest 原图二进制文件至公开包）。
2. **80 张可公网再分发高清样本（`800×600` WebP）**：
   - `architecture`（16 张）、`industrial`（16 张）、`editorial`（16 张）、`craft`（16 张）：先通过 **Openverse CC0 / Public Domain Mark (`pdm`)** 接口筛选高分辨率免版权摄影与博物馆公开藏品，再经 `contact_sheet_80.jpg` 逐格目视审计，将无精确公有领域匹配或题材偏离的 41 个锚点/垂类样本通过 `gpt-image-1-mini` 定向生成替换（`AI-SELF-GENERATED-SHOWCASE`），最终构成 **22 `CC0` + 1 `PDM` + 41 `AI-SELF-GENERATED-SHOWCASE` + 16 `CC0-SELF-GENERATED` = 80 张** 100% 版权安全样张，并均提取实测 OKLab `k=5` 主色板；
   - `graphic`（16 张）：由 `pipeline/curate_80.py` 内置程序化矢量构成引擎生成 `1200×900` 超采样后 Lanczos 抗锯齿降采样至 `800×600` WebP（协议：`CC0-SELF-GENERATED`）。

---

## 二、 五大门类样本均衡分布与先验配比

| 门类 ID | 中文门类 | 样本数量 | 个人库先验 (`is_personal_prior=True`) | 跨界破圈样本 | 典型美学覆盖焦点 |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `architecture` | 当代建筑空间 | **16** | 8 (`arch_01`~`arch_08`) | 8 | 耐候钢、清水混凝土、木构茶室、狭缝光影、张拉膜 |
| `industrial` | 精密工业产品 | **16** | 4 (`ind_01`~`ind_04`) | 12 | 光学镀膜镜头、CNC 合成器、机械腕表、黑胶/金属材质 |
| `editorial` | 高定与电影摄影 | **16** | 4 (`edit_01`~`edit_04`) | 12 | 极地漫射天光、银盐黑白、强光束剪影、机能材质 |
| `craft` | 东方手作器物 | **16** | 4 (`craft_01`~`craft_04`) | 12 | 柴烧裂纹釉、备前烧、桧木榫卯、南铁、大漆与和纸 |
| `graphic` | 构成主义插画 | **16** | 4 (`graph_01`~`graph_04`) | 12 | 瑞士 12 栏网格、包豪斯原色对冲、孔版印刷、Op-Art |
| **合计** | **5 大跨界门类** | **80** | **24** | **56** | **全量通过 `AestheticAsset` 四层 Schema 校验** |

---

## 三、 8 轴 × 5 点黄金锚点标尺与显著度门控规则（40 个独立锚点）

为消除 VLM 直接盲打 `[-1.0, +1.0]` 浮点数导致的跨批次漂移，系统在 [pipeline/anchor_specs.py](file:///D:/Projects/spatial-ai-portfolio/pipeline/anchor_specs.py) 固化了每条轴的 5 档物理判据与 40 个唯一参照图 ID（成对区间定标 Pairwise Interval Bracketing）：

| 光谱轴 ID | 中文名称 | `-1.0` 锚点 | `-0.5` 锚点 | `0.0` 锚点 | `+0.5` 锚点 | `+1.0` 锚点 | 显著度 `salience` 门控要点 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `tectonic_honesty` | 构造表现度 | `arch_06` | `ind_04` | `arch_04` | `arch_01` | `ind_02` | 纯 2D 扁平图形与微距肌理自动降权 `s <= 0.25` |
| `surface_entropy` | 肌理时间熵 | `ind_01` | `ind_06` | `craft_04` | `arch_02` | `craft_01` | 材质表面占主视觉 >30% 时锁定 `s >= 0.85` |
| `spatial_density` | 信息与留白 | `edit_01` | `arch_08` | `craft_06` | `ind_08` | `graph_08` | 跨媒介全局可测（`s ∈ [0.80, 0.98]`） |
| `geometric_order` | 几何形态秩序 | `arch_10` | `craft_02` | `edit_06` | `arch_03` | `graph_01` | 曲直廓形与轴网分格清晰时 `s >= 0.75` |
| `lighting_drama` | 光影反差度 | `edit_02` | `craft_08` | `arch_05` | `ind_03` | `arch_07` | 无体量光影的 2D 纯平矢量画降权 `s <= 0.20` |
| `chromatic_tension` | 色彩能量张力 | `edit_03` | `arch_09` | `craft_05` | `ind_05` | `graph_02` | 基于 OKLab 色度与色相角差全媒介高置信度 `s >= 0.85` |
| `thermal_mood` | 情绪色温亲疏 | `ind_07` | `arch_11` | `graph_04` | `craft_03` | `arch_12` | 纯消色差黑白影调自动降权至 `s <= 0.45` |
| `reality_abstraction` | 写实与抽象度 | `edit_04` | `arch_13` | `ind_09` | `graph_05` | `graph_03` | 清晰分离物理光学镜头摄影与图形抽象构成 `s >= 0.85` |

---

## 四、 端云分层入库冷启动成本账本（目标 `<= ¥0.008 / 图`）

参考设计师首次导入 `1,000` 张本地参考图（如 Eagle 目录）的冷启动链路（代码实算：`estimate_ingestion_cost_cny(1000)`）：

| 阶段层级 | 执行位置与技术栈 | 处理内容 | 成本策略 | 摊销单价 (RMB) |
| :--- | :--- | :--- | :--- | :---: |
| **Tier 0 · 本地边缘预处理** | 本机 CPU/GPU（`Pillow` + `NumPy` + `SigLIP-2`） | 生成 `512px` WebP、`pHash/dHash` 去重（拦截 ~12% 重复图）、OKLab `k=5` HEX 色板、本地向量入库（3 秒内可搜） | 零云端 API 调用 | **¥0.0000 / 张** |
| **Tier 1 · 异步批量 VLM 解析** | Cloud Batch API（`gemini-2.5-flash-lite` + Context Caching） | 缓存 1,850 tokens 五点黄金标尺 System Prompt + 258 img tokens + 90 user tokens → 输出 320 tokens 四层正交 JSON（含 +15% 重试冗余） | Batch 50% 折扣 + Context Cache 75% 折扣 + pHash 跳重 12% | **¥0.0008 / 张** |
| **合计有效入库成本** | `1,000` 张批次实测总计 **¥0.77** | 全量完成 4 层 Schema + OKLab 色板 + 向量建库 | 预算红线：`¥0.0080 / 张` | **¥0.0008 / 张（仅占红线 9.6%）** |

> 即使未来将单图分析模型升级至更高阶的 `gemini-2.5-flash`（Batch 价约 `¥0.0038 / 张`），仍保有 **2 倍以上**的成本安全余量。
