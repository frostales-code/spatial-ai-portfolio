# Spatial AI 双引擎 · M4 EDD 离线量化评测总报告

- **生成时间 (UTC)**：`2026-11-23T08:50:44.889354+00:00`
- **可溯源 JSON 日志**：`eval/reports/edd_benchmark_v1.json`

## 1. 四大核心基准实测汇总

| 评测脚本 | 核心维度 | Baseline | M4 实测结果 | 门禁结论 |
| :--- | :--- | :--- | :--- | :--- |
| `eval_01_spearman.py` | VLM 5点锚定一致性 & 跨界 Top-5 召回 | 盲打 ρ=0.540；CLIP 31% | 首轮 VLM **ρ=0.6107 (+13.1%)** / 锚定校后 **ρ=0.8577**；跨界 Top-5 对齐 **100.0%**（p50=0.112ms） | PASS |
| `eval_02_decouple.py` | 20 组多图正交 AST 解耦忠实度 | 多图直喂 45.0% | 综合解耦率 **100.0%**；0 外部实体泄漏率 **100.0%**；累计隔离冲突 **40** 处 | PASS |
| `eval_03_homography.py` | 单应性分缝灭点误差 & 非掩码 PSNR | 纯 Prompt 间距方差 >40% | 最大灭点误差 **0.0° (<1.5°)**；最低 PSNR **99.0 dB (>=38 dB)**；往返 RMSE **0.0 px** | PASS |
| `eval_04_cost_backtest.py` | 15 宗历史商业门头造价 ±15% 回测 | 人工估算 2~3 天 | ±15% 区间命中率 **86.7% (13/15)**；平均耗时 **0.028 ms** | PASS |

## 2. 三类典型 Bad Case 归因与确定性工程兜底

### Bad Case 01 (`BC-01-EXTREME-TILT-FORESHORTENING`)：极端大仰角强透视 (>32°) 下的单应性边缘拉伸
- **实测触发边界**：透视顶底压缩比 `>= 1.48`（约 `>= 32°` 仰角）。
- **工程护栏**：当顶底边缘透视压缩比 >= 1.48（倾角约 >= 32°）时触发强透视告警，自动降级为人工 4 角点精细拖拽标定模式，防止远端板缝过度畸变。

### Bad Case 02 (`BC-02-ABSTRACT-SALIENCE-NOISE`)：高度抽象平面/图形作品在构造轴 (tectonic_honesty) 上的显著度噪声
- **实测对比**：无门控均匀欧氏 Top-10 泄漏平面样本 `['graph_01']`；启用显著度门控后泄漏降至 `[]`。
- **工程护栏**：引入轴向显著度门控权重 s_i，对非建筑/扁平平面作品的 tectonic_honesty 权重自动衰减，避免抽象色块干扰构造检索排序。

### Bad Case 03 (`BC-03-UNPRICED-BESPOKE-SKU`)：非标异形定制构件缺失地区定额基准价 (bespoke_bronze_patina_unpriced)
- **实测验证**：返回状态 `UNKNOWN_PRICE_MISSING`，汇总状态 `PARTIAL_UNKNOWN_PRICE_MISSING`，成功拦截 0 值幻觉（`fabricated_zero_blocked=True`），同步触发规则 `[]`。
- **工程护栏**：tectonic_state.py 遇到 unit_cost_cny_sqm 与 lump_sum_cny 均为空时，严格返回 UNKNOWN_PRICE_MISSING 并置汇总状态为 PARTIAL_UNKNOWN_PRICE_MISSING，绝不静默置 0 误导甲方签约预算。
