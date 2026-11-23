export type AssemblyCategory =
  | 'wall_cladding'
  | 'glazing_portal'
  | 'edge_weatherproofing'
  | 'interior_threshold';

export type ConstructionMethod =
  | 'wet_cast_in_situ'
  | 'dry_hanging_prefab'
  | 'curtain_wall_framed'
  | 'raw_hallucination';

export interface PanelModulusMm {
  width: number;
  height: number;
  joint_gap_mm: number;
  joint_type: string;
}

export interface TectonicAssemblySku {
  sku_id: string;
  category: AssemblyCategory;
  name: string;
  active_tier: 'Tier_A_Bespoke' | 'Tier_B_Balanced' | 'Tier_C_Value';
  construction_method: ConstructionMethod;
  detail_drawing_code: string;
  assembly_layers: string[];
  unit_cost_cny_sqm: string | null;
  substructure_amortization_cny_sqm: string;
  lump_sum_cny: string | null;
  wastage_factor: string;
  lead_time_days: number;
  panel_modulus_mm: PanelModulusMm | null;
  has_parapet_flashing: boolean;
  has_recessed_plinth: boolean;
  default_area_sqm: number;
  default_span_m: number;
  is_curved_geometry: boolean;
}

export interface ConstructabilityLintRule {
  code: string;
  severity: 'BLOCKING' | 'WARNING';
  title: string;
  standard_basis: string;
  physical_limit: string;
  remediation: string;
}

export interface CadDetailDiagram {
  code: string;
  title: string;
  svg: string;
}

export interface Point2D {
  x: number;
  y: number;
}

export interface ProjectedSeamSegment {
  orientation: 'vertical' | 'horizontal';
  start: Point2D;
  end: Point2D;
}

export interface HomographyProjectionData {
  homography_matrix: number[][];
  inverse_homography_matrix: number[][];
  seam_segments: ProjectedSeamSegment[];
  vertical_vanishing_deviation_deg: number;
  panel_count_estimate: number;
}

export interface RelightMetricsData {
  non_mask_psnr_db: number;
  shadow_luma_corr: number;
  vertical_vanishing_deviation_deg: number;
}

export interface TectonicAlert {
  code: string;
  severity: 'BLOCKING' | 'WARNING';
  zone_id: string;
  message: string;
  remediation_hint: string;
}

export interface ZoneCostBreakdown {
  zone_id: string;
  status: 'CALCULATED' | 'UNKNOWN_PRICE_MISSING';
  net_area_sqm: string;
  effective_area_with_wastage_sqm: string;
  material_and_substructure_cny: string | null;
  low_estimate_cny: string | null;
  high_estimate_cny: string | null;
  currency: string;
  confidence_band_pct: number;
  data_benchmark_date: string;
}

export interface VeProjectSummaryJson {
  known_subtotal_cny: string;
  low_estimate_cny: string;
  high_estimate_cny: string;
  max_lead_time_days: number;
  blocking_alerts_count: number;
  warning_alerts_count: number;
  has_missing_prices: boolean;
  missing_price_zone_ids: string[];
  cost_status: 'CALCULATED' | 'PARTIAL_UNKNOWN_PRICE_MISSING';
  currency: string;
}

export interface TectonicZoneState {
  zone_id: string;
  zone_label: string;
  sku_id?: string;
  sku_name?: string;
  visual_binding: {
    sam_mask_ref: string;
    perspective_plane_normal: [number, number, number];
    estimated_area_sqm: string;
    max_continuous_span_m: string;
    is_curved_geometry: boolean;
  };
  engineering_state: {
    active_tier: 'Tier_A_Bespoke' | 'Tier_B_Balanced' | 'Tier_C_Value';
    assembly_layers: string[];
    panel_modulus_mm: PanelModulusMm | null;
    construction_method: ConstructionMethod;
    detail_drawing_code: string;
    has_parapet_flashing: boolean;
    has_recessed_plinth: boolean;
    unit_cost_cny_sqm: string | null;
    wastage_factor: string;
    substructure_amortization_cny_sqm: string;
    lump_sum_cny: string | null;
    lead_time_days: number;
    data_benchmark_date: string;
  };
}

export interface TectonicTierState {
  tier_id: 'tier_0_raw' | 'tier_1_balanced' | 'tier_2_value';
  tier_label: string;
  short_label: string;
  image_url: string;
  homography_projection: HomographyProjectionData;
  relight_metrics: RelightMetricsData;
  zones: TectonicZoneState[];
  alerts: TectonicAlert[];
  cost_breakdowns: ZoneCostBreakdown[];
  summary: VeProjectSummaryJson;
}

export interface TectonicDiagnosticPin {
  zone_id: string;
  x_pct: number;
  y_pct: number;
}

export interface TectonicCase {
  case_id: string;
  title: string;
  subtitle: string;
  site_context: string;
  scale_anchor: {
    facade_width_mm: number;
    facade_height_mm: number;
    door_height_mm: number;
    label: string;
  };
  geometry?: {
    facade_quad_px: Point2D[];
    diagnostic_pins_pct: TectonicDiagnosticPin[];
  };
  tiers: TectonicTierState[];
}

export interface TectonicShowcaseBundle {
  version: string;
  benchmark_date: string;
  generated_at?: string;
  total_assemblies: number;
  category_counts: Record<string, number>;
  assemblies: TectonicAssemblySku[];
  lint_rules: ConstructabilityLintRule[];
  cad_details: Record<string, CadDetailDiagram>;
  cases: TectonicCase[];
}
