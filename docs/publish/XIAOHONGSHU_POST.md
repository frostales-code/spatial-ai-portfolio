# 《当甲方把 18 万清水混凝土门头预算砍到 7 万，我用自研 AI 10 秒重画了干挂板拼缝和节点表》

> 发布前事实核对：标题中的 18 万→7 万是预算情境，10 秒为创意标题说法，仓库未提供端到端 10 秒计时证据。建议发布标题改为「当门头预算被大幅压缩，我做了一个能重画拼缝并检查节点的空间 AI 双引擎」。Case 01 的已知小计为 ¥204,169 → ¥43,181.40 → ¥29,900，并非 18 万→7 万的实测结算。

## 封面钩子

画面：Case 01 原始概念和 Tier 2 左右对照，叠加细线拼缝与「效果图 → 构造 → 造价」。素材：`web/public/assets/tectonic_cases/case_01_corner_cafe_tier_0_raw.webp` 和 `case_01_corner_cafe_tier_2_value.webp`。角标注明「方案测算，非结算报价」。

## 六页轮播

1. **预算被砍，设计还能落地吗？** Case 01 Tier 0 原图；点出概念与施工之间的鸿沟。
2. **把效果图拆成真实构造。** Case 01 Tier 1 与 Tier 2；说明预制干挂、模数与节点不同。
3. **拼缝要遵循透视。** Case 01 Tier 2，叠加 `tectonic_showcase_v1.json` 的 H/H⁻¹ 拼缝，强调平面适用范围。
4. **换一类门店再看一次。** Case 02 Tier 0 / Tier 2：`case_02_concept_boutique_tier_0_raw.webp`、`case_02_concept_boutique_tier_2_value.webp`。
5. **老街茶馆也能比较方案。** Case 03 Tier 0 / Tier 2：`case_03_oldstreet_teahouse_tier_0_raw.webp`、`case_03_oldstreet_teahouse_tier_2_value.webp`。
6. **灵感也需要边界。** `web/public/assets/ast_comparisons/cmp_01_naive.webp` / `cmp_01_ast.webp`：多图直混与作用域隔离对照；附在线体验链接。

## 正文

做商业空间方案时，最难的往往不是出第一张效果图，而是预算变化后，怎么把它变成能讨论、能施工的方案。

我做了一个空间 AI 双引擎：AetherVault 把材质、光影等灵感分别约束，减少多图混合时的实体串入；TectonicLoop 把立面映射到施工 SKU、规则、拼缝和造价。

街角咖啡馆案例里，仓库模型的三个方案已知小计分别为 ¥204,169、¥43,181.40 和 ¥29,900。它们是不同构造方案的测算，不是实际签约报价。15 个历史结算回测中，13 个落在 ±15% 区间；缺单价时系统直接提示 `UNKNOWN_PRICE_MISSING`。

体验：[在线 Showcase](https://frostales-code.github.io/spatial-ai-portfolio/)｜[开源仓库](https://github.com/frostales-code/spatial-ai-portfolio)

## 评论区互动

- 你最常遇到的「效果图好看、施工很难」节点是什么？
- 当预算被压缩，你会先换材料、缩面积还是改构造？
- 哪种缺失信息会让你拒绝给出报价？

#空间设计 #商业空间 #建筑设计 #AI产品经理 #设计工具 #价值工程 #独立开发
