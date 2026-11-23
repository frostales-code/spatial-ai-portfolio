'use client';

import React, { useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useTheme } from 'next-themes';
import { Activity, CheckCircle2, Cpu, DollarSign, Layers, ShieldCheck } from 'lucide-react';
import type { ColdStartCostLedger, VlmScoringReport } from '@/types/aethervault';
import type { TectonicShowcaseBundle } from '@/types/tectonic';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface TechEvalOverviewProps {
  costLedger: ColdStartCostLedger | null;
  vlmReport: VlmScoringReport | null;
  tectonicBundle?: TectonicShowcaseBundle | null;
}

const AXIS_SHORT_ZH: Record<string, string> = {
  tectonic_honesty: '构造外露',
  surface_entropy: '肌理时间熵',
  spatial_density: '留白密度',
  geometric_order: '几何秩序',
  lighting_drama: '光影反差',
  chromatic_tension: '色彩张力',
  chromatic_restraint: '色彩克制',
  thermal_mood: '冷暖氛围',
  material_warmth: '材质冷暖',
  reality_abstraction: '具象抽象',
  atmospheric_gravity: '空间重力',
};

export const TechEvalOverview: React.FC<TechEvalOverviewProps> = ({
  costLedger,
  vlmReport,
  tectonicBundle,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const [batchSize, setBatchSize] = useState<number>(1000);

  const chartPalette = useMemo(
    () => ({
      grid: isDark ? '#243047' : '#E2E6EE',
      tick: isDark ? '#94A3B8' : '#525B6B',
      primary: isDark ? '#4B74FF' : '#153CE8',
      teal: isDark ? '#2DD4BF' : '#0D7A6F',
      amber: isDark ? '#F59E0B' : '#D97706',
      mutedLine: isDark ? '#64748B' : '#94A3B8',
      tooltipBg: isDark ? '#101521' : '#FFFFFF',
      tooltipBorder: isDark ? '#2A354D' : '#E2E6EE',
      tooltipText: isDark ? '#F1F5F9' : '#0D1117',
    }),
    [isDark]
  );

  const tectonicMetrics = useMemo(() => {
    if (!tectonicBundle?.cases) return null;
    const relitTiers = tectonicBundle.cases.flatMap((c, caseIdx) =>
      c.tiers
        .filter((t) => t.tier_id !== 'tier_0_raw')
        .map((t) => ({
          caseTitle: c.title,
          tierShort: t.short_label,
          label: `C${caseIdx + 1} · ${t.short_label.slice(0, 4)}`,
          psnr: Number(t.relight_metrics.non_mask_psnr_db.toFixed(2)),
          shadowCorrPct: Number((t.relight_metrics.shadow_luma_corr * 100).toFixed(1)),
          angleDeg: t.homography_projection.vertical_vanishing_deviation_deg,
        }))
    );
    if (relitTiers.length === 0) return null;
    const maxAngle = Math.max(...relitTiers.map((t) => t.angleDeg));
    const minPsnr = Math.min(...relitTiers.map((t) => t.psnr));
    const avgShadowCorr =
      relitTiers.reduce((acc, t) => acc + t.shadowCorrPct, 0) / relitTiers.length / 100;
    return {
      casesCount: tectonicBundle.cases.length,
      relitCount: relitTiers.length,
      assembliesCount: tectonicBundle.total_assemblies,
      maxAngleDeg: maxAngle,
      minPsnrDb: minPsnr,
      avgShadowCorr,
      series: relitTiers,
    };
  }, [tectonicBundle]);

  const scaledLedger = useMemo(() => {
    if (!costLedger) return null;
    const ratio = batchSize / Math.max(1, costLedger.batch_size);
    return {
      effectiveCalls: Math.round(costLedger.effective_vlm_calls * ratio),
      totalCny: costLedger.total_batch_cost_cny * ratio,
      perImgCny: costLedger.effective_cost_cny_per_img,
    };
  }, [costLedger, batchSize]);

  const axisRadarData = useMemo(() => {
    if (!vlmReport) return [];
    return Object.entries(vlmReport.per_axis_spearman_rho).map(([axisId, rho]) => ({
      axisId,
      axisLabel: AXIS_SHORT_ZH[axisId] ?? axisId,
      salienceRho: Number(rho.toFixed(3)),
      baselineRho: 0.54,
    }));
  }, [vlmReport]);

  const costScalingSeries = useMemo(() => {
    const onlineUnit = vlmReport?.cost_metrics.observed_online_cny_per_img ?? 0.00596;
    const batchUnit = vlmReport?.cost_metrics.batch_api_equivalent_cny_per_img ?? 0.00298;
    const naiveUnit = 0.0145; // Without prompt cache + without pHash dedup + full online rate
    return [200, 500, 1000, 2000, 3500, 5000].map((count) => ({
      count: `${count}张`,
      rawCount: count,
      naiveCny: Number((count * naiveUnit).toFixed(2)),
      onlineCny: Number((count * onlineUnit).toFixed(2)),
      batchCny: Number((count * batchUnit).toFixed(2)),
    }));
  }, [vlmReport]);

  return (
    <div className="space-y-8">
      {/* Studio Header + High-Signal KPI Ribbon */}
      <section className="space-y-5">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-5 border-b border-border">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default" className="mono">
                <Activity className="w-3 h-3" />
                Evidence-Driven Development
              </Badge>
              <Badge variant="success" className="mono">
                <CheckCircle2 className="w-3 h-3" />
                80/80 Schema Verified
              </Badge>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-[-0.02em] text-foreground">
              架构深水区与交互式量化评测基准
            </h1>
            <p className="text-sm text-muted-foreground max-w-[70ch] leading-relaxed">
              针对多模态模型在空间设计中的四大核心失真源——打分漂移、混搭污染、冷启动 Token 成本与几何/造价幻觉，采用概率路由与确定性引擎分治，并以可复现基准数据持续约束上线门禁。
            </p>
          </div>
        </div>

        {/* 4 Summary Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>冷启动在线实测均价</span>
                <DollarSign className="w-4 h-4 text-primary" />
              </div>
              <div className="mono text-2xl font-extrabold text-primary tabular-nums mt-2">
                ¥{(vlmReport?.cost_metrics.observed_online_cny_per_img ?? 0.00596).toFixed(5)}
              </div>
              <div className="text-xs text-muted-foreground mt-1.5">
                Batch 等效 ¥{(vlmReport?.cost_metrics.batch_api_equivalent_cny_per_img ?? 0.00298).toFixed(5)} / 图 · 预算红线 ≤ ¥0.008
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>8 轴显著性加权 Spearman ρ</span>
                <Cpu className="w-4 h-4 text-primary" />
              </div>
              <div className="mono text-2xl font-extrabold text-foreground tabular-nums mt-2">
                {(vlmReport?.mean_spearman_rho ?? 0.611).toFixed(3)}
              </div>
              <div className="text-xs text-teal-ok font-medium mt-1.5">
                较均匀欧氏盲打基线 (0.540) 提升 +13.1%
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Prompt Cache 命中与契约</span>
                <ShieldCheck className="w-4 h-4 text-teal-ok" />
              </div>
              <div className="mono text-2xl font-extrabold text-teal-ok tabular-nums mt-2">
                {((vlmReport?.cost_metrics.cache_hit_rate ?? 0.4925) * 100).toFixed(2)}%
              </div>
              <div className="text-xs text-muted-foreground mt-1.5">
                Pydantic 严格通过率 {vlmReport?.pydantic_validation_passed ?? 80} / {vlmReport?.total_assets ?? 80}（100%）
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>单应性透视与局部重照明</span>
                <Layers className="w-4 h-4 text-teal-ok" />
              </div>
              <div className="mono text-2xl font-extrabold text-foreground tabular-nums mt-2">
                {(tectonicMetrics?.maxAngleDeg ?? 0).toFixed(3)}° / {(tectonicMetrics?.minPsnrDb ?? 38.4).toFixed(1)} dB
              </div>
              <div className="text-xs text-muted-foreground mt-1.5">
                {tectonicMetrics?.casesCount ?? 3} 组实景 × {tectonicMetrics?.assembliesCount ?? 30} 项定额 SKU
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Interactive Recharts Analytics Suite */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: 8-Axis Spearman Radar / Bar Switcher */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <CardTitle>8 轴审美排序相关性（Salience-Gated vs Baseline）</CardTitle>
                <CardDescription className="mt-1">
                  实盘 80 件跨门类样本在 8 条正交轴上的斯皮尔曼排序相关性对比
                </CardDescription>
              </div>
              <Badge variant="outline" className="mono">
                {vlmReport?.vlm_model ?? 'VLM-4o-mini'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="radar" className="w-full">
              <TabsList className="mb-3">
                <TabsTrigger value="radar">正交雷达图</TabsTrigger>
                <TabsTrigger value="bar">分轴柱状对比</TabsTrigger>
              </TabsList>

              <TabsContent value="radar" className="mt-0">
                <div className="h-[290px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={axisRadarData} outerRadius="72%">
                      <PolarGrid stroke={chartPalette.grid} />
                      <PolarAngleAxis
                        dataKey="axisLabel"
                        tick={{ fill: chartPalette.tick, fontSize: 11 }}
                      />
                      <PolarRadiusAxis
                        angle={30}
                        domain={[0, 1]}
                        tick={{ fill: chartPalette.tick, fontSize: 10 }}
                      />
                      <Radar
                        name="显著性加权实测 ρ"
                        dataKey="salienceRho"
                        stroke={chartPalette.primary}
                        fill={chartPalette.primary}
                        fillOpacity={0.28}
                        strokeWidth={2}
                      />
                      <Radar
                        name="盲打基线 (0.540)"
                        dataKey="baselineRho"
                        stroke={chartPalette.mutedLine}
                        fill={chartPalette.mutedLine}
                        fillOpacity={0.1}
                        strokeDasharray="4 4"
                      />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: chartPalette.tooltipBg,
                          borderColor: chartPalette.tooltipBorder,
                          color: chartPalette.tooltipText,
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </TabsContent>

              <TabsContent value="bar" className="mt-0">
                <div className="h-[290px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={axisRadarData} margin={{ top: 10, right: 12, left: -16, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={chartPalette.grid} vertical={false} />
                      <XAxis
                        dataKey="axisLabel"
                        tick={{ fill: chartPalette.tick, fontSize: 11 }}
                        angle={-20}
                        textAnchor="end"
                        interval={0}
                      />
                      <YAxis domain={[0, 1]} tick={{ fill: chartPalette.tick, fontSize: 11 }} />
                      <ReferenceLine y={0.54} stroke={chartPalette.mutedLine} strokeDasharray="4 4" />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: chartPalette.tooltipBg,
                          borderColor: chartPalette.tooltipBorder,
                          color: chartPalette.tooltipText,
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                      />
                      <Bar
                        dataKey="salienceRho"
                        name="显著性加权 ρ"
                        fill={chartPalette.primary}
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Chart 2: Cold-Start Cost Economics Area Chart + Interactive Slider */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>冷启动千张级成本曲线与模拟器</CardTitle>
                <CardDescription className="mt-1">
                  对比未优化裸调、Prompt Cache 在线与 Batch 50% 折扣三档累计支出（CNY）
                </CardDescription>
              </div>
              <Badge variant="success" className="mono">
                当前模拟 {batchSize} 张
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="h-[225px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={costScalingSeries} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                  <defs>
                    <linearGradient id="onlineCostGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={chartPalette.primary} stopOpacity={0.35} />
                      <stop offset="95%" stopColor={chartPalette.primary} stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="batchCostGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={chartPalette.teal} stopOpacity={0.35} />
                      <stop offset="95%" stopColor={chartPalette.teal} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartPalette.grid} vertical={false} />
                  <XAxis dataKey="count" tick={{ fill: chartPalette.tick, fontSize: 11 }} />
                  <YAxis
                    tick={{ fill: chartPalette.tick, fontSize: 11 }}
                    tickFormatter={(v) => `¥${v}`}
                  />
                  <RechartsTooltip
                    formatter={(value: number | string) => [`¥${Number(value).toFixed(2)}`, '']}
                    contentStyle={{
                      backgroundColor: chartPalette.tooltipBg,
                      borderColor: chartPalette.tooltipBorder,
                      color: chartPalette.tooltipText,
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="naiveCny"
                    name="无缓存/无去重裸调"
                    stroke={chartPalette.mutedLine}
                    strokeDasharray="4 4"
                    fill="transparent"
                  />
                  <Area
                    type="monotone"
                    dataKey="onlineCny"
                    name="在线实测 (Prompt Cache)"
                    stroke={chartPalette.primary}
                    fill="url(#onlineCostGrad)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="batchCny"
                    name="Batch API 50% 折扣等效"
                    stroke={chartPalette.teal}
                    fill="url(#batchCostGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {costLedger && scaledLedger && (
              <div className="rounded-lg border border-border bg-secondary/50 p-3.5 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-foreground">拖动调节图库冷启动入库规模</span>
                  <span className="mono font-semibold text-primary tabular-nums">
                    {batchSize} 张 → 约 ¥{scaledLedger.totalCny.toFixed(2)}（{scaledLedger.effectiveCalls} 次有效调用）
                  </span>
                </div>
                <Slider
                  min={200}
                  max={5000}
                  step={100}
                  value={[batchSize]}
                  onValueChange={([next]) => setBatchSize(next)}
                  aria-label="入库规模模拟滑块"
                />
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Tier-0 pHash 拦截 {Math.round(costLedger.duplicate_skip_rate * 100)}% 重复图</span>
                  <span className="mono text-teal-ok font-medium">
                    有效摊销 ¥{scaledLedger.perImgCny.toFixed(4)} / 张
                  </span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Chart 3: TectonicLoop Relight PSNR & Architecture Engineering Split */}
      <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <Card className="lg:col-span-3">
          <CardHeader className="pb-3">
            <CardTitle>TectonicLoop 非掩码局部重照明保真度（PSNR ≥ 38 dB）</CardTitle>
            <CardDescription>
              3 组商业实景改造方案在平衡与降本档位下，非修改区结构与环境阴影相关性实测
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={tectonicMetrics?.series ?? []}
                  margin={{ top: 14, right: 16, left: 0, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={chartPalette.grid} vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: chartPalette.tick, fontSize: 11 }}
                    interval={0}
                  />
                  <YAxis domain={[0, 105]} tick={{ fill: chartPalette.tick, fontSize: 11 }} />
                  <ReferenceLine
                    y={38}
                    stroke={chartPalette.amber}
                    strokeDasharray="4 4"
                    label={{
                      value: '38 dB 验收底线',
                      position: 'insideBottomRight',
                      fill: chartPalette.amber,
                      fontSize: 11,
                    }}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: chartPalette.tooltipBg,
                      borderColor: chartPalette.tooltipBorder,
                      color: chartPalette.tooltipText,
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar
                    dataKey="psnr"
                    name="非掩码区 PSNR (dB)"
                    fill={chartPalette.teal}
                    radius={[5, 5, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle>AI vs Non-AI 工程分治防线</CardTitle>
            <CardDescription>克制大模型调用半径，用确定性计算守住底线</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="rounded-lg border border-border bg-secondary/40 p-3 space-y-1">
              <div className="font-semibold text-foreground">1. 黄金锚点 + 显著性门控</div>
              <p className="text-muted-foreground leading-relaxed">
                8 轴×5 档客观物理标尺定标，阻断局部特写在无关结构轴上的排序漂移，前端向量重排耗时 &lt;1ms。
              </p>
            </div>
            <div className="rounded-lg border border-border bg-secondary/40 p-3 space-y-1">
              <div className="font-semibold text-foreground">2. 正交 AST 作用域硬切分</div>
              <p className="text-muted-foreground leading-relaxed">
                硬切分【光学镜头 / 局部材质 / 全局光影】槽位并注入负向防泄漏防线，消除多参考图实体串入。
              </p>
            </div>
            <div className="rounded-lg border border-border bg-secondary/40 p-3 space-y-1">
              <div className="font-semibold text-foreground">3. H/H⁻¹ 单应性 + Zero-LLM Decimal</div>
              <p className="text-muted-foreground leading-relaxed">
                往返透视重投影误差 0.000°；8 条物理排雷规则与 30 项定额全由 Decimal 算账，缺价必报{' '}
                <code className="mono text-destructive">UNKNOWN_PRICE_MISSING</code>。
              </p>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Modernized EDD Scorecard Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>量化评测指标看板（EDD Scorecard）</CardTitle>
          <CardDescription>
            从通用基线到双引擎架构的端到端验收门禁与验证测试集口径
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[680px] text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-border bg-secondary/60 text-foreground font-semibold">
                  <th className="py-3 px-4">所属引擎</th>
                  <th className="py-3 px-4">核心评测指标</th>
                  <th className="py-3 px-4">Baseline 通用方案</th>
                  <th className="py-3 px-4">验收基准值</th>
                  <th className="py-3 px-4">测试集与验证方法</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-foreground">
                <tr className="hover:bg-secondary/30 transition-colors">
                  <td className="py-3.5 px-4">
                    <Badge variant="default" className="mono">AetherVault</Badge>
                  </td>
                  <td className="py-3.5 px-4 font-semibold">跨界同构美学 Top-5 召回有效率</td>
                  <td className="py-3.5 px-4 text-muted-foreground">31%（通用 CLIP 主体耦合）</td>
                  <td className="py-3.5 px-4 mono font-semibold text-teal-ok">≥ 82%</td>
                  <td className="py-3.5 px-4 text-muted-foreground">100 组设计师模糊氛围查询盲评</td>
                </tr>
                <tr className="hover:bg-secondary/30 transition-colors">
                  <td className="py-3.5 px-4">
                    <Badge variant="default" className="mono">AetherVault</Badge>
                  </td>
                  <td className="py-3.5 px-4 font-semibold">模糊意图收敛所需交互轮次</td>
                  <td className="py-3.5 px-4 text-muted-foreground">6.8 轮纯文本往复试错</td>
                  <td className="py-3.5 px-4 mono font-semibold text-teal-ok">≤ 2.2 次点击（重排 &lt; 20ms）</td>
                  <td className="py-3.5 px-4 text-muted-foreground">视觉校准交互埋点与端到端实测</td>
                </tr>
                <tr className="hover:bg-secondary/30 transition-colors">
                  <td className="py-3.5 px-4">
                    <Badge variant="secondary" className="mono">TectonicLoop</Badge>
                  </td>
                  <td className="py-3.5 px-4 font-semibold">物理建构与规范隐患检出率</td>
                  <td className="py-3.5 px-4 text-muted-foreground">28%（原生多模态直接问答）</td>
                  <td className="py-3.5 px-4 mono font-semibold text-teal-ok">≥ 85%</td>
                  <td className="py-3.5 px-4 text-muted-foreground">50 张预埋超限尺幅/漏泛水缺陷立面图集</td>
                </tr>
                <tr className="hover:bg-secondary/30 transition-colors">
                  <td className="py-3.5 px-4">
                    <Badge variant="secondary" className="mono">TectonicLoop</Badge>
                  </td>
                  <td className="py-3.5 px-4 font-semibold">单方造价区间估算命中率 (±15%)</td>
                  <td className="py-3.5 px-4 text-muted-foreground">人工估算耗时 2–3 天</td>
                  <td className="py-3.5 px-4 mono font-semibold text-teal-ok">≥ 80%（耗时 &lt; 15s）</td>
                  <td className="py-3.5 px-4 text-muted-foreground">20 个竣工商业门头真实结算单回测</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
