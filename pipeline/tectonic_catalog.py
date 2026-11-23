"""Build M2 30-SKU Commercial Facade Catalog, Constructability Rules, CAD Sections & 3 Renovation Cases (`MIC-159`)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .tectonic_state import (
    EngineeringState,
    PanelModulusMm,
    VisualBinding,
    VisualTectonicZone,
    calculate_zone_cost,
    lint_constructability,
    summarize_project_ve,
)

CATALOG_OUT_PATH = Path(__file__).resolve().parent / "tectonic_catalog_v1.json"

LINT_RULES: list[dict[str, str]] = [
    {
        "code": "WET_WORK_STREET_CONFLICT",
        "severity": "BLOCKING",
        "title": "临街现浇湿作业跨度越界",
        "standard_basis": "《商业微更新快装施工与占道围挡限额规范 §3.2》",
        "physical_limit": "连续现浇清水混凝土跨度 > 4.5m 且养护期 > 21 天时，街区人行道不具备全封闭支模条件。",
        "remediation": "替换为 18mm 预制 UHPC 干挂板（1200×2400mm）或纤维水泥挂板装配体系。",
    },
    {
        "code": "JUMBO_GLASS_SPAN_EXCEEDED",
        "severity": "BLOCKING",
        "title": "无框超大玻璃运输与风压超限",
        "standard_basis": "《常见建筑玻璃制造极值与货梯进深规程 §4.1》",
        "physical_limit": "无竖梃玻璃单块净跨 > 3.2m 时，超出常规电梯与搬运极限，需特种吊车封路作业且热炸裂率陡增。",
        "remediation": "按 1200–1700mm 经济分格加设极窄黑钢竖梃或改用四扇折叠开启窗。",
    },
    {
        "code": "WEATHERPROOF_DETAIL_MISSING",
        "severity": "BLOCKING",
        "title": "檐口金属泛水与防潮踢脚缺失",
        "standard_basis": "《外墙饰面防水防返碱构造图集 J103-2》",
        "physical_limit": "女儿墙缺 3mm 滴水泛水压顶或墙脚直落人行道未设 ≥80mm 金属踢脚，雨季 6 个月内必然渗污返碱。",
        "remediation": "增设 3mm 氟碳铝板压顶滴水线、80mm 内凹不锈钢勒脚及雨棚结构斜拉杆。",
    },
    {
        "code": "CURVED_BESPOKE_FORMWORK_OVERFLOW",
        "severity": "BLOCKING",
        "title": "异形无缝双曲面定制工期与造价失控",
        "standard_basis": "《商业零售定制模具经济批量导则 §2.4》",
        "physical_limit": "连续异形曲面未作直板折线拆分（panel_modulus = None 且工期 > 21 天），模具摊销可达常规 6 倍。",
        "remediation": "采用多折线干挂铝合金板或预制水磨石/陶板小模数（600–900mm）分段拟合。",
    },
    {
        "code": "MOISTURE_UNSEALED_GROUND_CONTACT",
        "severity": "BLOCKING",
        "title": "多孔吸湿材质直触地面毛细虹吸隐患",
        "standard_basis": "《历史街区生土/无机墙体耐水耐久性指引 §5.1》",
        "physical_limit": "夯土、多孔灰泥等吸水性表皮直接接触街面地坪，雨水飞溅与地下潮气导致底层粉化脱落。",
        "remediation": "底层增设 ≥120mm 烧毛玄武岩或不锈钢防潮基座，表面喷涂透气有机硅憎水剂。",
    },
    {
        "code": "LEAD_TIME_COMMERCIAL_EXCEEDED",
        "severity": "WARNING",
        "title": "关键构件周期超出商业快装 21 天窗口",
        "standard_basis": "《90–300㎡ 商业街区免租金装修工期模型》",
        "physical_limit": "单一分项采购与现场固化周期超过 21 天，直接挤压门店免租期并推高综合财务成本。",
        "remediation": "优先选择标准化库存干挂板材或工厂预制模块化门窗框架。",
    },
    {
        "code": "EXCESSIVE_PANEL_MODULE_WEIGHT",
        "severity": "WARNING",
        "title": "单块预制板面积超过双人人工安装极值",
        "standard_basis": "《外墙干挂单板现场吊装安全标准 §6.3》",
        "physical_limit": "单块干挂饰面板面积 > 3.20 ㎡（例如 >1200×2400mm）时，单板自重超出双人徒手托举能力。",
        "remediation": "拆分为 1200×2400mm（2.88 ㎡）或 600×1200mm 标准规格。",
    },
    {
        "code": "UNKNOWN_PRICE_MISSING",
        "severity": "WARNING",
        "title": "定额库缺价强阻断（严禁静默置 0）",
        "standard_basis": "Zero-LLM Decimal 诚实工程计价规范 §1.1",
        "physical_limit": "定制非标手工饰面若尚未核定最新地区含税单价，算法绝不编造估算单价或折算为 0。",
        "remediation": "保留 UNKNOWN_PRICE_MISSING 标记并待供应商核价，或切换至已核价标准构造包。",
    },
]


def _cad_section_svg(
    code: str,
    title: str,
    wall_desc: str,
    cavity_desc: str,
    cladding_desc: str,
    joint_text: str,
    is_warning: bool = False,
) -> str:
    """Return crisp light-archival SVG cross-section schematic sized cleanly for CadDetailViewer."""
    accent = "#C62828" if is_warning else "#153CE8"
    return (
        f'<svg viewBox="0 0 360 220" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">'
        '<defs>'
        '<pattern id="cadHatch" width="8" height="8" patternUnits="userSpaceOnUse">'
        '<line x1="0" y1="8" x2="8" y2="0" stroke="#525866" stroke-width="0.7" opacity="0.45"/>'
        '</pattern>'
        '</defs>'
        '<rect x="0" y="0" width="360" height="220" fill="#FAFBFD"/>'
        # Base masonry wall section
        '<rect x="36" y="34" width="68" height="152" fill="url(#cadHatch)" stroke="#0E1015" stroke-width="1.5"/>'
        # Waterproof membrane
        '<line x1="108" y1="34" x2="108" y2="186" stroke="#0F766E" stroke-width="2" stroke-dasharray="4 2"/>'
        # Steel subframe / cavity
        '<rect x="122" y="54" width="48" height="16" fill="#E2E5EA" stroke="#0E1015" stroke-width="1.2"/>'
        '<rect x="122" y="138" width="48" height="16" fill="#E2E5EA" stroke="#0E1015" stroke-width="1.2"/>'
        '<line x1="146" y1="34" x2="146" y2="186" stroke="#525866" stroke-width="1" stroke-dasharray="2 3"/>'
        # Outer panel course top & bottom + joint shadow gap
        f'<rect x="176" y="34" width="16" height="68" fill="#FFFFFF" stroke="#0E1015" stroke-width="1.5"/>'
        f'<rect x="176" y="112" width="16" height="74" fill="#FFFFFF" stroke="#0E1015" stroke-width="1.5"/>'
        # Highlight joint dimension callout
        f'<line x1="168" y1="102" x2="206" y2="102" stroke="{accent}" stroke-width="1"/>'
        f'<line x1="168" y1="112" x2="206" y2="112" stroke="{accent}" stroke-width="1"/>'
        f'<line x1="200" y1="96" x2="200" y2="118" stroke="{accent}" stroke-width="1.2"/>'
        # Ground / Plinth datum
        '<line x1="24" y1="186" x2="220" y2="186" stroke="#0E1015" stroke-width="1.5"/>'
        # Callout annotations right side
        '<line x1="70" y1="48" x2="224" y2="48" stroke="#525866" stroke-width="0.8"/>'
        f'<text x="228" y="51" fill="#0E1015" font-size="10.5" font-family="Chivo Mono, sans-serif">{wall_desc}</text>'
        '<line x1="146" y1="62" x2="224" y2="82" stroke="#525866" stroke-width="0.8"/>'
        f'<text x="228" y="85" fill="#0E1015" font-size="10.5" font-family="Chivo Mono, sans-serif">{cavity_desc}</text>'
        f'<line x1="192" y1="107" x2="224" y2="118" stroke="{accent}" stroke-width="1"/>'
        f'<text x="228" y="121" fill="{accent}" font-size="10.5" font-weight="600" font-family="Chivo Mono, sans-serif">{joint_text}</text>'
        '<line x1="184" y1="148" x2="224" y2="152" stroke="#525866" stroke-width="0.8"/>'
        f'<text x="228" y="155" fill="#0E1015" font-size="10.5" font-family="Chivo Mono, sans-serif">{cladding_desc}</text>'
        f'<text x="36" y="206" fill="#525866" font-size="10" font-family="Chivo Mono, sans-serif">DETAIL {code}</text>'
        '</svg>'
    )


CAD_DETAILS: dict[str, dict[str, str]] = {
    "WARN-WET-CAST-01": {
        "code": "WARN-WET-CAST-01",
        "title": "现场定制木模现浇清水混凝土断面（受阻风险做法）",
        "svg": _cad_section_svg("WARN-WET-CAST-01", "现浇清水混凝土风险节点", "原基层结构", "双面木模支撑(占道)", "200mm现浇墙", "无分隔膨胀缝", is_warning=True),
    },
    "WARN-CURVE-GRG-02": {
        "code": "WARN-CURVE-GRG-02",
        "title": "连续异形双曲 GRG/抹灰定制体块（造价工期双超标）",
        "svg": _cad_section_svg("WARN-CURVE-GRG-02", "异形双曲定制风险节点", "钢网骨架", "异形 CNC 模具", "连续批嵌面层", "32天湿养护期", is_warning=True),
    },
    "WARN-EARTH-UNSEALED-03": {
        "code": "WARN-EARTH-UNSEALED-03",
        "title": "无踢脚防潮直落地生土饰面（雨水虹吸受潮风险）",
        "svg": _cad_section_svg("WARN-EARTH-UNSEALED-03", "无防潮踢脚生土风险节点", "旧砖墙基层", "直接粘接找平", "25mm未封闭生土", "直触地面返潮!", is_warning=True),
    },
    "STD-FAC-UHPC-04": {
        "code": "STD-FAC-UHPC-04",
        "title": "18mm 预制 UHPC 肌理挂板干挂标准节点（10mm 开放明缝）",
        "svg": _cad_section_svg("STD-FAC-UHPC-04", "18mm UHPC 干挂节点", "原墙防水砂浆", "50x50镀锌钢龙骨", "18mm预制UHPC板", "10mm开放阴影缝"),
    },
    "STD-FAC-FCB-09": {
        "code": "STD-FAC-FCB-09",
        "title": "12mm 高密纤维水泥挂板明装铆钉装配节点（600×1200 模数）",
        "svg": _cad_section_svg("STD-FAC-FCB-09", "12mm 纤维水泥快装节点", "防潮呼吸纸", "Z型轻钢龙骨", "12mm纤维水泥板", "8mm铝分缝+铆钉"),
    },
    "STD-FAC-ALU-12": {
        "code": "STD-FAC-ALU-12",
        "title": "2.5mm 氟碳穿孔铝单板多折线干挂节点（900×2400 模数）",
        "svg": _cad_section_svg("STD-FAC-ALU-12", "穿孔铝单板多折线干挂", "防水吸音无纺布", "40x40角钢副框", "2.5mm折边铝单板", "10mm硅酮耐候胶缝"),
    },
    "STD-FAC-TERRA-06": {
        "code": "STD-FAC-TERRA-06",
        "title": "30mm 空心陶瓷陶板幕墙干挂节点（600×1500 模数）",
        "svg": _cad_section_svg("STD-FAC-TERRA-06", "预制陶板干挂节点", "保温防水基层", "铝合金挂槽龙骨", "30mm挤出陶土板", "12mm通槽开放缝"),
    },
    "STD-FAC-WOOD-08": {
        "code": "STD-FAC-WOOD-08",
        "title": "碳化红雪松木条挂板通风幕墙与石材防潮基座节点",
        "svg": _cad_section_svg("STD-FAC-WOOD-08", "碳化木条+石材勒脚节点", "防白蚁呼吸膜", "防腐实木顺水条", "22mm碳化木挂板", "120mm石材防潮基"),
    },
}


def _sku(
    sku_id: str,
    category: str,
    name: str,
    tier: str,
    method: str,
    code: str,
    layers: list[str],
    unit_cost: str | None,
    sub_cost: str = "0",
    lump_sum: str | None = None,
    wastage: str = "1.08",
    days: int = 10,
    modulus: tuple[int, int, int, str] | None = None,
    has_flashing: bool = True,
    has_plinth: bool = True,
    default_area_sqm: float = 24.0,
    default_span_m: float = 3.0,
    is_curved: bool = False,
) -> dict[str, Any]:
    return {
        "sku_id": sku_id,
        "category": category,
        "name": name,
        "active_tier": tier,
        "construction_method": method,
        "detail_drawing_code": code,
        "assembly_layers": layers,
        "unit_cost_cny_sqm": unit_cost,
        "substructure_amortization_cny_sqm": sub_cost,
        "lump_sum_cny": lump_sum,
        "wastage_factor": wastage,
        "lead_time_days": days,
        "panel_modulus_mm": (
            {
                "width": modulus[0],
                "height": modulus[1],
                "joint_gap_mm": modulus[2],
                "joint_type": modulus[3],
            }
            if modulus
            else None
        ),
        "has_parapet_flashing": has_flashing,
        "has_recessed_plinth": has_plinth,
        "default_area_sqm": default_area_sqm,
        "default_span_m": default_span_m,
        "is_curved_geometry": is_curved,
    }


ASSEMBLIES_CATALOG: list[dict[str, Any]] = [
    # --- WALL CLADDING (12 SKUs) ---
    _sku(
        "cast_concrete_in_situ",
        "wall_cladding",
        "现浇弧形清水混凝土整体墙体（高风险湿作业）",
        "Tier_A_Bespoke",
        "wet_cast_in_situ",
        "WARN-WET-CAST-01",
        ["现场双面钢木组合定型模板支设", "P6 抗渗C40细石清水混凝土浇筑", "28天占道带模保湿养护"],
        "3800.00",
        "0.00",
        None,
        "1.12",
        28,
        None,
        True,
        True,
        24.0,
        7.2,
    ),
    _sku(
        "uhpc_dry_hang_1200",
        "wall_cladding",
        "18mm 预制 UHPC 超高性能混凝土干挂板 (1200×2400)",
        "Tier_B_Balanced",
        "dry_hanging_prefab",
        "STD-FAC-UHPC-04",
        ["基层：原砖墙水泥砂浆找平 + 防水涂膜", "龙骨：50×50×4mm 热镀锌方钢主龙骨", "饰面：18mm 预制 UHPC 肌理板（10mm 明缝）"],
        "520.00",
        "100.00",
        None,
        "1.08",
        12,
        (1200, 2400, 10, "open_shadow_gap"),
    ),
    _sku(
        "fiber_cement_600",
        "wall_cladding",
        "12mm 高密纤维水泥挂板 + 拉铆钉明装 (600×1200)",
        "Tier_C_Value",
        "dry_hanging_prefab",
        "STD-FAC-FCB-09",
        ["基层：单向防潮呼吸纸敷贴", "龙骨：1.5mm Z 型轻钢龙骨体系", "饰面：12mm 穿心高密纤维水泥板（8mm 阳极铝分缝条）"],
        "210.00",
        "80.00",
        None,
        "1.08",
        7,
        (600, 1200, 8, "anodized_alu_spline"),
    ),
    _sku(
        "perforated_alu_900",
        "wall_cladding",
        "2.5mm 氟碳喷涂穿孔铝单板多折线干挂 (900×2400)",
        "Tier_C_Value",
        "dry_hanging_prefab",
        "STD-FAC-ALU-12",
        ["基层：防水深灰吸音无纺布衬底", "龙骨：40×40 镀锌角钢骨架系统", "饰面：2.5mm 氟碳折边微穿孔铝单板"],
        "280.00",
        "80.00",
        None,
        "1.08",
        9,
        (900, 2400, 10, "silicone_weather_seal"),
    ),
    _sku(
        "limestone_dry_hang_900",
        "wall_cladding",
        "25mm 莱姆石背栓式干挂石材幕墙 (900×1800)",
        "Tier_A_Bespoke",
        "dry_hanging_prefab",
        "STD-FAC-UHPC-04",
        ["防水：聚合物水泥渗透结晶底涂", "龙骨：8#热镀锌槽钢主柱 + 不锈钢背栓", "饰面：25mm 米白荔枝面莱姆石板（6mm 胶缝）"],
        "780.00",
        "140.00",
        None,
        "1.12",
        15,
        (900, 1800, 6, "recessed_silicone"),
    ),
    _sku(
        "terracotta_baguette_600",
        "wall_cladding",
        "30mm 挤出自然窑变陶土板开放幕墙 (600×1500)",
        "Tier_B_Balanced",
        "dry_hanging_prefab",
        "STD-FAC-TERRA-06",
        ["基层：防水保温一体化岩棉层", "龙骨：定制T型铝合金干挂挂件系统", "饰面：30mm 空心挤压陶土板（12mm 通风开放缝）"],
        "560.00",
        "120.00",
        None,
        "1.10",
        14,
        (600, 1500, 12, "open_drained_joint"),
    ),
    _sku(
        "weathering_steel_1200",
        "wall_cladding",
        "3mm 耐候考登钢预锈折边干挂板 (1200×2400)",
        "Tier_B_Balanced",
        "dry_hanging_prefab",
        "STD-FAC-UHPC-04",
        ["底部设防锈溢流导水槽防污染铺装", "龙骨：镀锌角钢双向焊接背架", "饰面：3mm 厂内促锈钝化耐候钢板（10mm 明缝）"],
        "480.00",
        "100.00",
        None,
        "1.10",
        11,
        (1200, 2400, 10, "shadow_reveal_gap"),
    ),
    _sku(
        "flexible_stone_sheet_600",
        "wall_cladding",
        "4mm MCM 改性无机土柔性石材切片 (600×1200)",
        "Tier_C_Value",
        "dry_hanging_prefab",
        "STD-FAC-FCB-09",
        ["基层：原有实墙防碱封闭底漆+耐碱玻纤网", "粘结：柔性高弹聚合物瓷砖胶满刮", "饰面：4mm 柔性夯土/石材纹理切片（600 模数勾缝）"],
        "195.00",
        "45.00",
        None,
        "1.08",
        5,
        (600, 1200, 4, "grouted_modular_seam"),
    ),
    _sku(
        "mineral_stucco_grooved",
        "wall_cladding",
        "预制金属分隔条无机矿物泥灰分格墙体 (600×1200)",
        "Tier_C_Value",
        "dry_hanging_prefab",
        "STD-FAC-FCB-09",
        ["基层：水泥纤维板干式基底+不锈钢分缝条", "中间：抗裂网格布增强层", "饰面：2.5mm 天然无机石灰基哑光涂料 + 硅烷防潮封闭"],
        "240.00",
        "55.00",
        None,
        "1.08",
        6,
        (600, 1200, 6, "metal_reveal_bead"),
    ),
    _sku(
        "charred_cedar_siding",
        "wall_cladding",
        "22mm 碳化红雪松直纹木挂板装配系统 (600×2400)",
        "Tier_B_Balanced",
        "dry_hanging_prefab",
        "STD-FAC-WOOD-08",
        ["防蚁防水呼吸膜全墙铺设", "龙骨：防腐花旗松双向通风顺水木龙骨", "饰面：22mm 碳化拉丝红雪松实木挂板（防白蚁阻燃处理）"],
        "460.00",
        "90.00",
        None,
        "1.12",
        10,
        (600, 2400, 8, "ventilated_tongue_groove"),
    ),
    _sku(
        "curved_grg_monolith",
        "wall_cladding",
        "双曲面定制 GRG + 现场批嵌无缝弧形门头（超标异形）",
        "Tier_A_Bespoke",
        "raw_hallucination",
        "WARN-CURVE-GRG-02",
        ["三维扫描与CNC异形泡沫模具制作", "手工双曲玻璃纤维石膏拼装打磨", "室外现场 4 遍无缝抗裂腻子与养护"],
        "4200.00",
        "350.00",
        None,
        "1.15",
        32,
        None,
        True,
        True,
        32.0,
        8.4,
        is_curved=True,
    ),
    _sku(
        "bespoke_bronze_patina_unpriced",
        "wall_cladding",
        "定制手工锻铜硫肝做旧艺术挂板（待厂商实时询价 · 缺价验证）",
        "Tier_A_Bespoke",
        "dry_hanging_prefab",
        "STD-FAC-ALU-12",
        ["不锈钢双保险背栓龙骨系统", "手工锤纹锻铜表皮与天然抗氧化蜡封", "当前季度原材料铜价剧烈波动：暂无认证定额单价"],
        None,
        "0.00",
        None,
        "1.10",
        20,
        (900, 1800, 8, "bronze_reveal_joint"),
    ),
    # --- GLAZING PORTAL (8 SKUs) ---
    _sku(
        "jumbo_frameless_5200",
        "glazing_portal",
        "5.2m 整块超限无框超白夹胶玻璃（特种吊装）",
        "Tier_A_Bespoke",
        "raw_hallucination",
        "STD-FAC-UHPC-04",
        ["定制 15+15mm 超长超重钢化SGP夹胶玻璃", "地埋重型U型槽暗框", "封路特种随车吊夜间施工"],
        "6500.00",
        "0.00",
        None,
        "1.10",
        22,
        None,
        True,
        True,
        10.5,
        5.2,
    ),
    _sku(
        "mullion_steel_1700",
        "glazing_portal",
        "1.7m 三等分极窄黑钢竖梃中空玻璃幕墙",
        "Tier_B_Balanced",
        "curtain_wall_framed",
        "STD-FAC-UHPC-04",
        ["38×140mm 氟碳极窄精密黑钢竖梃立柱", "6+12A+6mm 双钢化 Low-E 节能中空玻璃", "常规地下货梯分段运输安装"],
        "1650.00",
        "0.00",
        None,
        "1.08",
        8,
        (1700, 2400, 12, "narrow_steel_mullion"),
        True,
        True,
        10.5,
        1.7,
    ),
    _sku(
        "folding_alu_4leaf",
        "glazing_portal",
        "窄边隔热断桥铝合金四扇折叠开启窗 + 咖啡外摆台",
        "Tier_C_Value",
        "curtain_wall_framed",
        "STD-FAC-FCB-09",
        ["重型上承重不锈钢隐藏滑轨五金", "四扇 1300mm 模数断桥铝合金折叠窗扇", "下方配 900mm 矮墙支撑外摆吧台挑板"],
        "1480.00",
        "0.00",
        None,
        "1.08",
        7,
        (1300, 2200, 10, "thermal_break_mullion"),
        True,
        True,
        10.5,
        1.3,
    ),
    _sku(
        "curved_jumbo_glass_4800",
        "glazing_portal",
        "4.8m 整块热弯异形超白无框弧形橱窗玻璃（高破损风险）",
        "Tier_A_Bespoke",
        "raw_hallucination",
        "WARN-CURVE-GRG-02",
        ["开模定制热弯超白夹胶玻璃", "弧形地面暗埋固定槽", "非标海运木箱专车运输"],
        "7400.00",
        "0.00",
        None,
        "1.12",
        30,
        None,
        True,
        True,
        14.0,
        4.8,
        is_curved=True,
    ),
    _sku(
        "faceted_steel_curtain_1200",
        "glazing_portal",
        "1.2m 折线拼接平玻黑钢幕墙系统（多折面拟合弧形）",
        "Tier_B_Balanced",
        "curtain_wall_framed",
        "STD-FAC-ALU-12",
        ["1.2m 等分折线高精度钢结构转换竖框", "平板钢化中空玻璃（零热弯开模费）", "标准化 EPDM 等压防水胶条"],
        "1820.00",
        "0.00",
        None,
        "1.09",
        10,
        (1200, 2400, 12, "faceted_steel_transom"),
        True,
        True,
        14.0,
        1.2,
    ),
    _sku(
        "timber_alu_composite_1500",
        "glazing_portal",
        "1.5m 模数室外铝包内部实木框格栅落地窗",
        "Tier_B_Balanced",
        "curtain_wall_framed",
        "STD-FAC-WOOD-08",
        ["外侧耐候喷涂氟碳铝型材保护罩", "内侧天然花旗松指接方木视觉暖质感框", "中空双银 Low-E 高透玻璃"],
        "1960.00",
        "0.00",
        None,
        "1.08",
        12,
        (1500, 2400, 10, "timber_alu_mullion"),
        True,
        True,
        9.6,
        1.5,
    ),
    _sku(
        "sliding_pocket_alu_1600",
        "glazing_portal",
        "1.6m 三轨嵌入式铝合金口袋推拉窗门系统",
        "Tier_C_Value",
        "curtain_wall_framed",
        "STD-FAC-FCB-09",
        ["下沉式平齐地轨铝合金门槽", "极窄边推拉窗扇可 2/3 面积全开启", "防夹手缓冲阻尼五金套件"],
        "1380.00",
        "0.00",
        None,
        "1.08",
        6,
        (1600, 2400, 10, "slim_alu_sliding_frame"),
        True,
        True,
        9.6,
        1.6,
    ),
    _sku(
        "low_e_modular_1400",
        "glazing_portal",
        "1.4m 标准模数铝合金明框高隔热幕墙",
        "Tier_C_Value",
        "curtain_wall_framed",
        "STD-FAC-ALU-12",
        ["PA66 尼龙隔热断桥铝主框", "1.4m 标准工厂流水线裁切玻璃板", "快装压块免打胶外饰盖板"],
        "1550.00",
        "0.00",
        None,
        "1.08",
        9,
        (1400, 2400, 10, "modular_alu_cap"),
        True,
        True,
        14.0,
        1.4,
    ),
    # --- EDGE & WEATHERPROOFING (5 SKUs) ---
    _sku(
        "zero_edge_raw_hallucination",
        "edge_weatherproofing",
        "零厚度刀锋挑檐 + 无踢脚墙皮直落人行道（缺防水构造）",
        "Tier_A_Bespoke",
        "raw_hallucination",
        "WARN-WET-CAST-01",
        ["概念渲染零厚度悬挑边缘", "无金属压顶与滴水凹槽", "地面无缝衔接但无防水泛水收口"],
        None,
        "0.00",
        "26950.00",
        "1.00",
        18,
        None,
        False,
        False,
        7.2,
        7.2,
    ),
    _sku(
        "alu_coping_plinth_canopy_std",
        "edge_weatherproofing",
        "3mm 氟碳铝板压顶滴水线 + 80mm 不锈钢内凹防潮踢脚 + 拉杆雨棚",
        "Tier_B_Balanced",
        "dry_hanging_prefab",
        "STD-FAC-UHPC-04",
        ["顶口：3mm 氟碳铝板泛水坡度 5% + 12mm 防滴水鹰嘴", "基座：80mm 304 拉丝不锈钢内凹防潮踢脚线", "门口：斜拉杆钢构雨棚防水引流"],
        None,
        "0.00",
        "8400.00",
        "1.00",
        5,
        None,
        True,
        True,
        7.2,
        2.4,
    ),
    _sku(
        "galvanized_drip_plinth_econ",
        "edge_weatherproofing",
        "2mm 烤漆镀锌钢泛水押顶 + 水泥基防潮收边踢脚（经济型）",
        "Tier_C_Value",
        "dry_hanging_prefab",
        "STD-FAC-FCB-09",
        ["2mm 热镀锌钢板折弯卡扣泛水押顶", "50mm 聚合物防水砂浆深色防潮踢脚边"],
        None,
        "0.00",
        "5600.00",
        "1.00",
        4,
        None,
        True,
        True,
        7.2,
        2.4,
    ),
    _sku(
        "stainless_drip_recessed_curb",
        "edge_weatherproofing",
        "4mm 黑钛不锈钢折边押顶 + 120mm 烧毛玄武岩防潮台基",
        "Tier_A_Bespoke",
        "dry_hanging_prefab",
        "STD-FAC-ALU-12",
        ["4mm 黑钛 304 不锈钢隐蔽自攻钉扣压顶", "120mm 高硬度烧毛黑玄武岩整石防踢底座", "隐藏线性落水暗槽"],
        None,
        "0.00",
        "9800.00",
        "1.00",
        6,
        None,
        True,
        True,
        8.4,
        2.4,
    ),
    _sku(
        "copper_eave_stone_plinth",
        "edge_weatherproofing",
        "历史风貌仿青铜氧化压顶檐口 + 120mm 花岗岩防潮勒脚",
        "Tier_B_Balanced",
        "dry_hanging_prefab",
        "STD-FAC-WOOD-08",
        ["传统老街深棕金属折边滴水屋檐压顶", "120mm 剁斧面灰麻花岗岩防水防返碱勒脚", "隐形导水檐沟"],
        None,
        "0.00",
        "10600.00",
        "1.00",
        8,
        None,
        True,
        True,
        6.6,
        2.2,
    ),
    # --- INTERIOR & THRESHOLD (5 SKUs) ---
    _sku(
        "flamed_basalt_600",
        "interior_threshold",
        "25mm 烧毛福鼎黑玄武岩入口防滑铺装 (600×1200)",
        "Tier_B_Balanced",
        "dry_hanging_prefab",
        "STD-FAC-WOOD-08",
        ["C25 半干硬性防水结合层", "25mm 烧毛防滑高致密玄武岩整板", "3mm 耐候聚氨酯伸缩缝"],
        "440.00",
        "65.00",
        None,
        "1.10",
        6,
        (600, 1200, 6, "expansion_stone_joint"),
    ),
    _sku(
        "terrazzo_precast_600",
        "interior_threshold",
        "20mm 无机水泥预制水磨石模块化墙地挂板 (600×600)",
        "Tier_C_Value",
        "dry_hanging_prefab",
        "STD-FAC-FCB-09",
        ["12mm 胶泥调平防潮基座", "20mm 预制哑光水磨石标准板", "渗入型抗油污纳米密封保护层"],
        "380.00",
        "50.00",
        None,
        "1.09",
        5,
        (600, 600, 4, "flush_brass_divider"),
    ),
    _sku(
        "microcement_sealed",
        "interior_threshold",
        "室外级聚氨酯双组份罩面微水泥护墙板 (600×1200)",
        "Tier_C_Value",
        "dry_hanging_prefab",
        "STD-FAC-FCB-09",
        ["防水纤维水泥预制衬板", "两道耐水微水泥批刮", "双组份哑光脂肪族聚氨酯抗紫外罩面"],
        "310.00",
        "40.00",
        None,
        "1.08",
        5,
        (600, 1200, 4, "hairline_control_joint"),
    ),
    _sku(
        "raw_rammed_earth_unsealed",
        "interior_threshold",
        "25mm 原生态无保护现夯土入口墙体（易渗湿粉化隐患）",
        "Tier_A_Bespoke",
        "raw_hallucination",
        "WARN-EARTH-UNSEALED-03",
        ["现场调配生土直接批覆在木砖基面上", "未掺加固化硅酸钠也无底层石材防潮踢脚", "多雨季直接面临雨水冲刷溶蚀风险"],
        "2950.00",
        "200.00",
        None,
        "1.14",
        26,
        None,
        False,
        False,
        21.0,
        6.6,
    ),
    _sku(
        "acoustic_timber_slat_600",
        "interior_threshold",
        "门廊吸音实木格栅预制组件 (600×2400)",
        "Tier_B_Balanced",
        "dry_hanging_prefab",
        "STD-FAC-WOOD-08",
        ["9mm 黑色高密聚酯纤维吸音背板", "阻燃处理白橡/杉木实木格栅条", "免油漆快卡扣挂件安装"],
        "390.00",
        "60.00",
        None,
        "1.08",
        5,
        (600, 2400, 6, "slat_shadow_reveal"),
    ),
]

SKU_BY_ID: dict[str, dict[str, Any]] = {item["sku_id"]: item for item in ASSEMBLIES_CATALOG}


def _zone_from_sku(
    zone_id: str,
    zone_label: str,
    sam_mask_ref: str,
    normal: tuple[float, float, float],
    area_sqm: float,
    span_m: float,
    sku_id: str,
    is_curved_override: bool | None = None,
) -> VisualTectonicZone:
    s = SKU_BY_ID[sku_id]
    modulus_data = s["panel_modulus_mm"]
    modulus = PanelModulusMm(**modulus_data) if modulus_data else None
    is_curved = bool(s["is_curved_geometry"]) if is_curved_override is None else is_curved_override
    return VisualTectonicZone(
        zone_id=zone_id,
        zone_label=zone_label,
        visual_binding=VisualBinding(
            sam_mask_ref=sam_mask_ref,
            perspective_plane_normal=normal,
            estimated_area_sqm=Decimal(str(area_sqm)),
            max_continuous_span_m=Decimal(str(span_m)),
            is_curved_geometry=is_curved,
        ),
        engineering_state=EngineeringState(
            active_tier=s["active_tier"],
            assembly_layers=s["assembly_layers"],
            panel_modulus_mm=modulus,
            construction_method=s["construction_method"],
            detail_drawing_code=s["detail_drawing_code"],
            has_parapet_flashing=s["has_parapet_flashing"],
            has_recessed_plinth=s["has_recessed_plinth"],
            unit_cost_cny_sqm=Decimal(s["unit_cost_cny_sqm"]) if s["unit_cost_cny_sqm"] is not None else None,
            wastage_factor=Decimal(s["wastage_factor"]),
            substructure_amortization_cny_sqm=Decimal(s["substructure_amortization_cny_sqm"]),
            lump_sum_cny=Decimal(s["lump_sum_cny"]) if s["lump_sum_cny"] is not None else None,
            lead_time_days=int(s["lead_time_days"]),
            data_benchmark_date="2026-11-23",
        ),
    )


def _evaluate_tier(
    tier_id: str,
    tier_label: str,
    short_label: str,
    zone_specs: list[tuple[str, str, str, tuple[float, float, float], float, float, str, bool | None]],
) -> dict[str, Any]:
    zones = [_zone_from_sku(*spec) for spec in zone_specs]
    summary = summarize_project_ve(zones)
    alerts = [a.model_dump() for z in zones for a in lint_constructability(z)]
    breakdowns = [calculate_zone_cost(z).model_dump(mode="json") for z in zones]

    return {
        "tier_id": tier_id,
        "tier_label": tier_label,
        "short_label": short_label,
        "zones": [
            {
                **z.model_dump(mode="json"),
                "sku_id": zone_specs[i][6],
                "sku_name": SKU_BY_ID[zone_specs[i][6]]["name"],
            }
            for i, z in enumerate(zones)
        ],
        "alerts": alerts,
        "cost_breakdowns": breakdowns,
        "summary": summary.model_dump(mode="json"),
    }


def build_cases_state_trees() -> list[dict[str, Any]]:
    """Construct 3 complete street-front commercial renovation state trees with deterministic BOM & alerts."""
    return [
        {
            "case_id": "case_01_corner_cafe",
            "title": "90㎡ 街角精品咖啡馆立面改造",
            "subtitle": "清水质感概念图的干挂化与外摆开启窗价值工程",
            "site_context": "沿街一层转角老房底层更新，人行道紧邻门店，禁止长时间封路现浇支模，黄昏有高大梧桐树影投射在右侧墙面与人行道。",
            "scale_anchor": {
                "facade_width_mm": 7200,
                "facade_height_mm": 3400,
                "door_height_mm": 2200,
                "label": "门高 2,200mm | 总面宽 7,200mm | 总饰面面积 34.5 ㎡",
            },
            "tiers": [
                _evaluate_tier(
                    "tier_0_raw",
                    "状态 0 · 原始 AI 概念图（物理与工期隐患）",
                    "原始概念态",
                    [
                        ("facade_wall_01", "Zone A · 主立面墙体 (24.0 ㎡)", "mask_c1_wall.png", (0.04, 0.99, 0.12), 24.0, 7.2, "cast_concrete_in_situ", False),
                        ("glazing_portal_02", "Zone B · 临街采光界面 (10.5 ㎡)", "mask_c1_glass.png", (0.04, 0.99, 0.12), 10.5, 5.2, "jumbo_frameless_5200", False),
                        ("edge_weather_03", "Zone C · 檐口泛水与勒脚 (7.2 m)", "mask_c1_edge.png", (0.04, 0.99, 0.12), 7.2, 7.2, "zero_edge_raw_hallucination", False),
                    ],
                ),
                _evaluate_tier(
                    "tier_1_balanced",
                    "反向约束 A · 商业均衡 UHPC 干挂（1200×2400mm）",
                    "商业均衡干挂",
                    [
                        ("facade_wall_01", "Zone A · 主立面墙体 (24.0 ㎡)", "mask_c1_wall.png", (0.04, 0.99, 0.12), 24.0, 1.2, "uhpc_dry_hang_1200", False),
                        ("glazing_portal_02", "Zone B · 临街采光界面 (10.5 ㎡)", "mask_c1_glass.png", (0.04, 0.99, 0.12), 10.5, 1.7, "mullion_steel_1700", False),
                        ("edge_weather_03", "Zone C · 檐口泛水与勒脚 (7.2 m)", "mask_c1_edge.png", (0.04, 0.99, 0.12), 7.2, 2.4, "alu_coping_plinth_canopy_std", False),
                    ],
                ),
                _evaluate_tier(
                    "tier_2_value",
                    "反向约束 B · 7 天快装控本纤维水泥板（600×1200mm）",
                    "极限快装控本",
                    [
                        ("facade_wall_01", "Zone A · 主立面墙体 (24.0 ㎡)", "mask_c1_wall.png", (0.04, 0.99, 0.12), 24.0, 0.6, "fiber_cement_600", False),
                        ("glazing_portal_02", "Zone B · 临街采光界面 (10.5 ㎡)", "mask_c1_glass.png", (0.04, 0.99, 0.12), 10.5, 1.3, "folding_alu_4leaf", False),
                        ("edge_weather_03", "Zone C · 檐口泛水与勒脚 (7.2 m)", "mask_c1_edge.png", (0.04, 0.99, 0.12), 7.2, 2.4, "galvanized_drip_plinth_econ", False),
                    ],
                ),
            ],
        },
        {
            "case_id": "case_02_concept_boutique",
            "title": "180㎡ 设计师买手店超限弧形门头更新",
            "subtitle": "双曲面开模幻觉拆解为多折线阳极金属与平玻幕墙体系",
            "site_context": "商圈核心铺位改造，原方案包含超限双曲连续 GRG 与整块热弯玻璃，总周期超 32 天且单方破 4 千；需维持雕塑级几何张力并控本至 10 天全干法安装。",
            "scale_anchor": {
                "facade_width_mm": 8400,
                "facade_height_mm": 4200,
                "door_height_mm": 2400,
                "label": "门高 2,400mm | 总面宽 8,400mm | 总饰面面积 46.0 ㎡",
            },
            "tiers": [
                _evaluate_tier(
                    "tier_0_raw",
                    "状态 0 · 原始 AI 概念图（异形模具与热弯超限）",
                    "原始概念态",
                    [
                        ("facade_wall_01", "Zone A · 弧形主门头表皮 (32.0 ㎡)", "mask_c2_wall.png", (0.08, 0.98, 0.15), 32.0, 8.4, "curved_grg_monolith", True),
                        ("glazing_portal_02", "Zone B · 热弯弧形大橱窗 (14.0 ㎡)", "mask_c2_glass.png", (0.08, 0.98, 0.15), 14.0, 4.8, "curved_jumbo_glass_4800", True),
                        ("edge_weather_03", "Zone C · 女儿墙收口与踢脚 (8.4 m)", "mask_c2_edge.png", (0.08, 0.98, 0.15), 8.4, 8.4, "zero_edge_raw_hallucination", False),
                    ],
                ),
                _evaluate_tier(
                    "tier_1_balanced",
                    "反向约束 A · 多折线穿孔铝单板 + 1.2m 折面钢玻幕墙",
                    "多折线金属干挂",
                    [
                        ("facade_wall_01", "Zone A · 折线主门头表皮 (32.0 ㎡)", "mask_c2_wall.png", (0.08, 0.98, 0.15), 32.0, 0.9, "perforated_alu_900", False),
                        ("glazing_portal_02", "Zone B · 折线平玻钢构橱窗 (14.0 ㎡)", "mask_c2_glass.png", (0.08, 0.98, 0.15), 14.0, 1.2, "faceted_steel_curtain_1200", False),
                        ("edge_weather_03", "Zone C · 压顶与玄武岩台基 (8.4 m)", "mask_c2_edge.png", (0.08, 0.98, 0.15), 8.4, 2.4, "stainless_drip_recessed_curb", False),
                    ],
                ),
                _evaluate_tier(
                    "tier_2_value",
                    "反向约束 B · 耐候金属分隔泥灰挂板 + 1.4m 标准模数玻璃",
                    "极简快装控本",
                    [
                        ("facade_wall_01", "Zone A · 分格矿物质挂板 (32.0 ㎡)", "mask_c2_wall.png", (0.08, 0.98, 0.15), 32.0, 0.6, "mineral_stucco_grooved", False),
                        ("glazing_portal_02", "Zone B · 1.4m 模数断桥玻璃 (14.0 ㎡)", "mask_c2_glass.png", (0.08, 0.98, 0.15), 14.0, 1.4, "low_e_modular_1400", False),
                        ("edge_weather_03", "Zone C · 镀锌泛水与防潮踢脚 (8.4 m)", "mask_c2_edge.png", (0.08, 0.98, 0.15), 8.4, 2.4, "galvanized_drip_plinth_econ", False),
                    ],
                ),
            ],
        },
        {
            "case_id": "case_03_oldstreet_teahouse",
            "title": "120㎡ 历史老街茶空间立面微更新",
            "subtitle": "防潮台基加注与陶板/碳化木同效温润肌理降本替补",
            "site_context": "江南历史街区青石板街侧立面，原概念渲染呈现未经防潮封闭直接触地的夯土壁面，需替换为耐雨淋装配式东方质感材料并严守街巷竹影光感。",
            "scale_anchor": {
                "facade_width_mm": 6600,
                "facade_height_mm": 3200,
                "door_height_mm": 2150,
                "label": "门高 2,150mm | 总面宽 6,600mm | 总饰面面积 30.6 ㎡",
            },
            "tiers": [
                _evaluate_tier(
                    "tier_0_raw",
                    "状态 0 · 原始 AI 概念图（生土直触地与无泛水风险）",
                    "原始概念态",
                    [
                        ("facade_wall_01", "Zone A · 主立面墙体 (21.0 ㎡)", "mask_c3_wall.png", (-0.05, 0.99, 0.11), 21.0, 6.6, "raw_rammed_earth_unsealed", False),
                        ("glazing_portal_02", "Zone B · 茶室采光大窗 (9.6 ㎡)", "mask_c3_glass.png", (-0.05, 0.99, 0.11), 9.6, 4.2, "jumbo_frameless_5200", False),
                        ("edge_weather_03", "Zone C · 挑檐与底部勒脚 (6.6 m)", "mask_c3_edge.png", (-0.05, 0.99, 0.11), 6.6, 6.6, "zero_edge_raw_hallucination", False),
                    ],
                ),
                _evaluate_tier(
                    "tier_1_balanced",
                    "反向约束 A · 碳化红雪松木挂板 + 铝包木窗 + 花岗岩勒脚",
                    "碳化木与石材勒脚",
                    [
                        ("facade_wall_01", "Zone A · 主立面墙体 (21.0 ㎡)", "mask_c3_wall.png", (-0.05, 0.99, 0.11), 21.0, 0.6, "charred_cedar_siding", False),
                        ("glazing_portal_02", "Zone B · 铝包木格栅落地窗 (9.6 ㎡)", "mask_c3_glass.png", (-0.05, 0.99, 0.11), 9.6, 1.5, "timber_alu_composite_1500", False),
                        ("edge_weather_03", "Zone C · 铜色泛水与花岗岩勒脚 (6.6 m)", "mask_c3_edge.png", (-0.05, 0.99, 0.11), 6.6, 2.2, "copper_eave_stone_plinth", False),
                    ],
                ),
                _evaluate_tier(
                    "tier_2_value",
                    "反向约束 B · MCM 柔性夯土切片 + 推拉开启窗（5 天极速）",
                    "柔性夯土快装",
                    [
                        ("facade_wall_01", "Zone A · 柔性夯土纹理墙体 (21.0 ㎡)", "mask_c3_wall.png", (-0.05, 0.99, 0.11), 21.0, 0.6, "flexible_stone_sheet_600", False),
                        ("glazing_portal_02", "Zone B · 三轨推拉开启门窗 (9.6 ㎡)", "mask_c3_glass.png", (-0.05, 0.99, 0.11), 9.6, 1.6, "sliding_pocket_alu_1600", False),
                        ("edge_weather_03", "Zone C · 镀锌压顶与防潮边 (6.6 m)", "mask_c3_edge.png", (-0.05, 0.99, 0.11), 6.6, 2.2, "galvanized_drip_plinth_econ", False),
                    ],
                ),
            ],
        },
    ]


def build_catalog_bundle() -> dict[str, Any]:
    """Assemble full structured M2 catalog JSON ready for persistence and FastAPI serving."""
    cases = build_cases_state_trees()
    category_counts: dict[str, int] = {}
    for sku in ASSEMBLIES_CATALOG:
        cat = str(sku["category"])
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "version": "1.0.0",
        "benchmark_date": "2026-11-23",
        "total_assemblies": len(ASSEMBLIES_CATALOG),
        "category_counts": category_counts,
        "assemblies": ASSEMBLIES_CATALOG,
        "lint_rules": LINT_RULES,
        "cad_details": CAD_DETAILS,
        "cases": cases,
    }


def main() -> None:
    bundle = build_catalog_bundle()
    CATALOG_OUT_PATH.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"[OK] Wrote {bundle['total_assemblies']} assemblies, "
        f"{len(bundle['lint_rules'])} lint rules, "
        f"{len(bundle['cad_details'])} CAD SVGs, "
        f"{len(bundle['cases'])} cases to {CATALOG_OUT_PATH}"
    )


if __name__ == "__main__":
    main()
