export interface EvalScatterPoint {
  asset_id: string;
  axis: string;
  domain: string;
  expert_score: number;
  vlm_score: number;
  salience: number;
  expert_salience: number;
}

export interface TiltSweepRow {
  tilt_deg: number;
  edge_stretch_ratio: number;
  vanishing_deviation_deg: number;
  guardrail_triggered: boolean;
  action: string;
}

export interface CostBacktestRow {
  case_id: string;
  name: string;
  predicted_cny: number;
  low_cny: number;
  high_cny: number;
  actual_settlement_cny: number;
  variance_pct: number;
  within_15pct: boolean;
  blocking_alerts: number;
}

export interface EddBenchmarkBundle {
  version: string;
  generated_at: string;
  eval_01_spearman: {
    total_assets: number;
    pydantic_pass_rate: number;
    blind_baseline_rho: number;
    raw_vlm_first_pass_rho: number;
    observed_mean_spearman_rho: number;
    rho_gain_pct: number;
    queries_evaluated: number;
    top5_cross_domain_diversity_rate: number;
    top5_salience_alignment_rate: number;
    top5_uniform_alignment_rate: number;
    rerank_latency_p50_ms: number;
    rerank_latency_p95_ms: number;
    scatter_points: EvalScatterPoint[];
    bad_case_trace: {
      case_code: string;
      title: string;
      low_salience_graphic_assets_count: number;
      uniform_top10_graphic_leaks: string[];
      salience_gated_top10_graphic_leaks: string[];
      mitigation: string;
    };
  };
  eval_02_decouple: {
    tasks_evaluated: number;
    rendered_visual_ab_pairs: number;
    naive_ip_adapter_baseline_rate: number;
    ast_composite_decoupling_rate: number;
    optics_lock_rate: number;
    material_scope_isolation_rate: number;
    lighting_isolation_rate: number;
    zero_foreign_entity_leak_rate: number;
    total_lexical_conflicts_isolated: number;
    avg_conflicts_isolated_per_task: number;
  };
  eval_03_homography: {
    cases_evaluated: number;
    relit_tiers_evaluated: number;
    max_roundtrip_rmse_px: number;
    max_vanishing_deviation_deg: number;
    min_non_mask_psnr_db: number;
    avg_shadow_luma_corr: number;
    all_cases_passed_gate: boolean;
    bad_case_trace: {
      case_code: string;
      title: string;
      stretch_threshold_ratio: number;
      tilt_sweep: TiltSweepRow[];
      mitigation: string;
    };
  };
  eval_04_cost_backtest: {
    settlements_evaluated: number;
    hits_within_15pct: number;
    interval_hit_rate: number;
    target_hit_rate: number;
    avg_calc_latency_ms: number;
    case_results: CostBacktestRow[];
    bad_case_trace: {
      case_code: string;
      title: string;
      cost_status_returned: string;
      summary_cost_status: string;
      has_missing_prices: boolean;
      fabricated_zero_blocked: boolean;
      lint_alerts_triggered: string[];
      mitigation: string;
    };
  };
}
