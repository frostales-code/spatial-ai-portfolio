import type {
  TectonicAlert,
  TectonicAssemblySku,
  TectonicZoneState,
  VeProjectSummaryJson,
  ZoneCostBreakdown,
} from '../types/tectonic';

function parseNum(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function buildZoneFromSku(
  baseZone: TectonicZoneState,
  sku: TectonicAssemblySku,
): TectonicZoneState {
  return {
    ...baseZone,
    sku_id: sku.sku_id,
    sku_name: sku.name,
    visual_binding: {
      ...baseZone.visual_binding,
      max_continuous_span_m: sku.default_span_m.toFixed(1),
      is_curved_geometry: sku.is_curved_geometry,
    },
    engineering_state: {
      active_tier: sku.active_tier,
      assembly_layers: sku.assembly_layers,
      panel_modulus_mm: sku.panel_modulus_mm,
      construction_method: sku.construction_method,
      detail_drawing_code: sku.detail_drawing_code,
      has_parapet_flashing: sku.has_parapet_flashing,
      has_recessed_plinth: sku.has_recessed_plinth,
      unit_cost_cny_sqm: sku.unit_cost_cny_sqm,
      wastage_factor: sku.wastage_factor,
      substructure_amortization_cny_sqm: sku.substructure_amortization_cny_sqm,
      lump_sum_cny: sku.lump_sum_cny,
      lead_time_days: sku.lead_time_days,
      data_benchmark_date: baseZone.engineering_state.data_benchmark_date,
    },
  };
}

export function lintZoneClient(zone: TectonicZoneState): TectonicAlert[] {
  const alerts: TectonicAlert[] = [];
  const vb = zone.visual_binding;
  const es = zone.engineering_state;
  const maxSpan = parseNum(vb.max_continuous_span_m) ?? 0;
  const joined = `${zone.zone_id} ${zone.zone_label} ${es.detail_drawing_code} ${es.assembly_layers.join(' ')}`.toLowerCase();

  if (es.construction_method === 'wet_cast_in_situ' && maxSpan > 4.5) {
    alerts.push({
      code: 'WET_WORK_STREET_CONFLICT',
      severity: 'BLOCKING',
      zone_id: zone.zone_id,
      message: `连续 ${maxSpan}m 现浇清水混凝土在临街商铺微更新场景需占道支模养护 (${es.lead_time_days} 天)，审批与工期风险极高。`,
      remediation_hint: '切换为 18mm 预制 UHPC 干挂板 (1200x2400) 或纤维水泥挂板全干法体系。',
    });
  }

  if (zone.zone_id.toLowerCase().includes('glazing') && maxSpan > 3.2 && !es.panel_modulus_mm) {
    alerts.push({
      code: 'JUMBO_GLASS_SPAN_EXCEEDED',
      severity: 'BLOCKING',
      zone_id: zone.zone_id,
      message: `无框单块玻璃跨度达 ${maxSpan}m，超出常规货梯运输与钢化炉经济极值，需封路动用重型随车吊。`,
      remediation_hint: '按 1700mm 模数增设极窄黑钢竖梃或切换为四扇铝合金折叠开启窗。',
    });
  }

  if (!es.has_parapet_flashing || !es.has_recessed_plinth) {
    alerts.push({
      code: 'WEATHERPROOF_DETAIL_MISSING',
      severity: 'BLOCKING',
      zone_id: zone.zone_id,
      message: '检测到女儿墙缺少金属泛水滴水线或底部直抵地面无防潮勒脚，交付半年内极易流挂返碱。',
      remediation_hint: '注入 3mm 氟碳铝板压顶滴水线 + 80mm 不锈钢内凹防潮踢脚节点。',
    });
  }

  const isCurved = vb.is_curved_geometry || joined.includes('curved') || joined.includes('弧') || joined.includes('grg');
  if (isCurved && es.lead_time_days > 21 && !es.panel_modulus_mm) {
    alerts.push({
      code: 'CURVED_BESPOKE_FORMWORK_OVERFLOW',
      severity: 'BLOCKING',
      zone_id: zone.zone_id,
      message: `双曲面异形无分缝定制整体饰面需 CNC 异形模具与现场分段批嵌养护 (${es.lead_time_days} 天)，单方造价与接缝开裂风险显著超限。`,
      remediation_hint: '改用小幅面折叠直板多折线拟合曲面（600/900mm 干挂模数），彻底取消异形现场湿作业。',
    });
  }

  const isPorousEarth =
    joined.includes('earth') || joined.includes('夯土') || joined.includes('rammed') || joined.includes('stucco') || joined.includes('土墙');
  if ((es.construction_method === 'raw_hallucination' || isPorousEarth) && !es.has_recessed_plinth) {
    alerts.push({
      code: 'MOISTURE_UNSEALED_GROUND_CONTACT',
      severity: 'BLOCKING',
      zone_id: zone.zone_id,
      message: '多孔吸湿表皮（生土/夯土/无机粉刷）直接触地且无疏水防潮勒脚，毛细虹吸将在首个雨季引起粉化剥落。',
      remediation_hint: '增设 ≥120mm 花岗岩/不锈钢内凹防潮台基，并在饰面表面加注透气硅烷憎水封闭剂。',
    });
  }

  if (es.lead_time_days > 21) {
    alerts.push({
      code: 'LEAD_TIME_COMMERCIAL_EXCEEDED',
      severity: 'WARNING',
      zone_id: zone.zone_id,
      message: `当前工艺总生产/养护周期达 ${es.lead_time_days} 天，超出 90-300㎡ 街区商铺高周转黄金窗口 (≤21 天)。`,
      remediation_hint: '优先选择标准化库存干挂板材或工厂预制模块化门窗框架。',
    });
  }

  if (es.construction_method === 'dry_hanging_prefab' && es.panel_modulus_mm) {
    const areaMm2 = es.panel_modulus_mm.width * es.panel_modulus_mm.height;
    if (areaMm2 > 3_200_000) {
      alerts.push({
        code: 'EXCESSIVE_PANEL_MODULE_WEIGHT',
        severity: 'WARNING',
        zone_id: zone.zone_id,
        message: `单块干挂板尺寸 ${es.panel_modulus_mm.width}x${es.panel_modulus_mm.height}mm 自重过大，需重型双背栓与升降脚手架配合。`,
        remediation_hint: '建议将单块板面拆分至 1200x2400mm（2.88 ㎡）或 600x1200mm 标准规格。',
      });
    }
  }

  return alerts;
}

/** Integer-cent deterministic calculation matching Python Decimal ROUND_HALF_UP. */
export function calculateZoneCostClient(zone: TectonicZoneState): ZoneCostBreakdown {
  const vb = zone.visual_binding;
  const es = zone.engineering_state;

  const netAreaX100 = Math.round((parseNum(vb.estimated_area_sqm) ?? 0) * 100);
  const wastageX100 = Math.round((parseNum(es.wastage_factor) ?? 1.1) * 100);
  const effectiveAreaX100 = Math.round((netAreaX100 * wastageX100) / 100);

  const lumpSum = parseNum(es.lump_sum_cny);
  const unitCost = parseNum(es.unit_cost_cny_sqm);
  const subCost = parseNum(es.substructure_amortization_cny_sqm) ?? 0;

  let baseCents: number | null = null;
  if (lumpSum !== null) {
    baseCents = Math.round(lumpSum * 100);
  } else if (unitCost !== null) {
    const rateCents = Math.round((unitCost + subCost) * 100);
    baseCents = Math.round((effectiveAreaX100 * rateCents) / 100);
  }

  if (baseCents === null) {
    return {
      zone_id: zone.zone_id,
      status: 'UNKNOWN_PRICE_MISSING',
      net_area_sqm: (netAreaX100 / 100).toFixed(2),
      effective_area_with_wastage_sqm: (effectiveAreaX100 / 100).toFixed(2),
      material_and_substructure_cny: null,
      low_estimate_cny: null,
      high_estimate_cny: null,
      currency: 'CNY',
      confidence_band_pct: 12,
      data_benchmark_date: es.data_benchmark_date,
    };
  }

  const lowCents = Math.round(baseCents * 0.88);
  const highCents = Math.round(baseCents * 1.12);

  return {
    zone_id: zone.zone_id,
    status: 'CALCULATED',
    net_area_sqm: (netAreaX100 / 100).toFixed(2),
    effective_area_with_wastage_sqm: (effectiveAreaX100 / 100).toFixed(2),
    material_and_substructure_cny: (baseCents / 100).toFixed(2),
    low_estimate_cny: (lowCents / 100).toFixed(2),
    high_estimate_cny: (highCents / 100).toFixed(2),
    currency: 'CNY',
    confidence_band_pct: 12,
    data_benchmark_date: es.data_benchmark_date,
  };
}

export function evaluateZonesClient(zones: TectonicZoneState[]): {
  alerts: TectonicAlert[];
  costBreakdowns: ZoneCostBreakdown[];
  summary: VeProjectSummaryJson;
} {
  const alerts = zones.flatMap((z) => lintZoneClient(z));
  const costBreakdowns = zones.map((z) => calculateZoneCostClient(z));

  let knownCents = 0;
  const missingIds: string[] = [];
  for (const bd of costBreakdowns) {
    if (bd.status === 'UNKNOWN_PRICE_MISSING' || bd.material_and_substructure_cny === null) {
      missingIds.push(bd.zone_id);
    } else {
      knownCents += Math.round(Number(bd.material_and_substructure_cny) * 100);
    }
  }

  const lowCents = Math.round(knownCents * 0.88);
  const highCents = Math.round(knownCents * 1.12);
  const maxDays = zones.reduce((acc, z) => Math.max(acc, z.engineering_state.lead_time_days), 0);

  return {
    alerts,
    costBreakdowns,
    summary: {
      known_subtotal_cny: (knownCents / 100).toFixed(2),
      low_estimate_cny: (lowCents / 100).toFixed(2),
      high_estimate_cny: (highCents / 100).toFixed(2),
      max_lead_time_days: maxDays,
      blocking_alerts_count: alerts.filter((a) => a.severity === 'BLOCKING').length,
      warning_alerts_count: alerts.filter((a) => a.severity === 'WARNING').length,
      has_missing_prices: missingIds.length > 0,
      missing_price_zone_ids: missingIds,
      cost_status: missingIds.length > 0 ? 'PARTIAL_UNKNOWN_PRICE_MISSING' : 'CALCULATED',
      currency: 'CNY',
    },
  };
}
