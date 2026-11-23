import type { SpectrumAxisId, SpectrumAxisReading } from '../engine/salienceMetric';

export type AssetDomain = 'architecture' | 'industrial' | 'editorial' | 'craft' | 'graphic';

export interface SpectrumAxisMeta {
  axis_id: SpectrumAxisId;
  label_zh: string;
  neg_label: string;
  pos_label: string;
  cross_domain_definition: string;
}

export interface AnchorBenchmarkPoint {
  level: -1 | -0.5 | 0 | 0.5 | 1;
  anchor_title_zh: string;
  anchor_title_en: string;
  physical_visual_criteria: string;
  cross_domain_examples: string;
  reference_asset_id: string;
}

export interface AxisCalibrationRubric {
  axis_id: SpectrumAxisId;
  label_zh: string;
  neg_label: string;
  pos_label: string;
  salience_gating_rule: string;
  anchors: AnchorBenchmarkPoint[];
}

export interface CuratedShowcaseAsset {
  asset_id: string;
  title: string;
  title_en?: string;
  image_url: string;
  license: string;
  source_kind: string;
  source_url?: string;
  akb_prior_asset_id?: string | null;
  akb_board_hint?: string | null;
  subject_isolation: {
    domain: AssetDomain;
    domain_label: string;
    primary_subject: string;
    is_personal_prior: boolean;
  };
  style_spectrums: Record<SpectrumAxisId, SpectrumAxisReading>;
  granular_descriptors: {
    optics_camera: string;
    lighting_rig: string;
    material_stack: string;
    color_palette: string[];
  };
  compiler_primitives: {
    positive_tokens: string[];
    negative_guardrails: string[];
  };
}

export interface ColdStartCostLedger {
  batch_size: number;
  duplicate_skip_rate: number;
  effective_vlm_calls: number;
  edge_deterministic_cost_cny_per_img: number;
  vlm_model_tier: string;
  cached_system_prompt_tokens: number;
  image_tokens_per_asset: number;
  uncached_user_tokens_per_asset: number;
  output_tokens_per_asset: number;
  usd_to_cny_rate: number;
  batch_discount_factor: number;
  total_batch_cost_cny: number;
  effective_cost_cny_per_img: number;
  target_ceiling_cny_per_img: number;
  within_budget: boolean;
}

export interface VlmScoringCostMetrics {
  scored_count: number;
  total_prompt_tokens: number;
  total_cached_tokens: number;
  total_uncached_prompt_tokens: number;
  total_completion_tokens: number;
  cache_hit_rate: number;
  avg_prompt_tokens_per_img: number;
  avg_completion_tokens_per_img: number;
  observed_online_total_cny: number;
  observed_online_cny_per_img: number;
  batch_api_equivalent_cny_per_img: number;
  target_ceiling_cny_per_img: number;
  within_budget: boolean;
}

export interface VlmScoringReport {
  version: string;
  generated_at: string;
  vlm_model: string;
  pydantic_validation_passed: number;
  total_assets: number;
  mean_spearman_rho: number;
  per_axis_spearman_rho: Record<SpectrumAxisId, number>;
  cost_metrics: VlmScoringCostMetrics;
}

export interface AstComparisonPair {
  pair_id: string;
  title_zh: string;
  subtitle_zh: string;
  subject_core: string;
  slots: {
    optics: string;
    material: string;
    lighting: string;
  };
  naive_image_url: string;
  ast_image_url: string;
  compiled_prompt: string;
  negative_guardrails: string[];
  conflicts_isolated_count: number;
  naive_failure_summary: string;
  ast_decoupling_summary: string;
}

export interface AstComparisonBundle {
  version: string;
  generated_at: string;
  total_pairs: number;
  pairs: AstComparisonPair[];
}

export interface AetherVaultShowcaseBundle {
  version: string;
  generated_at: string;
  total_assets: number;
  domain_counts: Record<AssetDomain, number>;
  axes: SpectrumAxisMeta[];
  golden_anchors: Record<SpectrumAxisId, AxisCalibrationRubric>;
  cost_ledger: ColdStartCostLedger;
  vlm_scoring_report?: VlmScoringReport;
  assets: CuratedShowcaseAsset[];
}
