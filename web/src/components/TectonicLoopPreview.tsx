'use client';

import React, { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  AlertTriangle,
  BookOpen,
  Box,
  Check,
  Crosshair,
  FileText,
  Info,
  X,
} from 'lucide-react';
import {
  buildZoneFromSku,
  evaluateZonesClient,
} from '../engine/tectonicCostEngine';
import type {
  TectonicShowcaseBundle,
  TectonicTierState,
} from '../types/tectonic';
import { BeforeAfterSlider } from './BeforeAfterSlider';
import { CadDetailViewer } from './CadDetailViewer';
import { LiveHomographyCalibrator } from './LiveHomographyCalibrator';
import { TectonicVeReportModal } from './TectonicVeReportModal';
import { trackShowcaseEvent } from '../utils/analytics';

const TectonicPlane3D = dynamic(
  () => import('./three/TectonicPlane3D').then((m) => m.TectonicPlane3D),
  {
    ssr: false,
    loading: () => (
      <div className="h-[440px] rounded-lg border border-border bg-card flex items-center justify-center text-xs text-muted-foreground">
        正在初始化 Three.js 3D 单应性投影平面...
      </div>
    ),
  }
);

interface TectonicLoopPreviewProps {
  tectonicBundle: TectonicShowcaseBundle | null;
  isLiveEngine: boolean;
}

const FALLBACK_SEAM_COLORS = {
  stroke: '#153CE8',
};

export const TectonicLoopPreview: React.FC<TectonicLoopPreviewProps> = ({
  tectonicBundle,
  isLiveEngine,
}) => {
  const cases = tectonicBundle?.cases ?? [];
  const assemblies = tectonicBundle?.assemblies ?? [];
  const lintRules = tectonicBundle?.lint_rules ?? [];
  const cadDetails = tectonicBundle?.cad_details ?? {};

  const [selectedCaseId, setSelectedCaseId] = useState<string>('case_01_corner_cafe');
  const [selectedTierId, setSelectedTierId] = useState<TectonicTierState['tier_id']>('tier_1_balanced');
  const [customSkus, setCustomSkus] = useState<Record<string, string>>({});

  const [viewportMode, setViewportMode] = useState<'photoreal' | 'orthographic' | '3d'>('photoreal');
  const [showSeams, setShowSeams] = useState(true);
  const [showPins, setShowPins] = useState(true);
  const [selectedPinIndex, setSelectedPinIndex] = useState(0);

  const [veReportOpen, setVeReportOpen] = useState(false);
  const [catalogModalOpen, setCatalogModalOpen] = useState(false);
  const [calibratorOpen, setCalibratorOpen] = useState(false);
  const [catalogTab, setCatalogTab] = useState<'assemblies' | 'rules'>('assemblies');

  const [liveVeLoading, setLiveVeLoading] = useState(false);
  const [liveVeStatus, setLiveVeStatus] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (veReportOpen) setVeReportOpen(false);
        else if (catalogModalOpen) setCatalogModalOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [veReportOpen, catalogModalOpen]);

  const activeCase = useMemo(
    () => cases.find((c) => c.case_id === selectedCaseId) ?? cases[0] ?? null,
    [cases, selectedCaseId],
  );

  const rawTier = useMemo(
    () => activeCase?.tiers.find((t) => t.tier_id === 'tier_0_raw') ?? activeCase?.tiers[0] ?? null,
    [activeCase],
  );

  const activePresetTier = useMemo(
    () =>
      activeCase?.tiers.find((t) => t.tier_id === selectedTierId) ??
      activeCase?.tiers[1] ??
      activeCase?.tiers[0] ??
      null,
    [activeCase, selectedTierId],
  );

  const skuById = useMemo(() => {
    const map: Record<string, (typeof assemblies)[number]> = {};
    for (const s of assemblies) map[s.sku_id] = s;
    return map;
  }, [assemblies]);

  const effectiveZones = useMemo(() => {
    if (!activePresetTier) return [];
    return activePresetTier.zones.map((z) => {
      const overrideSkuId = customSkus[z.zone_id];
      if (overrideSkuId && skuById[overrideSkuId]) {
        return buildZoneFromSku(z, skuById[overrideSkuId]);
      }
      return z;
    });
  }, [activePresetTier, customSkus, skuById]);

  const evalResult = useMemo(
    () => evaluateZonesClient(effectiveZones),
    [effectiveZones],
  );

  const hasCustomOverride = Object.keys(customSkus).length > 0;

  // Diagnostic markers anchored cleanly per zone
  const diagnosticMarkers = useMemo(() => {
    const pins = activeCase?.geometry?.diagnostic_pins_pct ?? [
      { zone_id: 'facade_wall_01', x_pct: 50, y_pct: 28 },
      { zone_id: 'glazing_portal_02', x_pct: 60, y_pct: 68 },
      { zone_id: 'edge_weather_03', x_pct: 20, y_pct: 90 },
    ];
    return effectiveZones.map((zone, idx) => {
      const pin = pins[idx] ?? { zone_id: zone.zone_id, x_pct: 30 + idx * 20, y_pct: 40 + idx * 15 };
      const zoneAlerts = evalResult.alerts.filter((a) => a.zone_id === zone.zone_id);
      const hasBlocking = zoneAlerts.some((a) => a.severity === 'BLOCKING');
      const hasAnyAlert = zoneAlerts.length > 0;
      const bd = evalResult.costBreakdowns[idx];
      return {
        zone,
        pin,
        alerts: zoneAlerts,
        hasBlocking,
        hasAnyAlert,
        breakdown: bd,
      };
    });
  }, [activeCase, effectiveZones, evalResult]);

  const activeMarker = diagnosticMarkers[selectedPinIndex] ?? diagnosticMarkers[0] ?? null;

  const wallZone = effectiveZones[0] ?? null;
  const wallCadCode = wallZone?.engineering_state.detail_drawing_code ?? 'STD-FAC-UHPC-04';
  const activeCadDetail = cadDetails[wallCadCode] ?? null;

  const skusByCategory = useMemo(() => {
    return {
      wall_cladding: assemblies.filter((s) => s.category === 'wall_cladding'),
      glazing_portal: assemblies.filter((s) => s.category === 'glazing_portal'),
      edge_weatherproofing: assemblies.filter((s) => s.category === 'edge_weatherproofing'),
    };
  }, [assemblies]);

  const handleSelectCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    setSelectedTierId('tier_1_balanced');
    setCustomSkus({});
    setSelectedPinIndex(0);
    setLiveVeStatus(null);
    trackShowcaseEvent('tectonic_case_switch', { case_id: caseId });
  };

  const handleSelectTier = (tierId: TectonicTierState['tier_id']) => {
    setSelectedTierId(tierId);
    setCustomSkus({});
    setLiveVeStatus(null);
    trackShowcaseEvent('tectonic_tier_switch', { tier_id: tierId, case_id: selectedCaseId });
  };

  const handleLiveBackendVeCalc = async () => {
    if (effectiveZones.length === 0) return;
    setLiveVeLoading(true);
    try {
      const payload = effectiveZones.map((z) => ({
        zone_id: z.zone_id,
        zone_label: z.zone_label,
        visual_binding: {
          sam_mask_ref: z.visual_binding.sam_mask_ref,
          perspective_plane_normal: z.visual_binding.perspective_plane_normal,
          estimated_area_sqm: z.visual_binding.estimated_area_sqm,
          max_continuous_span_m: z.visual_binding.max_continuous_span_m,
          is_curved_geometry: z.visual_binding.is_curved_geometry,
        },
        engineering_state: z.engineering_state,
      }));
      const res = await fetch('/api/tectonic/calc-ve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const s = data.summary;
      setLiveVeStatus({
        ok: true,
        message:
          s?.has_missing_prices
            ? `Live FastAPI Zero-LLM 核算完成：检出 ${data.blocking_alerts_count} 项阻断预警，含缺价分项（${s.cost_status}）。`
            : `Live FastAPI Zero-LLM 核算完成：阻断预警 ${data.blocking_alerts_count} 项，汇总净额 ¥${Number(s?.known_subtotal_cny ?? 0).toLocaleString()}，最长工期 ${s?.max_lead_time_days} 天。`,
      });
    } catch (err) {
      setLiveVeStatus({
        ok: false,
        message: `Live FastAPI 引擎未响应（${err instanceof Error ? err.message : String(err)}），当前页面已同步执行确定性前端定额运算。`,
      });
    } finally {
      setLiveVeLoading(false);
    }
  };

  if (!tectonicBundle || !activeCase || !rawTier || !activePresetTier) {
    return (
      <div className="py-20 text-center text-sm text-muted-foreground border border-border bg-secondary/60">
        正在加载 3 套实景商业立面重绘案例、30 项构造定额库与单应性分缝投影数据…
      </div>
    );
  }

  const totalCostNum = Number(evalResult.summary.known_subtotal_cny);
  const lowCostNum = Number(evalResult.summary.low_estimate_cny);
  const highCostNum = Number(evalResult.summary.high_estimate_cny);
  const seamSegments = activePresetTier.homography_projection?.seam_segments ?? [];
  const wallModulus = wallZone?.engineering_state.panel_modulus_mm;

  return (
    <div className="space-y-8">
      {/* Header + 3-Case Selector + Export Report CTA */}
      <section className="pb-6 border-b border-border space-y-5">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-5">
          <div className="space-y-2 max-w-2xl">
            <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-[-0.02em] text-foreground">
              TectonicLoop · 物理建构排雷与树影锁定价值工程
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              通过单应性矩阵（H/H⁻¹）透视模数投影与本征树影锁定重绘，在保留街景氛围与自然树影的前提下，对 90–300㎡ 商业门头执行 30 项构造包选型、隐患拦截与 Zero-LLM Decimal 实时核算。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={() => setCalibratorOpen(true)}
              className="min-h-[42px] px-4 rounded-md border border-border hover:border-primary bg-card text-xs font-semibold text-foreground inline-flex items-center gap-2 transition-colors"
            >
              <Crosshair className="w-3.5 h-3.5 text-primary" />
              <span>自定义 4 点透视标定</span>
            </button>
            <button
              type="button"
              onClick={() => setCatalogModalOpen(true)}
              className="min-h-[42px] px-4 rounded-md border border-border hover:border-foreground/70 bg-card text-xs font-semibold text-foreground inline-flex items-center gap-2 transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5 text-primary" />
              <span>30 项定额库与 8 条排雷规则</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setVeReportOpen(true);
                trackShowcaseEvent('tectonic_ve_open', { case_id: selectedCaseId });
              }}
              className="min-h-[42px] px-5 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold inline-flex items-center gap-2 transition-colors"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>导出甲方 VE 任务书</span>
            </button>
          </div>
        </div>

        {/* 3 Real Commercial Case Switcher */}
        <div
          role="group"
          aria-label="选择 3 套实测商业改造案例"
          className="grid grid-cols-1 md:grid-cols-3 border border-border divide-y md:divide-y-0 md:divide-x divide-border"
        >
          {cases.map((c, idx) => {
            const isSel = c.case_id === activeCase.case_id;
            return (
              <button
                key={c.case_id}
                type="button"
                aria-pressed={isSel}
                onClick={() => handleSelectCase(c.case_id)}
                className={`text-left p-3.5 transition-colors ${
                  isSel
                    ? 'bg-accent text-foreground border-b-2 border-b-[#153CE8]'
                    : 'bg-card text-muted-foreground hover:bg-secondary/60 hover:text-foreground'
                }`}
              >
                <div className="flex items-center justify-between text-xs mono mb-1">
                  <span className={isSel ? 'text-primary font-semibold' : 'text-muted-foreground'}>
                    CASE 0{idx + 1} · {c.scale_anchor.facade_width_mm}×{c.scale_anchor.facade_height_mm}mm
                  </span>
                </div>
                <div className="text-sm font-bold text-foreground">{c.title}</div>
                <div className="text-xs text-muted-foreground truncate mt-0.5">{c.subtitle}</div>
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left 7 Cols · Dual-Mode Interactive Viewport + Telemetry + CAD Section */}
        <div className="lg:col-span-7 space-y-5">
          {/* Viewport Controls Row */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div role="group" aria-label="视图模式切换" className="inline-flex border border-border divide-x divide-border">
              <button
                type="button"
                aria-pressed={viewportMode === 'photoreal'}
                onClick={() => setViewportMode('photoreal')}
                className={`min-h-[34px] px-3 text-xs font-semibold transition-colors ${
                  viewportMode === 'photoreal'
                    ? 'bg-foreground text-background'
                    : 'bg-card text-foreground hover:bg-secondary/60'
                }`}
              >
                实景重绘对比帘
              </button>
              <button
                type="button"
                aria-pressed={viewportMode === 'orthographic'}
                onClick={() => setViewportMode('orthographic')}
                className={`min-h-[34px] px-3 text-xs font-semibold transition-colors ${
                  viewportMode === 'orthographic'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card text-foreground hover:bg-secondary'
                }`}
              >
                正交施工立面图
              </button>
              <button
                type="button"
                aria-pressed={viewportMode === '3d'}
                onClick={() => setViewportMode('3d')}
                className={`min-h-[34px] px-3 text-xs font-semibold inline-flex items-center gap-1.5 transition-colors ${
                  viewportMode === '3d'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card text-foreground hover:bg-secondary'
                }`}
              >
                <Box className="w-3.5 h-3.5" />
                <span>3D 单应性投影</span>
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs text-foreground">
              <label className="inline-flex items-center gap-2 cursor-pointer select-none min-h-[32px]">
                <input
                  type="checkbox"
                  checked={showSeams}
                  onChange={(e) => setShowSeams(e.target.checked)}
                  className="w-4 h-4 accent-primary"
                />
                <span>H/H⁻¹ 透视模数分缝层</span>
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer select-none min-h-[32px]">
                <input
                  type="checkbox"
                  checked={showPins}
                  onChange={(e) => setShowPins(e.target.checked)}
                  className="w-4 h-4 accent-destructive"
                />
                <span>建构排雷标点 ({evalResult.summary.blocking_alerts_count})</span>
              </label>
            </div>
          </div>

          {/* Primary Viewport Plate */}
          {viewportMode === '3d' ? (
            <TectonicPlane3D
              activeCase={activeCase}
              activeTier={activePresetTier}
              showSeams={showSeams}
              showPins={showPins}
            />
          ) : viewportMode === 'photoreal' ? (
            <BeforeAfterSlider
              beforeSrc={rawTier.image_url}
              afterSrc={activePresetTier.image_url}
              beforeAlt={`${activeCase.title} 原始概念方案`}
              afterAlt={`${activeCase.title} ${activePresetTier.short_label} 重绘方案`}
              beforeLabel="原始概念 · 建构隐患"
              afterLabel={`${activePresetTier.short_label} · 树影锁定重绘`}
              overlay={
                <>
                  {/* Dynamic OpenCV H/H^-1 Perspective Seam Overlay + Scale Anchor */}
                  {showSeams && (
                    <svg viewBox="0 0 800 600" className="w-full h-full block">
                      {seamSegments.map((seg, i) => (
                        <line
                          key={i}
                          x1={seg.start.x}
                          y1={seg.start.y}
                          x2={seg.end.x}
                          y2={seg.end.y}
                          stroke={FALLBACK_SEAM_COLORS.stroke}
                          strokeWidth="1.6"
                          strokeDasharray={seg.orientation === 'horizontal' ? '4 2' : undefined}
                          opacity="0.88"
                        />
                      ))}
                      {activeCase.geometry?.facade_quad_px && activeCase.geometry.facade_quad_px.length === 4 && (
                        <>
                          <polygon
                            points={activeCase.geometry.facade_quad_px.map((p) => `${p.x},${p.y}`).join(' ')}
                            fill="none"
                            stroke="#153CE8"
                            strokeWidth="1.2"
                            strokeDasharray="6 4"
                            opacity="0.7"
                          />
                          <line
                            x1={activeCase.geometry.facade_quad_px[3].x}
                            y1={Math.min(585, activeCase.geometry.facade_quad_px[3].y + 10)}
                            x2={activeCase.geometry.facade_quad_px[2].x}
                            y2={Math.min(585, activeCase.geometry.facade_quad_px[2].y + 10)}
                            stroke="#153CE8"
                            strokeWidth="1.5"
                          />
                        </>
                      )}
                    </svg>
                  )}

                  {/* Interactive Diagnostic Pins anchored on Facade Zones */}
                  {showPins &&
                    diagnosticMarkers.map((marker, idx) => {
                      const isSel = selectedPinIndex === idx;
                      const badgeBg = marker.hasAnyAlert ? 'bg-destructive' : 'bg-teal-ok';
                      return (
                        <button
                          key={marker.zone.zone_id}
                          type="button"
                          aria-label={`查看 ${marker.zone.zone_label} 排雷诊断`}
                          aria-pressed={isSel}
                          onPointerDown={(e) => e.stopPropagation()}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedPinIndex(idx);
                          }}
                          style={{
                            left: `${marker.pin.x_pct}%`,
                            top: `${marker.pin.y_pct}%`,
                          }}
                          className={`pointer-events-auto -translate-x-1/2 -translate-y-1/2 absolute w-8 h-8 rounded-full border-2 border-[#FFFFFF] text-white flex items-center justify-center mono text-xs font-bold shadow transition-transform ${badgeBg} ${
                            isSel ? 'scale-115 ring-2 ring-[#0E1015]' : 'hover:scale-105'
                          }`}
                        >
                          {idx + 1}
                        </button>
                      );
                    })}
                </>
              }
            />
          ) : (
            /* Precision Architectural Orthographic Elevation Mode */
            <div className="border border-foreground/70 bg-secondary/40">
              <div className="relative w-full">
                <svg
                  viewBox="0 0 760 440"
                  role="img"
                  aria-label="街角商业立面正交构造图纸"
                  className="w-full h-auto block select-none"
                >
                  <defs>
                    <pattern id="tlOrthoConcrete" width="24" height="24" patternUnits="userSpaceOnUse">
                      <circle cx="6" cy="8" r="0.8" fill="#525866" opacity="0.35" />
                      <circle cx="18" cy="18" r="0.7" fill="#525866" opacity="0.25" />
                    </pattern>
                    <pattern id="tlOrthoGlaze" width="12" height="12" patternUnits="userSpaceOnUse">
                      <line x1="0" y1="12" x2="12" y2="0" stroke="#153CE8" strokeWidth="0.6" opacity="0.2" />
                    </pattern>
                  </defs>
                  <line x1="36" y1="92" x2="720" y2="92" stroke="#CBD0D8" strokeWidth="0.75" strokeDasharray="4 4" />
                  <text x="40" y="85" fill="#525866" fontSize="10" fontFamily="Chivo Mono">
                    +{activeCase.scale_anchor.facade_height_mm}mm 檐口
                  </text>
                  <line x1="30" y1="348" x2="730" y2="348" stroke="#0E1015" strokeWidth="1.5" />
                  <rect x="110" y="92" width="540" height="256" fill="#ECEEF2" stroke="#0E1015" strokeWidth="1.5" />
                  <rect x="110" y="92" width="540" height="256" fill="url(#tlOrthoConcrete)" />
                  {showSeams && wallModulus && (
                    <g opacity="0.7">
                      {Array.from({ length: Math.max(1, Math.floor(activeCase.scale_anchor.facade_width_mm / wallModulus.width) - 1) }).map((_, i) => {
                        const cols = Math.floor(activeCase.scale_anchor.facade_width_mm / wallModulus.width);
                        const xPos = 110 + (540 * (i + 1)) / Math.max(1, cols);
                        return <line key={`ov-${i}`} x1={xPos} y1="92" x2={xPos} y2="348" stroke="#153CE8" strokeWidth="1" />;
                      })}
                      <line x1="110" y1="220" x2="650" y2="220" stroke="#153CE8" strokeWidth="0.9" strokeDasharray="3 2" />
                    </g>
                  )}
                  <rect x="145" y="184" width="82" height="164" fill="#FFFFFF" stroke="#0E1015" strokeWidth="1.5" />
                  <rect x="260" y="184" width="345" height="164" fill="#FFFFFF" stroke="#0E1015" strokeWidth="1.75" />
                  <rect x="265" y="189" width="335" height="154" fill="url(#tlOrthoGlaze)" stroke="#525866" strokeWidth="0.75" />
                  {effectiveZones[1]?.engineering_state.panel_modulus_mm && (
                    <g>
                      <line x1="375" y1="184" x2="375" y2="348" stroke="#0E1015" strokeWidth="3.5" />
                      <line x1="490" y1="184" x2="490" y2="348" stroke="#0E1015" strokeWidth="3.5" />
                    </g>
                  )}
                  {effectiveZones[2]?.engineering_state.has_parapet_flashing && (
                    <>
                      <rect x="106" y="85" width="548" height="8" fill="#0E1015" />
                      <rect x="110" y="338" width="540" height="10" fill="#0E1015" />
                    </>
                  )}
                  <line x1="110" y1="400" x2="650" y2="400" stroke="#0E1015" strokeWidth="1" />
                  <text x="380" y="394" fill="#0E1015" fontSize="10.5" fontFamily="Chivo Mono" fontWeight="600" textAnchor="middle">
                    {activeCase.scale_anchor.label}
                  </text>
                </svg>

                {showPins &&
                  diagnosticMarkers.map((marker, idx) => {
                    const isSel = selectedPinIndex === idx;
                    const badgeBg = marker.hasAnyAlert ? 'bg-destructive' : 'bg-teal-ok';
                    return (
                      <button
                        key={marker.zone.zone_id}
                        type="button"
                        aria-label={`查看 ${marker.zone.zone_label} 排雷诊断`}
                        aria-pressed={isSel}
                        onClick={() => setSelectedPinIndex(idx)}
                        style={{ left: `${marker.pin.x_pct}%`, top: `${marker.pin.y_pct}%` }}
                        className={`-translate-x-1/2 -translate-y-1/2 absolute w-8 h-8 rounded-full border-2 border-[#FFFFFF] text-white flex items-center justify-center mono text-xs font-bold ${badgeBg} ${
                          isSel ? 'ring-2 ring-[#0E1015]' : ''
                        }`}
                      >
                        {idx + 1}
                      </button>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Measured Homography & Relight Quality Strip */}
          <div className="grid grid-cols-3 gap-px bg-border border border-border text-xs">
            <div className="bg-secondary/60 p-3">
              <div className="text-muted-foreground">基准尺度锚点</div>
              <div className="mono font-semibold text-foreground truncate mt-0.5">
                {activeCase.scale_anchor.facade_width_mm} × {activeCase.scale_anchor.facade_height_mm} mm
              </div>
            </div>
            <div className="bg-secondary/60 p-3">
              <div className="text-muted-foreground">H⁻¹ 分缝灭点误差</div>
              <div className="mono font-semibold text-primary tabular-nums mt-0.5">
                {activePresetTier.homography_projection.vertical_vanishing_deviation_deg.toFixed(3)}° (&lt;1.5°)
              </div>
            </div>
            <div className="bg-secondary/60 p-3">
              <div className="text-muted-foreground">非修改区像素保真度</div>
              <div className="mono font-semibold text-teal-ok tabular-nums mt-0.5">
                {activePresetTier.tier_id === 'tier_0_raw'
                  ? '原始输入底图基准'
                  : activePresetTier.relight_metrics.non_mask_psnr_db >= 90
                    ? `像素锁死 (PSNR ≥38dB · r=${activePresetTier.relight_metrics.shadow_luma_corr.toFixed(2)})`
                    : `${activePresetTier.relight_metrics.non_mask_psnr_db.toFixed(2)} dB (r=${activePresetTier.relight_metrics.shadow_luma_corr.toFixed(2)})`}
              </div>
            </div>
          </div>

          {/* Active Diagnostic Status Strip */}
          {activeMarker && (
            <div className="border border-foreground/70 bg-card p-4 flex flex-col sm:flex-row sm:items-start justify-between gap-3 text-xs">
              <div className="flex items-start gap-2.5 leading-relaxed text-foreground">
                {activeMarker.hasAnyAlert ? (
                  <AlertTriangle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                ) : (
                  <Check className="w-4 h-4 text-teal-ok shrink-0 mt-0.5" />
                )}
                <div className="space-y-1">
                  <div className="font-semibold">
                    {activeMarker.zone.zone_label} · {activeMarker.zone.sku_name ?? activeMarker.zone.engineering_state.detail_drawing_code}
                  </div>
                  {activeMarker.alerts.length === 0 ? (
                    <p className="text-muted-foreground">
                      构造合法，模数与防潮节点符合《常见饰面极限制造尺幅与构造禁忌》。
                    </p>
                  ) : (
                    activeMarker.alerts.map((al, idx) => (
                      <p key={idx} className="text-muted-foreground">
                        <span className="mono font-semibold text-destructive mr-1.5">[{al.code}]</span>
                        {al.message} <span className="text-foreground">建议：{al.remediation_hint}</span>
                      </p>
                    ))
                  )}
                </div>
              </div>
              <span
                className={`px-2.5 py-1 font-semibold border shrink-0 whitespace-nowrap ${
                  activeMarker.hasAnyAlert
                    ? 'border-destructive text-destructive'
                    : 'border-teal-ok text-teal-ok'
                }`}
              >
                {activeMarker.hasBlocking ? '阻断预警' : activeMarker.hasAnyAlert ? '周期提醒' : '构造合规'}
              </span>
            </div>
          )}

          {/* CAD Section Detail Blueprint */}
          {wallZone && (
            <CadDetailViewer
              detail={activeCadDetail}
              drawingCode={wallCadCode}
              assemblyName={wallZone.sku_name ?? wallZone.zone_label}
              layers={wallZone.engineering_state.assembly_layers}
            />
          )}
        </div>

        {/* Right 5 Cols · 3-Tier Switcher, Zero-LLM Cost Engine & 30-SKU Controllers */}
        <div className="lg:col-span-5 space-y-6">
          {/* 3-Tier Preset Bar */}
          <div className="space-y-2">
            <div className="text-xs font-bold text-foreground">一键切换同效异构价值工程档位</div>
            <div role="group" aria-label="三档价值工程方案" className="grid grid-cols-3 gap-2">
              {activeCase.tiers.map((tier) => {
                const isSel = !hasCustomOverride && selectedTierId === tier.tier_id;
                return (
                  <button
                    key={tier.tier_id}
                    type="button"
                    aria-pressed={isSel}
                    onClick={() => handleSelectTier(tier.tier_id)}
                    className={`min-h-[42px] px-2.5 py-2 text-xs font-semibold border text-left transition-colors ${
                      isSel
                        ? 'bg-primary border-primary text-white'
                        : 'bg-card border-border text-foreground hover:border-foreground/70'
                    }`}
                  >
                    <div className="truncate">{tier.short_label}</div>
                    <div className={`mono mt-0.5 tabular-nums ${isSel ? 'text-[#EEF2FF]' : 'text-muted-foreground'}`}>
                      ¥{Math.round(Number(tier.summary.known_subtotal_cny)).toLocaleString()} · {tier.summary.max_lead_time_days}天
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3 Live Deterministic Decimal KPIs */}
          <div className="grid grid-cols-3 gap-px bg-border border border-border">
            <div className="bg-card p-3.5">
              <div className="text-xs text-muted-foreground">预估造价 (±12%)</div>
              {evalResult.summary.has_missing_prices ? (
                <>
                  <div className="mono text-sm font-bold text-destructive mt-1">
                    UNKNOWN_PRICE_MISSING
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5 tabular-nums">
                    已知项 ¥{totalCostNum.toLocaleString()}
                  </div>
                </>
              ) : (
                <>
                  <div
                    className={`mono text-base sm:text-lg font-bold tabular-nums mt-1 ${
                      totalCostNum <= 80000 ? 'text-teal-ok' : 'text-destructive'
                    }`}
                  >
                    ¥ {totalCostNum.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5 mono tabular-nums">
                    {Math.round(lowCostNum / 1000)}k~{Math.round(highCostNum / 1000)}k
                  </div>
                </>
              )}
            </div>

            <div className="bg-card p-3.5">
              <div className="text-xs text-muted-foreground">施工周期</div>
              <div className="mono text-base sm:text-lg font-bold text-foreground tabular-nums mt-1">
                {evalResult.summary.max_lead_time_days} 天
              </div>
              <div
                className={`text-xs mt-0.5 ${
                  evalResult.summary.warning_alerts_count > 0 ? 'text-destructive' : 'text-teal-ok'
                }`}
              >
                {evalResult.summary.warning_alerts_count > 0 ? '超出快装窗口' : '干法快速装配'}
              </div>
            </div>

            <div className="bg-card p-3.5">
              <div className="text-xs text-muted-foreground">建构排雷校验</div>
              <div
                className={`mono text-base sm:text-lg font-bold tabular-nums mt-1 whitespace-nowrap ${
                  evalResult.summary.blocking_alerts_count === 0 ? 'text-teal-ok' : 'text-destructive'
                }`}
              >
                {evalResult.summary.blocking_alerts_count === 0
                  ? '0 项阻断'
                  : `${evalResult.summary.blocking_alerts_count} 项阻断`}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5 whitespace-nowrap">
                点击左图数字排查
              </div>
            </div>
          </div>

          {hasCustomOverride && (
            <div className="p-3 border border-primary bg-accent text-xs text-foreground flex items-center justify-between gap-2">
              <span>已启用自定义 SKU 搭配（CAD 详图、排雷与造价即时重算；左图当前对应所选实景基准档位）</span>
              <button
                type="button"
                onClick={() => setCustomSkus({})}
                className="font-semibold text-primary underline shrink-0"
              >
                还原
              </button>
            </div>
          )}

          {/* Zone A / B / C 30-SKU Controllers */}
          <div className="space-y-4">
            <h2 className="font-display text-base font-bold text-foreground">
              分区域工艺替换与定额核算（30 项实库）
            </h2>

            {effectiveZones.map((zone, idx) => {
              const bd = evalResult.costBreakdowns[idx];
              const categoryKey =
                idx === 0
                  ? 'wall_cladding'
                  : idx === 1
                    ? 'glazing_portal'
                    : 'edge_weatherproofing';
              const options = skusByCategory[categoryKey];
              const currentSkuId = zone.sku_id ?? options[0]?.sku_id ?? '';
              const selectId = `zone-select-${zone.zone_id}`;
              const isMissing = bd?.status === 'UNKNOWN_PRICE_MISSING';

              return (
                <div key={zone.zone_id} className="border border-border p-4 space-y-2 bg-card">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <label htmlFor={selectId} className="font-semibold text-foreground">
                      {zone.zone_label}
                    </label>
                    <span
                      className={`mono font-semibold tabular-nums ${
                        isMissing ? 'text-destructive' : 'text-primary'
                      }`}
                    >
                      {isMissing
                        ? 'UNKNOWN_PRICE_MISSING'
                        : `¥ ${Number(bd.material_and_substructure_cny).toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                          })}`}
                    </span>
                  </div>
                  <select
                    id={selectId}
                    value={currentSkuId}
                    onChange={(e) => {
                      const nextSkuId = e.target.value;
                      setCustomSkus((prev) => ({ ...prev, [zone.zone_id]: nextSkuId }));
                      setLiveVeStatus(null);
                    }}
                    className="w-full min-h-[38px] px-2.5 border border-border focus:border-primary bg-card text-xs text-foreground"
                  >
                    {options.map((opt) => (
                      <option key={opt.sku_id} value={opt.sku_id}>
                        {opt.name} (
                        {opt.lump_sum_cny !== null
                          ? `包干 ¥${Number(opt.lump_sum_cny).toLocaleString()}`
                          : opt.unit_cost_cny_sqm !== null
                            ? `¥${Math.round(Number(opt.unit_cost_cny_sqm) + Number(opt.substructure_amortization_cny_sqm))}/㎡`
                            : '待核价 · 触发 UNKNOWN_PRICE_MISSING'}
                        {' · '}
                        {opt.lead_time_days}天)
                      </option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>

          {/* Live Backend Calc Verification + Missing Price Policy */}
          <div className="border border-border bg-secondary/60 p-4 space-y-3 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-foreground">Zero-LLM Decimal 规则验证</span>
              <button
                type="button"
                disabled={liveVeLoading}
                onClick={handleLiveBackendVeCalc}
                className={`min-h-[36px] px-3.5 text-xs font-semibold transition-colors ${
                  isLiveEngine
                    ? 'bg-teal-ok hover:bg-[#0D5F59] text-white'
                    : 'bg-foreground hover:bg-primary text-primary-foreground'
                }`}
              >
                {liveVeLoading ? '核算请求中…' : '执行 Live FastAPI 实时核算'}
              </button>
            </div>

            {liveVeStatus && (
              <div
                role="status"
                className={`p-3 border bg-card leading-relaxed ${
                  liveVeStatus.ok
                    ? 'border-teal-ok text-teal-ok'
                    : 'border-destructive text-destructive'
                }`}
              >
                {liveVeStatus.message}
              </div>
            )}

            <div className="pt-1 flex items-start gap-2 text-muted-foreground leading-relaxed">
              <Info className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
              <span>
                未知单价阻断测试：在 Zone A 下拉框中选择「定制手工锻铜做旧艺术挂板」，可即时观测系统阻断伪估算并输出 <code className="mono text-destructive font-semibold">UNKNOWN_PRICE_MISSING</code>。
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Custom 4-Point Homography Calibrator (MIC-166 Live Engine + Offline Fallback) */}
      <LiveHomographyCalibrator
        open={calibratorOpen}
        onOpenChange={setCalibratorOpen}
        defaultImageUrl={activePresetTier.image_url}
        defaultQuad={activeCase.geometry?.facade_quad_px ?? []}
        isLiveEngine={isLiveEngine}
      />

      {/* Exportable VE Monograph Sheet Modal */}
      <TectonicVeReportModal
        isOpen={veReportOpen}
        onClose={() => setVeReportOpen(false)}
        activeCase={activeCase}
        rawTier={rawTier}
        currentZones={effectiveZones}
        currentCostBreakdowns={evalResult.costBreakdowns}
        currentAlerts={evalResult.alerts}
        currentSummary={evalResult.summary}
        targetImageUrl={activePresetTier.image_url}
        relightMetrics={activePresetTier.relight_metrics}
        homographyMetrics={activePresetTier.homography_projection}
        activeCadDetail={activeCadDetail}
      />

      {/* 30-SKU Catalog & 8-Rule Drawer Modal */}
      {catalogModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="tectonic-catalog-modal-title"
          onClick={() => setCatalogModalOpen(false)}
          className="fixed inset-0 z-50 bg-foreground/65 backdrop-blur-[2px] flex items-center justify-center p-3 sm:p-6"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-card border border-foreground/70 w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden"
          >
            <div className="px-5 py-4 border-b border-border flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 id="tectonic-catalog-modal-title" className="font-display text-lg font-bold text-foreground">
                  商业立面与饰面构造定额库（{tectonicBundle.total_assemblies} 项）及排雷标准
                </h2>
                <p className="text-xs text-muted-foreground">
                  涵盖外墙饰面、门窗幕墙、泛水压顶与入口地面四类高频商业改造节点（基准日期 {tectonicBundle.benchmark_date}）
                </p>
              </div>
              <button
                type="button"
                aria-label="关闭定额库窗口"
                onClick={() => setCatalogModalOpen(false)}
                className="w-10 h-10 border border-border hover:border-foreground/70 flex items-center justify-center text-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="px-5 pt-3 border-b border-border flex gap-6 text-xs">
              <button
                type="button"
                onClick={() => setCatalogTab('assemblies')}
                className={`pb-3 font-semibold border-b-2 transition-colors ${
                  catalogTab === 'assemblies'
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground'
                }`}
              >
                全部 {tectonicBundle.total_assemblies} 项构造工艺包
              </button>
              <button
                type="button"
                onClick={() => setCatalogTab('rules')}
                className={`pb-3 font-semibold border-b-2 transition-colors ${
                  catalogTab === 'rules'
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground'
                }`}
              >
                {lintRules.length} 条物理建构排雷准则
              </button>
            </div>

            <div className="p-5 overflow-y-auto flex-1 text-xs">
              {catalogTab === 'assemblies' ? (
                <div className="overflow-x-auto border border-border">
                  <table className="w-full min-w-[700px] text-left border-collapse">
                    <thead>
                      <tr className="bg-secondary/60 border-b border-foreground/70 text-foreground font-semibold">
                        <th className="py-2.5 px-3">分类</th>
                        <th className="py-2.5 px-3">构造做法名称</th>
                        <th className="py-2.5 px-3">标准模数 (mm)</th>
                        <th className="py-2.5 px-3">基价 + 龙骨 (CNY)</th>
                        <th className="py-2.5 px-3">损耗 / 周期</th>
                        <th className="py-2.5 px-3">图集索引</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {assemblies.map((item) => {
                        const isUnpriced = item.unit_cost_cny_sqm === null && item.lump_sum_cny === null;
                        return (
                          <tr key={item.sku_id}>
                            <td className="py-2.5 px-3 mono text-muted-foreground">{item.category}</td>
                            <td className="py-2.5 px-3 font-semibold text-foreground">{item.name}</td>
                            <td className="py-2.5 px-3 mono text-muted-foreground">
                              {item.panel_modulus_mm
                                ? `${item.panel_modulus_mm.width}×${item.panel_modulus_mm.height}`
                                : '无缝/非标'}
                            </td>
                            <td className="py-2.5 px-3 mono tabular-nums">
                              {isUnpriced ? (
                                <span className="font-semibold text-destructive">UNKNOWN_PRICE_MISSING</span>
                              ) : item.lump_sum_cny !== null ? (
                                `包干 ¥${Number(item.lump_sum_cny).toLocaleString()}`
                              ) : (
                                `¥${item.unit_cost_cny_sqm} + ¥${item.substructure_amortization_cny_sqm}/㎡`
                              )}
                            </td>
                            <td className="py-2.5 px-3 mono text-foreground tabular-nums">
                              ×{item.wastage_factor} · {item.lead_time_days}天
                            </td>
                            <td className="py-2.5 px-3 mono text-primary">{item.detail_drawing_code}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {lintRules.map((r) => (
                    <div key={r.code} className="border border-border p-4 space-y-2 bg-card">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-foreground">{r.title}</span>
                        <span
                          className={`mono font-semibold ${
                            r.severity === 'BLOCKING' ? 'text-destructive' : 'text-primary'
                          }`}
                        >
                          {r.code}
                        </span>
                      </div>
                      <div className="text-muted-foreground font-medium">{r.standard_basis}</div>
                      <p className="text-foreground leading-relaxed">{r.physical_limit}</p>
                      <p className="text-teal-ok border-t border-border pt-2">整改路径：{r.remediation}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
