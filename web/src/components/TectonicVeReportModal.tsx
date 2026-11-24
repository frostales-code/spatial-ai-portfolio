'use client';

import React, { useEffect } from 'react';
import { Download, Printer, X } from 'lucide-react';
import type {
  CadDetailDiagram,
  HomographyProjectionData,
  RelightMetricsData,
  TectonicAlert,
  TectonicCase,
  TectonicTierState,
  TectonicZoneState,
  VeProjectSummaryJson,
  ZoneCostBreakdown,
} from '../types/tectonic';

interface TectonicVeReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeCase: TectonicCase;
  rawTier: TectonicTierState;
  currentZones: TectonicZoneState[];
  currentCostBreakdowns: ZoneCostBreakdown[];
  currentAlerts: TectonicAlert[];
  currentSummary: VeProjectSummaryJson;
  targetImageUrl: string;
  relightMetrics: RelightMetricsData;
  homographyMetrics: HomographyProjectionData;
  activeCadDetail: CadDetailDiagram | null;
}

export const TectonicVeReportModal: React.FC<TectonicVeReportModalProps> = ({
  isOpen,
  onClose,
  activeCase,
  rawTier,
  currentZones,
  currentCostBreakdowns,
  currentAlerts,
  currentSummary,
  targetImageUrl,
  relightMetrics,
  homographyMetrics,
  activeCadDetail,
}) => {
  useEffect(() => {
    return () => {
      document.body.classList.remove('printing-ve-report');
    };
  }, []);

  if (!isOpen) return null;

  const rawCost = Number(rawTier.summary.known_subtotal_cny);
  const currentCost = Number(currentSummary.known_subtotal_cny);
  const savedCny = rawCost - currentCost;
  const savedPct = rawCost > 0 ? Math.round((savedCny / rawCost) * 100) : 0;
  const savedDays = rawTier.summary.max_lead_time_days - currentSummary.max_lead_time_days;

  const handlePrintPdf = () => {
    document.body.classList.add('printing-ve-report');
    setTimeout(() => {
      window.print();
      setTimeout(() => {
        document.body.classList.remove('printing-ve-report');
      }, 300);
    }, 60);
  };

  const handleDownloadMarkdown = () => {
    const lines: string[] = [
      `# 甲方价值工程（VE）深化对比任务书`,
      ``,
      `- **改造案例**：${activeCase.title}`,
      `- **场地说明**：${activeCase.site_context}`,
      `- **基准尺度锚点**：${activeCase.scale_anchor.label}`,
      `- **测算日期**：${currentZones[0]?.engineering_state.data_benchmark_date ?? '2026-11-23'}`,
      ``,
      `## 一、核心成本与工期变化`,
      `- **原始概念方案造价**：¥${rawCost.toLocaleString('en-US', { minimumFractionDigits: 2 })}（${rawTier.summary.max_lead_time_days} 天，${rawTier.summary.blocking_alerts_count} 项阻断隐患）`,
      `- **当前深化方案造价**：${currentSummary.has_missing_prices ? `部分缺价（已核价分项 ¥${currentCost.toLocaleString('en-US', { minimumFractionDigits: 2 })} + UNKNOWN_PRICE_MISSING）` : `¥${currentCost.toLocaleString('en-US', { minimumFractionDigits: 2 })}（区间 ¥${Number(currentSummary.low_estimate_cny).toLocaleString()} ~ ¥${Number(currentSummary.high_estimate_cny).toLocaleString()}）`}`,
      `- **现场工期变化**：${currentSummary.max_lead_time_days} 天（${savedDays >= 0 ? `缩短 ${savedDays} 天` : `增加 ${Math.abs(savedDays)} 天`}）`,
      `- **阻断级隐患数量**：${currentSummary.blocking_alerts_count} 项`,
      `- **几何投影与像素保真指标**：灭点角度偏离 ${homographyMetrics.vertical_vanishing_deviation_deg.toFixed(3)}°，非修改区域保真 PSNR = ${relightMetrics.non_mask_psnr_db.toFixed(2)} dB`,
      ``,
      `## 二、分区域定额清单 (Zero-LLM Decimal BOM)`,
      ``,
      `| 部位 | 选定构造体系 | 净工程量 | 损耗系数 | 含损耗量 | 小计 (CNY ±12%) |`,
      `| :--- | :--- | :--- | :--- | :--- | :--- |`,
    ];

    currentZones.forEach((zone, idx) => {
      const bd = currentCostBreakdowns[idx];
      const costText =
        bd.status === 'UNKNOWN_PRICE_MISSING'
          ? 'UNKNOWN_PRICE_MISSING'
          : `¥${Number(bd.material_and_substructure_cny).toLocaleString('en-US', { minimumFractionDigits: 2 })} (¥${Number(bd.low_estimate_cny).toLocaleString()}~¥${Number(bd.high_estimate_cny).toLocaleString()})`;
      lines.push(
        `| ${zone.zone_label} | ${zone.sku_name ?? zone.engineering_state.detail_drawing_code} | ${bd.net_area_sqm} | ${zone.engineering_state.wastage_factor} | ${bd.effective_area_with_wastage_sqm} | ${costText} |`,
      );
    });

    lines.push('', '## 三、物理建构排雷校验', '');
    if (currentAlerts.length === 0) {
      lines.push('- 全部区域均已消除超限尺幅、湿作业占道与防水泛水隐患，满足施工条件。');
    } else {
      for (const alert of currentAlerts) {
        lines.push(`- **[${alert.severity}] ${alert.code}**：${alert.message}（整改建议：${alert.remediation_hint}）`);
      }
    }

    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeCase.case_id}_ve_report.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ve-report-title"
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/65 backdrop-blur-[2px] flex items-center justify-center p-3 sm:p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="ve-print-sheet rounded-xl bg-card border border-border shadow-2xl w-full max-w-5xl max-h-[92vh] overflow-y-auto p-5 sm:p-8 space-y-6"
      >
        {/* Sheet Header */}
        <div className="flex flex-wrap items-start justify-between gap-4 pb-5 border-b border-border">
          <div className="space-y-1">
            <h2 id="ve-report-title" className="font-display text-xl sm:text-2xl font-extrabold text-foreground">
              甲方价值工程（VE）深化对比任务书
            </h2>
            <p className="text-xs text-muted-foreground">
              {activeCase.title} · {activeCase.scale_anchor.label} · 基准日期 {currentZones[0]?.engineering_state.data_benchmark_date ?? '2026-11-23'}
            </p>
          </div>
          <div className="flex items-center gap-2 print-hide">
            <button
              type="button"
              onClick={handleDownloadMarkdown}
              className="min-h-[40px] rounded-md px-3.5 border border-border hover:border-primary/60 text-xs font-semibold text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>下载 Markdown</span>
            </button>
            <button
              type="button"
              onClick={handlePrintPdf}
              className="min-h-[40px] rounded-md px-4 bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold inline-flex items-center gap-1.5 transition-colors"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>打印 / 另存 PDF</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭 VE 任务书预览"
              className="w-10 h-10 rounded-md border border-border hover:border-primary/60 text-foreground flex items-center justify-center transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Before / After Comparison Plates */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div className="space-y-2">
            <div className="aspect-[4/3] rounded-lg border border-border bg-secondary/60 overflow-hidden">
              <img src={rawTier.image_url} alt="原始概念立面方案" className="w-full h-full object-cover" />
            </div>
            <div className="flex items-baseline justify-between text-xs">
              <span className="font-semibold text-destructive">原始概念方案（存在建构与造价隐患）</span>
              <span className="mono text-muted-foreground">¥{rawCost.toLocaleString()}</span>
            </div>
          </div>
          <div className="space-y-2">
            <div className="aspect-[4/3] rounded-lg border border-primary bg-secondary/60 overflow-hidden">
              <img src={targetImageUrl} alt="当前深化落地立面方案" className="w-full h-full object-cover" />
            </div>
            <div className="flex items-baseline justify-between text-xs">
              <span className="font-semibold text-primary">当前深化方案（树影与环境光照锁定）</span>
              <span className="mono font-semibold text-foreground">
                {currentSummary.has_missing_prices
                  ? '存在 UNKNOWN_PRICE_MISSING 缺价项'
                  : `¥${currentCost.toLocaleString()}`}
              </span>
            </div>
          </div>
        </div>

        {/* Quantified Delta Matrix */}
        <div className="grid grid-cols-1 sm:grid-cols-3 rounded-lg overflow-hidden gap-px bg-border border border-border">
          <div className="bg-card p-4">
            <div className="text-xs text-muted-foreground">造价压降 / 状态对比</div>
            {currentSummary.has_missing_prices ? (
              <div className="mono text-sm font-bold text-destructive break-all mt-1">
                UNKNOWN_PRICE_MISSING
              </div>
            ) : (
              <div className="mono text-lg font-bold text-teal-ok tabular-nums mt-1">
                {savedCny >= 0 ? `节省 ¥${savedCny.toLocaleString()} (-${savedPct}%)` : `增加 ¥${Math.abs(savedCny).toLocaleString()}`}
              </div>
            )}
          </div>
          <div className="bg-card p-4">
            <div className="text-xs text-muted-foreground">现场工期与施工可行性</div>
            <div className="mono text-lg font-bold text-foreground tabular-nums mt-1">
              {currentSummary.max_lead_time_days} 天（{savedDays >= 0 ? `缩短 ${savedDays} 天` : `+${Math.abs(savedDays)} 天`}）
            </div>
          </div>
          <div className="bg-card p-4">
            <div className="text-xs text-muted-foreground">建构隐患与几何保真校验</div>
            <div className="mono text-base font-bold text-primary tabular-nums mt-1">
              阻断 {currentSummary.blocking_alerts_count} 项 · 灭点误差 {homographyMetrics.vertical_vanishing_deviation_deg.toFixed(2)}° · PSNR {relightMetrics.non_mask_psnr_db.toFixed(1)} dB
            </div>
          </div>
        </div>

        {/* Zero-LLM Decimal BOM Table */}
        <div className="space-y-3">
          <h3 className="font-display text-base font-bold text-foreground">
            分区域定额工程量与造价对比表（Zero-LLM Decimal 计算）
          </h3>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[660px] text-left border-collapse text-xs">
              <thead>
                <tr className="bg-secondary/60 border-b border-border text-foreground font-semibold">
                  <th className="py-2.5 px-3">区域部位</th>
                  <th className="py-2.5 px-3">选定工艺体系</th>
                  <th className="py-2.5 px-3">净量 / 含损耗</th>
                  <th className="py-2.5 px-3">标准节点</th>
                  <th className="py-2.5 px-3">确定性造价 (±12% 区间)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {currentZones.map((zone, idx) => {
                  const bd = currentCostBreakdowns[idx];
                  const isMissing = bd.status === 'UNKNOWN_PRICE_MISSING';
                  return (
                    <tr key={zone.zone_id}>
                      <td className="py-3 px-3 font-semibold text-foreground">{zone.zone_label}</td>
                      <td className="py-3 px-3 text-muted-foreground">{zone.sku_name ?? zone.engineering_state.detail_drawing_code}</td>
                      <td className="py-3 px-3 mono tabular-nums text-foreground">
                        {bd.net_area_sqm} → {bd.effective_area_with_wastage_sqm} (×{zone.engineering_state.wastage_factor})
                      </td>
                      <td className="py-3 px-3 mono text-primary">{zone.engineering_state.detail_drawing_code}</td>
                      <td className="py-3 px-3 mono tabular-nums">
                        {isMissing ? (
                          <span className="font-semibold text-destructive">UNKNOWN_PRICE_MISSING</span>
                        ) : (
                          <div>
                            <div className="font-semibold text-foreground">
                              ¥{Number(bd.material_and_substructure_cny).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                            </div>
                            <div className="text-muted-foreground">
                              ¥{Number(bd.low_estimate_cny).toLocaleString()} ~ ¥{Number(bd.high_estimate_cny).toLocaleString()}
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Active CAD Detail & Constructability Conclusion */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-start pt-2 border-t border-border">
          <div className="md:col-span-6 space-y-2">
            <div className="text-xs font-bold text-foreground">
              主墙体匹配标准构造节点详图（{activeCadDetail?.code ?? currentZones[0]?.engineering_state.detail_drawing_code}）
            </div>
            {activeCadDetail?.svg && (
              <div className="rounded-lg border border-border bg-secondary/40 p-2 [&_svg]:w-full [&_svg]:h-auto [&_svg]:block">
                <div dangerouslySetInnerHTML={{ __html: activeCadDetail.svg }} />
              </div>
            )}
          </div>
          <div className="md:col-span-6 space-y-2 text-xs">
            <div className="text-xs font-bold text-foreground">物理建构排雷核验结论</div>
            {currentAlerts.length === 0 ? (
              <div className="rounded-lg p-3.5 border border-teal-ok bg-card text-teal-ok leading-relaxed">
                当前所有立面区域均已通过《常见饰面极限制造尺幅与构造禁忌》检查，具备全干法快速装配与安全防潮泛水条件。
              </div>
            ) : (
              <div className="space-y-2">
                {currentAlerts.map((a, idx) => (
                  <div key={idx} className="rounded-lg p-3 border border-destructive bg-card text-destructive space-y-1">
                    <div className="font-semibold mono">
                      [{a.severity}] {a.code}
                    </div>
                    <p className="text-foreground">{a.message}</p>
                    <p className="text-muted-foreground">建议：{a.remediation_hint}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
