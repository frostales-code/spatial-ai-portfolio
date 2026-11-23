"""TectonicLoop Visual-Tectonic State Graph, Constructability Linter, and Zero-LLM Decimal Cost Engine."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from pydantic import BaseModel, Field


class VisualBinding(BaseModel):
    """Visual geometry metadata extracted from SAM2 + Depth + Scale Anchor."""

    sam_mask_ref: str
    perspective_plane_normal: tuple[float, float, float]
    estimated_area_sqm: Decimal = Field(..., gt=Decimal("0"))
    max_continuous_span_m: Decimal = Field(..., gt=Decimal("0"))
    is_curved_geometry: bool = False


class PanelModulusMm(BaseModel):
    """Physical manufacturing panel dimensions and seam clearance."""

    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    joint_gap_mm: int = Field(..., ge=0)
    joint_type: str


class EngineeringState(BaseModel):
    """Engineering, constructability, and deterministic costing state for a facade/interior zone."""

    active_tier: Literal["Tier_A_Bespoke", "Tier_B_Balanced", "Tier_C_Value"]
    assembly_layers: list[str]
    panel_modulus_mm: PanelModulusMm | None = None
    construction_method: Literal["wet_cast_in_situ", "dry_hanging_prefab", "curtain_wall_framed", "raw_hallucination"]
    detail_drawing_code: str
    has_parapet_flashing: bool = True
    has_recessed_plinth: bool = True
    unit_cost_cny_sqm: Decimal | None = Field(default=None, ge=Decimal("0"))
    wastage_factor: Decimal = Field(default=Decimal("1.10"), ge=Decimal("1.00"), le=Decimal("1.35"))
    substructure_amortization_cny_sqm: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    lump_sum_cny: Decimal | None = Field(default=None, ge=Decimal("0"))
    lead_time_days: int = Field(..., gt=0)
    data_benchmark_date: str = "2026-11-23"


class VisualTectonicZone(BaseModel):
    """Single Source of Truth node coupling visual mask and engineering spec."""

    zone_id: str
    zone_label: str
    visual_binding: VisualBinding
    engineering_state: EngineeringState


class ConstructabilityAlert(BaseModel):
    """Structured diagnostic warning produced by deterministic Constructability Linter."""

    code: str
    severity: Literal["BLOCKING", "WARNING"]
    zone_id: str
    message: str
    remediation_hint: str


class CostBreakdown(BaseModel):
    """Zero-LLM deterministic cost breakdown; unknown prices are never coerced to 0."""

    zone_id: str
    status: Literal["CALCULATED", "UNKNOWN_PRICE_MISSING"]
    net_area_sqm: Decimal
    effective_area_with_wastage_sqm: Decimal
    material_and_substructure_cny: Decimal | None
    low_estimate_cny: Decimal | None
    high_estimate_cny: Decimal | None
    currency: str = "CNY"
    confidence_band_pct: int = 12
    data_benchmark_date: str


class VeProjectSummary(BaseModel):
    """Project-level deterministic Zero-LLM Decimal aggregation across facade/interior zones."""

    known_subtotal_cny: Decimal
    low_estimate_cny: Decimal
    high_estimate_cny: Decimal
    max_lead_time_days: int
    blocking_alerts_count: int
    warning_alerts_count: int
    has_missing_prices: bool
    missing_price_zone_ids: list[str]
    cost_status: Literal["CALCULATED", "PARTIAL_UNKNOWN_PRICE_MISSING"]
    currency: str = "CNY"


def lint_constructability(zone: VisualTectonicZone) -> list[ConstructabilityAlert]:
    """Run deterministic fabrication & building-detail checks (no LLM guessing)."""
    alerts: list[ConstructabilityAlert] = []
    vb = zone.visual_binding
    es = zone.engineering_state
    joined_specs = f"{zone.zone_id} {zone.zone_label} {es.detail_drawing_code} {' '.join(es.assembly_layers)}".lower()

    if es.construction_method == "wet_cast_in_situ" and vb.max_continuous_span_m > Decimal("4.5"):
        alerts.append(
            ConstructabilityAlert(
                code="WET_WORK_STREET_CONFLICT",
                severity="BLOCKING",
                zone_id=zone.zone_id,
                message=(
                    f"连续 {vb.max_continuous_span_m}m 现浇清水混凝土在临街商铺微更新场景"
                    f"需占道支模养护 ({es.lead_time_days} 天)，审批与工期风险极高。"
                ),
                remediation_hint="切换为 18mm 预制 UHPC 干挂板 (1200x2400) 或纤维水泥挂板全干法体系。",
            )
        )

    if "glazing" in zone.zone_id.lower() and vb.max_continuous_span_m > Decimal("3.2") and es.panel_modulus_mm is None:
        alerts.append(
            ConstructabilityAlert(
                code="JUMBO_GLASS_SPAN_EXCEEDED",
                severity="BLOCKING",
                zone_id=zone.zone_id,
                message=(
                    f"无框单块玻璃跨度达 {vb.max_continuous_span_m}m，超出常规货梯运输与钢化炉经济极值，"
                    "需封路动用重型随车吊。"
                ),
                remediation_hint="按 1700mm 模数增设极窄黑钢竖梃或切换为四扇铝合金折叠开启窗。",
            )
        )

    if not es.has_parapet_flashing or not es.has_recessed_plinth:
        alerts.append(
            ConstructabilityAlert(
                code="WEATHERPROOF_DETAIL_MISSING",
                severity="BLOCKING",
                zone_id=zone.zone_id,
                message="检测到女儿墙缺少金属泛水滴水线或底部直抵地面无防潮勒脚，交付半年内极易流挂返碱。",
                remediation_hint="注入 3mm 氟碳铝板压顶滴水线 + 80mm 不锈钢内凹防潮踢脚节点。",
            )
        )

    is_curved_monolith = vb.is_curved_geometry or any(tok in joined_specs for tok in ("curved", "弧", "grg"))
    if is_curved_monolith and es.lead_time_days > 21 and es.panel_modulus_mm is None:
        alerts.append(
            ConstructabilityAlert(
                code="CURVED_BESPOKE_FORMWORK_OVERFLOW",
                severity="BLOCKING",
                zone_id=zone.zone_id,
                message=(
                    f"双曲面异形无分缝定制整体饰面需 CNC 异形模具与现场分段批嵌养护 ({es.lead_time_days} 天)，"
                    "单方造价与接缝开裂风险显著超限。"
                ),
                remediation_hint="改用小幅面折叠直板多折线拟合曲面（600/900mm 干挂模数），彻底取消异形现场湿作业。",
            )
        )

    is_porous_earth = any(tok in joined_specs for tok in ("earth", "夯土", "rammed", "stucco", "土墙"))
    if (es.construction_method == "raw_hallucination" or is_porous_earth) and not es.has_recessed_plinth:
        alerts.append(
            ConstructabilityAlert(
                code="MOISTURE_UNSEALED_GROUND_CONTACT",
                severity="BLOCKING",
                zone_id=zone.zone_id,
                message="多孔吸湿表皮（生土/夯土/无机粉刷）直接触地且无疏水防潮勒脚，毛细虹吸将在首个雨季引起粉化剥落。",
                remediation_hint="增设 ≥120mm 花岗岩/不锈钢内凹防潮台基，并在饰面表面加注透气硅烷憎水封闭剂。",
            )
        )

    if es.lead_time_days > 21:
        alerts.append(
            ConstructabilityAlert(
                code="LEAD_TIME_COMMERCIAL_EXCEEDED",
                severity="WARNING",
                zone_id=zone.zone_id,
                message=f"当前工艺总生产/养护周期达 {es.lead_time_days} 天，超出 90-300㎡ 街区商铺高周转黄金窗口 (≤21 天)。",
                remediation_hint="优先切换工厂预制干挂或装配式模块化立面体系。",
            )
        )

    if es.construction_method == "dry_hanging_prefab" and es.panel_modulus_mm is not None:
        panel_area_mm2 = es.panel_modulus_mm.width * es.panel_modulus_mm.height
        if panel_area_mm2 > 3_200_000:
            alerts.append(
                ConstructabilityAlert(
                    code="EXCESSIVE_PANEL_MODULE_WEIGHT",
                    severity="WARNING",
                    zone_id=zone.zone_id,
                    message=(
                        f"单块干挂板尺寸 {es.panel_modulus_mm.width}x{es.panel_modulus_mm.height}mm "
                        f"({panel_area_mm2 / 1_000_000:.2f} ㎡ > 3.20 ㎡) 自重过大，需重型双背栓与升降脚手架配合。"
                    ),
                    remediation_hint="建议将单块板面拆分至 1200x2400mm（2.88 ㎡）或 600x1200mm 以适配双人干挂快装。",
                )
            )

    return alerts


def calculate_zone_cost(zone: VisualTectonicZone) -> CostBreakdown:
    """Zero-LLM Decimal arithmetic cost engine with wastage and +-12% confidence range."""
    vb = zone.visual_binding
    es = zone.engineering_state
    effective_area = (vb.estimated_area_sqm * es.wastage_factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if es.lump_sum_cny is not None:
        base_total = es.lump_sum_cny.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    elif es.unit_cost_cny_sqm is not None:
        all_in_rate = es.unit_cost_cny_sqm + es.substructure_amortization_cny_sqm
        base_total = (effective_area * all_in_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        # Strict honesty rule: unknown unit pricing MUST NOT silently become 0.
        return CostBreakdown(
            zone_id=zone.zone_id,
            status="UNKNOWN_PRICE_MISSING",
            net_area_sqm=vb.estimated_area_sqm,
            effective_area_with_wastage_sqm=effective_area,
            material_and_substructure_cny=None,
            low_estimate_cny=None,
            high_estimate_cny=None,
            data_benchmark_date=es.data_benchmark_date,
        )

    low = (base_total * Decimal("0.88")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    high = (base_total * Decimal("1.12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return CostBreakdown(
        zone_id=zone.zone_id,
        status="CALCULATED",
        net_area_sqm=vb.estimated_area_sqm,
        effective_area_with_wastage_sqm=effective_area,
        material_and_substructure_cny=base_total,
        low_estimate_cny=low,
        high_estimate_cny=high,
        data_benchmark_date=es.data_benchmark_date,
    )


def summarize_project_ve(zones: list[VisualTectonicZone]) -> VeProjectSummary:
    """Aggregate deterministic Decimal totals, alerts, and missing-price honesty flags across zones."""
    alerts = [alert for zone in zones for alert in lint_constructability(zone)]
    breakdowns = [calculate_zone_cost(zone) for zone in zones]

    known_subtotal = Decimal("0.00")
    missing_ids: list[str] = []
    for bd in breakdowns:
        if bd.status == "UNKNOWN_PRICE_MISSING" or bd.material_and_substructure_cny is None:
            missing_ids.append(bd.zone_id)
        else:
            known_subtotal += bd.material_and_substructure_cny

    known_subtotal = known_subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    low_est = (known_subtotal * Decimal("0.88")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    high_est = (known_subtotal * Decimal("1.12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return VeProjectSummary(
        known_subtotal_cny=known_subtotal,
        low_estimate_cny=low_est,
        high_estimate_cny=high_est,
        max_lead_time_days=max((z.engineering_state.lead_time_days for z in zones), default=0),
        blocking_alerts_count=sum(1 for a in alerts if a.severity == "BLOCKING"),
        warning_alerts_count=sum(1 for a in alerts if a.severity == "WARNING"),
        has_missing_prices=bool(missing_ids),
        missing_price_zone_ids=missing_ids,
        cost_status="PARTIAL_UNKNOWN_PRICE_MISSING" if missing_ids else "CALCULATED",
    )
