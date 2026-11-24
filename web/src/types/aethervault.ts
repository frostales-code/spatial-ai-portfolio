import type { SpectrumAxisId, SpectrumAxisReading } from '../engine/salienceMetric';

export type AssetDomain = 'architecture' | 'industrial' | 'editorial' | 'craft' | 'graphic';

export type AssetArchetype =
  | 'interior'
  | 'architecture'
  | 'graphic_typography'
  | 'craft'
  | 'industrial'
  | 'landscape'
  | 'illustration_character'
  | 'fashion_photography';

export type AestheticStyleId = string;

export type RagFacetKey = 'medium' | 'typology' | 'materials' | 'lighting';

export interface RagFacets {
  medium: string;
  typology: string;
  materials: string[];
  lighting: string;
}

export interface RagDoc {
  doc_id: string;
  archetype: AssetArchetype;
  archetype_en: string;
  style_id: AestheticStyleId;
  style_zh: string;
  style_en: string;
  native_style_primary?: string;
  native_style_secondary?: string;
  is_canonical_ism?: boolean;
  facets: RagFacets;
  visual_traits?: string[];
  model_prompt_tokens: string[];
  palette: string[];
  aspect_ratio: string;
  resonance_mode?: 'core_match' | 'contrast_inspiration';
  retrieval_text: string;
}

export interface RagSchemaMeta {
  schema_version: string;
  vision_model?: string;
  embedding_model?: string;
  embedding_dim?: number;
  fusion_model?: string;
  max_styles: number;
  facet_keys: Array<{
    key: RagFacetKey;
    label_zh: string;
    cardinality: string;
    max_vocab: number;
  }>;
  styles: Array<{
    style_id: AestheticStyleId;
    zh: string;
    en: string;
    is_movement?: boolean;
    desc?: string;
    count: number;
  }>;
  facet_counts: Record<RagFacetKey, Array<{ value: string; count: number }>>;
  jsonl_url: string;
}

export interface AestheticCritique {
  headline_insight: string;
  proportion_and_order: string;
  material_and_detail: string;
  light_and_palette: string;
  why_you_love_it: string;
  design_takeaways: string[];
  resonance_mode?: 'core_match' | 'contrast_inspiration';
}

export interface ArchetypeTaxonomyNode {
  archetype: AssetArchetype;
  label: string;
  count: number;
  sub_styles: Array<{ sub_style: string; count: number }>;
}

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
  width?: number;
  height?: number;
  aspect_label?: string;
  license: string;
  source_kind: string;
  source_origin?: 'pinterest_personal' | 'profile_expansion';
  source_url?: string;
  board_name?: string;
  archetype?: AssetArchetype;
  archetype_label?: string;
  aesthetic_style?: AestheticStyleId;
  aesthetic_style_zh?: string;
  aesthetic_style_en?: string;
  is_canonical_ism?: boolean;
  native_style_primary?: string;
  native_style_secondary?: string;
  visual_traits?: string[];
  discovery_confidence?: number;
  sub_style?: string;
  sub_category?: string;
  rag_facets?: RagFacets;
  rag_doc?: RagDoc;
  map_2d?: { x: number; y: number };
  map_3d?: { x: number; y: number; z: number };
  core_distance?: number;
  similar_ids?: Array<{ asset_id: string; score: number }>;
  aesthetic_critique?: AestheticCritique;
  aesthetic_motifs?: string[];
  aesthetic_quality_score?: number;
  profile_distance?: number;
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

export interface PersonalAestheticProfile {
  total_pinterest_analyzed: number;
  kept_pinterest_count: number;
  expansion_count: number;
  axis_signature: Record<
    string,
    {
      weighted_mean: number;
      mean: number;
      std: number;
      p25: number;
      median: number;
      p75: number;
      mean_salience: number;
    }
  >;
  dominant_color_clusters: Array<{ hex: string; count: number }>;
  top_motifs: Array<{ motif: string; count: number }>;
  top_boards: Array<{ board: string; count: number }>;
  vlm_cost_audit?: {
    model: string;
    images_analyzed: number;
    cache_hit_rate: number;
    observed_total_cny: number;
    observed_cny_per_img: number;
  };
}

export interface AetherVaultShowcaseBundle {
  version: string;
  generated_at: string;
  total_assets: number;
  domain_counts: Record<AssetDomain, number>;
  origin_counts?: Record<string, number>;
  sub_category_counts?: Record<string, number>;
  archetype_taxonomy?: ArchetypeTaxonomyNode[];
  archetype_counts?: Record<string, number>;
  rag_schema?: RagSchemaMeta;
  axes: SpectrumAxisMeta[];
  golden_anchors: Record<SpectrumAxisId, AxisCalibrationRubric>;
  cost_ledger: ColdStartCostLedger;
  vlm_scoring_report?: VlmScoringReport;
  aesthetic_profile?: PersonalAestheticProfile | null;
  assets: CuratedShowcaseAsset[];
}
