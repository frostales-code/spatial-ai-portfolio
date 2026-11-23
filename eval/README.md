# EDD Evaluation Suite Specification (Milestone M4)

本目录用于存放四大离线量化评测脚本与 Golden Benchmark 数据集，把《Product Thesis》中的目标值变成**可复现、带 Bad Case 拆解的实测数据**（用于面试深挖与 Tab 03 看板展示）。

## 四大评测脚本规划

| 脚本 | 评测维度 | Baseline | Target V1.0 | 数据集与验收方法 |
| :--- | :--- | :--- | :--- | :--- |
| `eval_01_spearman.py` | **VLM 光谱打标一致性 & 跨媒介召回率** | 无锚点直接打分 `ρ = 0.54`；CLIP 跨界召回 `31%` | `ρ >= 0.86`；Top-5 跨界同构有效率 `>= 82%` | 40+ 张多门类锚点基准图多次运行排序一致性 + 模糊查询盲评 |
| `eval_02_decouple.py` | **多参考图正交混音忠实度** | 多图直喂 IP-Adapter `45%` | `>= 85%` | 20 组三图正交混搭任务，VLM-as-a-Judge 独立盲评三槽位达成率 |
| `eval_03_homography.py` | **透视分缝灭点误差 & 非修改区保真度** | 纯 Prompt 间距方差 `>40%` | 透视角度误差 `< 1.5°`；Mask 外 `PSNR >= 38 dB` | 基于 `pipeline/homography_seam.py` 自动化重投影几何误差 + 图像差分测试 |
| `eval_04_cost_backtest.py` | **综合单方造价区间命中率** | 人工深化询价耗时 `2~3 天` | `>= 80%` 落在 `±15%` 区间（`<15s`） | 12~20 个已竣工商业门头/精品餐饮历史结算单回测 |

## AI PM 面试加分项：Bad Case 分类框架

在运行评测后，必须在报告中明确记录以下 3 类典型失败案例及工程护栏策略：
1. **极端强透视大仰角下的单应性边缘拉伸** → 设定倾角阈值告警与人工 4 点微调回退；
2. **高度抽象图形作品在 `tectonic_honesty` 轴上的显著度误判** → 依靠显著度门控权重 $s_i \to 0$ 抑制噪声；
3. **非标异形定制构件缺失地区定额基准价** → `tectonic_state.py` 强制返回 `UNKNOWN_PRICE_MISSING`，绝不置 `0` 误导预算。
