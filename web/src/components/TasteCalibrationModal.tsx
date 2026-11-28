'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Check,
  CheckCircle2,
  Compass,
  Heart,
  Layers,
  Loader2,
  RefreshCw,
  Scale,
  ShieldCheck,
  Shuffle,
  SkipForward,
  Sparkles,
  X,
} from 'lucide-react';

interface PairCard {
  asset_id: string;
  title: string;
  image_url: string;
  source_origin?: string;
  archetype: string;
  archetype_label: string;
  aesthetic_style_zh?: string;
  typology?: string;
  max_medoid_sim: number;
  nearest_medoid_id: string;
  contrast_axis: string | null;
  contrast_reason_zh?: string;
  image_species?: string;
  subject_structure?: string;
  primary_family_zh?: string;
  secondary_family_zh?: string;
  overarching_principle?: string;
  candidate_reasons?: Array<{ p: string; tag: string; text: string }>;
}

interface AestheticFamilySample {
  asset_id: string;
  title: string;
  image_url: string;
  board_name: string;
  secondary_family_zh: string;
  verdict_why: string;
  overarching_principle: string;
  res_score: number;
}

interface AestheticFamilyCard {
  key: string;
  num: string;
  name: string;
  short: string;
  desc: string;
  count: number;
  pct: number;
  samples: AestheticFamilySample[];
}

interface AestheticFamiliesSummary {
  total_personal_pins: number;
  pragmatic_noise_count: number;
  families: AestheticFamilyCard[];
  top_tensions: Array<{ pair: string; count: number }>;
  reason_chips: Array<{ key: string; label: string }>;
  reason_attribution: {
    total_votes_with_reasons: number;
    tie_like_votes_with_reasons: number;
    top_reasons: Array<{ label: string; count: number }>;
    recent_notes: Array<{ asset_a: string; asset_b: string; choice: string; note: string }>;
  };
}

interface CalibrationPair {
  signal: 'core_taste' | 'serendipity_save';
  stratum: string;
  stratum_badge_zh: string;
  question_zh: string;
  hint_zh: string;
  a: PairCard;
  b: PairCard;
}

interface MedoidItem {
  medoid_id: string;
  asset_id: string;
  title: string;
  image_url: string;
  archetype_label: string;
  aesthetic_style_zh: string;
  cluster_size: number;
  cluster_weight: number;
}

interface AnchorCard {
  asset_id: string;
  title: string;
  image_url: string;
  archetype: string;
  archetype_label: string;
  aesthetic_style_zh: string;
  role: string;
  max_medoid_sim: number;
  contrast_axis: string | null;
  contrast_reason_zh: string;
  contrast_score: number;
  passes_pixel_contrast: boolean;
  low_personal_prior: boolean;
  craft_confirmed: boolean;
  contrast_confirmed: boolean | null;
  user_confirmed: boolean;
}

interface DomainAnchorPair {
  domain: string;
  domain_label: string;
  familiar_anchor: AnchorCard;
  contrast_anchor: AnchorCard;
}

interface CalibrationState {
  version: string;
  profile: {
    k_medoids: number;
    personal_count: number;
    total_atlas_count: number;
    medoids: MedoidItem[];
  };
  anchors: {
    domains: Record<string, DomainAnchorPair>;
  };
  confirmed_anchors: number;
  confirmed_contrast: number;
  total_anchors: number;
  total_contrast_anchors: number;
  vote_counts: {
    core_taste_total: number;
    core_taste_stratified: number;
    legacy_cross_domain_diagnostic: number;
    tie_like_count: number;
    cannot_compare_count: number;
    stratum_counts: Record<string, number>;
    serendipity_total: number;
    serendipity_saved: number;
    trial_budget_target: number;
  };
  rerank_summary: {
    latency_ms: number;
    lane_counts: {
      core_resonance: number;
      cross_domain_bridge: number;
      adversarial_exploration: number;
      exploration_qualified_pool: number;
      exploration_cap: number;
      exploration_underfilled_honestly: boolean;
    };
    bt_model: {
      fitted: boolean;
      n_stratified_pairs: number;
      legacy_cross_domain_diagnostic: number;
      train_acc: number | null;
      cv_acc: number | null;
      cv_logloss: number | null;
      macro_only_acc: number | null;
      max_medoid_acc: number | null;
      single_centroid_acc: number | null;
      beta_micro5?: number[];
      beta_labels?: string[];
    };
    serendipity_eval: {
      n_votes: number;
      n_saved: number;
      save_rate: number | null;
    };
  };
  aesthetic_families?: AestheticFamiliesSummary;
  next_core_pair: CalibrationPair | null;
  next_serendipity_pair: CalibrationPair | null;
}

interface TasteCalibrationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type BenchTab = 'core' | 'serendipity' | 'anchors' | 'families';

const STRATUM_OPTIONS: Array<{ key: string; short: string; target: string }> = [
  { key: 'auto', short: '自动配比', target: '25/35/20/20' },
  { key: 'T1_macro_style', short: 'T1 比风格', target: '25%' },
  { key: 'T2_same_style_instance', short: 'T2 同风格比作品', target: '35%' },
  { key: 'T3_same_subject_treatment', short: 'T3 同对象换处理', target: '20%' },
  { key: 'T4_same_comp_material_or_subject', short: 'T4 同构图对照', target: '20%' },
];

export const TasteCalibrationModal: React.FC<TasteCalibrationModalProps> = ({ isOpen, onClose }) => {
  const [tab, setTab] = useState<BenchTab>('core');
  const [lockedStratum, setLockedStratum] = useState<string>('auto');
  const [state, setState] = useState<CalibrationState | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [reasonNote, setReasonNote] = useState<string>('');

  const loadState = useCallback(async (stratumOverride?: string) => {
    setLoading(true);
    setError(null);
    const st = stratumOverride ?? lockedStratum;
    const qs = st && st !== 'auto' ? `?stratum=${encodeURIComponent(st)}` : '';
    try {
      const res = await fetch(`/api/atlas/calibration/state${qs}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `加载失败 (HTTP ${res.status})`);
      setState(data as CalibrationState);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : '无法连接本地 FastAPI (127.0.0.1:8780)，请确认后端服务已启动。'
      );
    } finally {
      setLoading(false);
    }
  }, [lockedStratum]);

  useEffect(() => {
    if (isOpen) {
      void loadState();
    }
  }, [isOpen, loadState]);

  const activePair =
    tab === 'core' ? state?.next_core_pair ?? null : tab === 'serendipity' ? state?.next_serendipity_pair ?? null : null;

  const toggleReasonChip = (label: string) => {
    setSelectedReasons((prev) => (prev.includes(label) ? prev.filter((x) => x !== label) : [...prev, label].slice(0, 4)));
  };

  const handleVote = useCallback(
    async (choice: 'a' | 'b' | 'tie_like' | 'cannot_compare' | 'both' | 'neither') => {
      if (!activePair || submitting) return;
      setSubmitting(true);
      setError(null);
      try {
        const res = await fetch('/api/atlas/calibration/vote', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            signal: activePair.signal,
            asset_a: activePair.a.asset_id,
            asset_b: activePair.b.asset_id,
            choice,
            chosen_reasons: selectedReasons,
            reason_note: reasonNote.trim(),
            meta: {
              stratum: activePair.stratum,
              locked_stratum: lockedStratum !== 'auto' ? lockedStratum : null,
              a_contrast_axis: activePair.a.contrast_axis,
              b_contrast_axis: activePair.b.contrast_axis,
            },
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.detail || `投票失败 (HTTP ${res.status})`);
        if (data?.state) setState(data.state as CalibrationState);
        setSelectedReasons([]);
        setReasonNote('');
      } catch (err) {
        setError(err instanceof Error ? err.message : '提交投票失败');
      } finally {
        setSubmitting(false);
      }
    },
    [activePair, submitting, lockedStratum, selectedReasons, reasonNote]
  );

  const handleAnchorAction = async (payload: {
    domain: string;
    role: 'familiar_anchor' | 'contrast_anchor';
    craft_confirmed?: boolean;
    contrast_confirmed?: boolean;
    cycle_next?: boolean;
  }) => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch('/api/atlas/calibration/anchors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `更新失败 (HTTP ${res.status})`);
      if (data?.state) setState(data.state as CalibrationState);
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新参考标准失败');
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (tab === 'anchors' || tab === 'families' || !activePair || submitting) return;
      if (e.key === 'ArrowLeft' || e.key.toLowerCase() === 'a') {
        e.preventDefault();
        void handleVote('a');
      } else if (e.key === 'ArrowRight' || e.key.toLowerCase() === 'b') {
        e.preventDefault();
        void handleVote('b');
      } else if (e.key.toLowerCase() === 't') {
        e.preventDefault();
        void handleVote(tab === 'serendipity' ? 'both' : 'tie_like');
      } else if (e.key.toLowerCase() === 's') {
        e.preventDefault();
        void handleVote(tab === 'serendipity' ? 'neither' : 'cannot_compare');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose, tab, activePair, submitting, handleVote]);

  if (!isOpen) return null;

  const bt = state?.rerank_summary.bt_model;
  const lanes = state?.rerank_summary.lane_counts;
  const vc = state?.vote_counts;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="分层品味校准与完成度标准"
      className="fixed inset-0 z-[65] bg-black/75 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-5xl max-h-[92vh] rounded-2xl border border-border bg-card shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-primary" />
              <h2 className="font-display text-base sm:text-lg font-bold text-foreground">
                Taste Engine v2.1 · 分层品味校准与完成度标准
              </h2>
              {state && (
                <span className="mono text-[11px] px-2 py-0.5 rounded bg-secondary text-muted-foreground border border-border">
                  7参分层BT · OKLab+4×4 CV · 重排 {state.rerank_summary.latency_ms}ms
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              同门类 4 层控制变量对比（宏观风格 + 微观执行解耦）· 像素级可核验反差主轴 · 完成度标准独立复核
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void loadState()}
              disabled={loading}
              className="h-8 px-2.5 rounded-md border border-border bg-secondary/40 hover:bg-secondary text-xs text-foreground inline-flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>刷新</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭校准台"
              className="h-8 w-8 rounded-md border border-border hover:bg-secondary inline-flex items-center justify-center text-muted-foreground hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tab Bar + Live Metrics */}
        <div className="px-5 py-2.5 border-b border-border bg-secondary/20 flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex rounded-lg border border-border bg-card p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setTab('core')}
              className={`px-3 py-1.5 rounded-md font-semibold inline-flex items-center gap-1.5 transition-colors ${
                tab === 'core' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>① 分层口味校准 ({vc?.core_taste_stratified ?? 0}/{vc?.trial_budget_target ?? 60})</span>
            </button>
            <button
              type="button"
              onClick={() => setTab('serendipity')}
              className={`px-3 py-1.5 rounded-md font-semibold inline-flex items-center gap-1.5 transition-colors ${
                tab === 'serendipity'
                  ? 'bg-amber-500 text-zinc-950'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Compass className="w-3.5 h-3.5" />
              <span>② 破圈探索验证 ({vc?.serendipity_total ?? 0})</span>
            </button>
            <button
              type="button"
              onClick={() => setTab('anchors')}
              className={`px-3 py-1.5 rounded-md font-semibold inline-flex items-center gap-1.5 transition-colors ${
                tab === 'anchors' ? 'bg-foreground text-background' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>
                ③ 完成度标准 ({state?.confirmed_anchors ?? 0}/{state?.total_anchors ?? 16} · 反差{' '}
                {state?.confirmed_contrast ?? 0}/{state?.total_contrast_anchors ?? 8})
              </span>
            </button>
            <button
              type="button"
              onClick={() => setTab('families')}
              className={`px-3 py-1.5 rounded-md font-semibold inline-flex items-center gap-1.5 transition-colors ${
                tab === 'families' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>④ 7 大审美倾向 ({state?.aesthetic_families?.total_personal_pins ?? 390})</span>
            </button>
          </div>

          {lanes && (
            <div className="flex flex-wrap items-center gap-2 text-[11px] mono text-muted-foreground">
              <span className="px-2 py-0.5 rounded bg-card border border-border">
                Core <strong className="text-foreground">{lanes.core_resonance}</strong>
              </span>
              <span className="px-2 py-0.5 rounded bg-card border border-border">
                Bridge <strong className="text-foreground">{lanes.cross_domain_bridge}</strong>
              </span>
              <span
                className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/40 text-amber-600 dark:text-amber-400"
                title="像素反差 ≥P90 且完成度达标的探索池（不足 15% 上限时诚实少展示，不塞次品）"
              >
                Explore <strong>{lanes.adversarial_exploration}</strong>/{lanes.exploration_cap}
              </span>
            </div>
          )}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-xs text-destructive">
              {error}
            </div>
          )}

          {loading && !state ? (
            <div className="h-80 flex flex-col items-center justify-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
              <span>正在加载 OKLab + 4×4 构图特征与分层对比对...</span>
            </div>
          ) : tab !== 'anchors' ? (
            activePair ? (
              <div className="space-y-3.5">
                {/* Stratum Selector for Tab 1 */}
                {tab === 'core' && (
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                      {STRATUM_OPTIONS.map((opt) => {
                        const active = lockedStratum === opt.key;
                        const cnt = opt.key !== 'auto' ? vc?.stratum_counts?.[opt.key] ?? 0 : null;
                        return (
                          <button
                            key={opt.key}
                            type="button"
                            onClick={() => {
                              setLockedStratum(opt.key);
                              void loadState(opt.key);
                            }}
                            className={`px-2.5 py-1 rounded-md border font-medium transition-colors ${
                              active
                                ? 'border-primary bg-primary/15 text-primary font-semibold'
                                : 'border-border bg-secondary/30 text-muted-foreground hover:text-foreground'
                            }`}
                          >
                            {opt.short}
                            {cnt !== null ? ` (${cnt})` : ` · ${opt.target}`}
                          </button>
                        );
                      })}
                    </div>
                    {vc && vc.legacy_cross_domain_diagnostic > 0 && (
                      <span className="text-[11px] text-muted-foreground">
                        已隔离旧跨域票 {vc.legacy_cross_domain_diagnostic} 条作诊断
                      </span>
                    )}
                  </div>
                )}

                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="space-y-1">
                    <div className="inline-flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-primary/15 text-primary border border-primary/30 text-[11px] font-semibold">
                        {activePair.stratum_badge_zh}
                      </span>
                      <h3 className="text-base font-bold text-foreground">{activePair.question_zh}</h3>
                    </div>
                    <p className="text-xs text-muted-foreground">{activePair.hint_zh}</p>
                  </div>
                  <div className="text-[11px] mono text-muted-foreground shrink-0">
                    <kbd className="px-1.5 py-0.5 rounded border border-border bg-secondary">←</kbd> 左 ·{' '}
                    <kbd className="px-1.5 py-0.5 rounded border border-border bg-secondary">→</kbd> 右 ·{' '}
                    <kbd className="px-1.5 py-0.5 rounded border border-border bg-secondary">T</kbd> 同喜 ·{' '}
                    <kbd className="px-1.5 py-0.5 rounded border border-border bg-secondary">S</kbd> 跳过
                  </div>
                </div>

                {/* Controlled A/B Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {(
                    [
                      { key: 'a' as const, label: 'A · 左侧候选', card: activePair.a },
                      { key: 'b' as const, label: 'B · 右侧候选', card: activePair.b },
                    ] as const
                  ).map(({ key, label, card }) => (
                    <button
                      key={card.asset_id}
                      type="button"
                      disabled={submitting}
                      onClick={() => void handleVote(key)}
                      className="group text-left rounded-xl border border-border hover:border-primary bg-secondary/15 overflow-hidden transition-all focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <div className="aspect-[4/3] w-full bg-zinc-950/90 flex items-center justify-center overflow-hidden relative">
                        <img
                          src={card.image_url}
                          alt={card.title}
                          className="w-full h-full object-contain group-hover:scale-[1.02] transition-transform duration-200"
                        />
                        <span className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-md bg-black/70 text-white text-[11px] font-semibold backdrop-blur-sm">
                          {label}
                        </span>
                        <span className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-md bg-black/65 text-zinc-200 text-[11px] backdrop-blur-sm">
                          {card.archetype_label}
                          {card.typology ? ` · ${card.typology}` : ''}
                        </span>
                        {tab === 'serendipity' && card.contrast_reason_zh && (
                          <span className="absolute bottom-2 left-2 right-2 px-2 py-1 rounded bg-black/75 text-amber-300 text-[10px] backdrop-blur-sm truncate">
                            {card.contrast_reason_zh}
                          </span>
                        )}
                      </div>
                      <div className="px-3.5 py-2.5 flex items-center justify-between gap-2 border-t border-border">
                        <div className="min-w-0">
                          <div className="text-xs font-medium text-foreground truncate">{card.title}</div>
                          {card.primary_family_zh && (
                            <div className="text-[10px] text-primary/90 truncate mt-0.5">
                              {card.primary_family_zh}
                              {card.secondary_family_zh ? ` × ${card.secondary_family_zh}` : ''}
                            </div>
                          )}
                        </div>
                        <span className="text-xs font-semibold text-primary shrink-0 group-hover:translate-x-0.5 transition-transform">
                          {tab === 'core' ? '更合口味 →' : '愿意破例收藏 →'}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>

                {/* Optional Candidate Reason Attribution Shelf (also retained on tie_like / both!) */}
                {state?.aesthetic_families?.reason_chips && (
                  <div className="rounded-lg border border-border/80 bg-secondary/15 px-3.5 py-2.5 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                      <span className="text-muted-foreground font-medium">
                        喜欢的原因候选（可选，点选 1–2 个再投票；点「两张同样喜欢」也会保留共同原因）
                      </span>
                      {selectedReasons.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setSelectedReasons([])}
                          className="text-muted-foreground hover:text-foreground underline underline-offset-2"
                        >
                          清空 ({selectedReasons.length})
                        </button>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {state.aesthetic_families.reason_chips.map((chip) => {
                        const active = selectedReasons.includes(chip.label);
                        return (
                          <button
                            key={chip.key}
                            type="button"
                            onClick={() => toggleReasonChip(chip.label)}
                            className={`px-2.5 py-1 rounded-md border text-[11px] transition-colors ${
                              active
                                ? 'bg-foreground text-background border-foreground font-semibold'
                                : 'bg-card text-muted-foreground border-border hover:border-foreground/50 hover:text-foreground'
                            }`}
                          >
                            {chip.label}
                          </button>
                        );
                      })}
                    </div>
                    <input
                      type="text"
                      value={reasonNote}
                      onChange={(e) => setReasonNote(e.target.value)}
                      placeholder="可选补充一句你的直觉（如：更喜欢磨砂玻璃后的暖光感）…"
                      className="w-full bg-transparent border-0 border-b border-border/70 focus:border-foreground py-1 text-xs text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
                    />
                  </div>
                )}

                {/* Action Row: Separate Tie-Like vs Cannot-Compare */}
                <div className="flex flex-wrap items-center justify-center gap-2.5 pt-1">
                  {tab === 'core' ? (
                    <>
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => void handleVote('tie_like')}
                        className="h-9 px-4 rounded-md border border-emerald-500/50 bg-emerald-500/10 hover:bg-emerald-500/20 text-xs font-semibold text-emerald-600 dark:text-emerald-400 inline-flex items-center gap-1.5"
                      >
                        <Heart className="w-3.5 h-3.5" />
                        <span>两张同样喜欢 (T)</span>
                      </button>
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => void handleVote('cannot_compare')}
                        className="h-9 px-4 rounded-md border border-border bg-secondary/50 hover:bg-secondary text-xs font-medium text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5"
                      >
                        <SkipForward className="w-3.5 h-3.5" />
                        <span>无法比较 / 跳过 (S)</span>
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => void handleVote('both')}
                        className="h-9 px-4 rounded-md border border-amber-500/60 bg-amber-500/15 hover:bg-amber-500/25 text-xs font-semibold text-amber-600 dark:text-amber-300 inline-flex items-center gap-1.5"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>两张都愿破例收藏 (T)</span>
                      </button>
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => void handleVote('neither')}
                        className="h-9 px-4 rounded-md border border-border bg-secondary/50 hover:bg-secondary text-xs font-medium text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5"
                      >
                        <SkipForward className="w-3.5 h-3.5" />
                        <span>都不想收 / 跳过 (S)</span>
                      </button>
                    </>
                  )}
                </div>

                {/* Live 7-Param Hierarchical BT Telemetry */}
                {bt && (
                  <div className="rounded-xl border border-border bg-secondary/20 p-3.5 space-y-2.5 text-xs">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div>
                        <div className="text-[11px] text-muted-foreground">7参分层 BT（同域分层CV）</div>
                        <div className="mono font-bold text-foreground mt-0.5">
                          {bt.fitted && bt.cv_acc !== null
                            ? `${(bt.cv_acc * 100).toFixed(1)}% · LL ${bt.cv_logloss?.toFixed(3)}`
                            : `待标满 5 组同域 (${bt.n_stratified_pairs}/5)`}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-muted-foreground">仅宏观风格基线</div>
                        <div className="mono font-bold text-foreground mt-0.5">
                          {bt.macro_only_acc !== null ? `${(bt.macro_only_acc * 100).toFixed(1)}%` : '—'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-muted-foreground">旧单质心 / Medoid 基线</div>
                        <div className="mono font-bold text-muted-foreground mt-0.5">
                          {bt.single_centroid_acc !== null && bt.max_medoid_acc !== null
                            ? `${(bt.single_centroid_acc * 100).toFixed(1)}% / ${(bt.max_medoid_acc * 100).toFixed(1)}%`
                            : '—'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-muted-foreground">Q2 陌生破圈收藏率</div>
                        <div className="mono font-bold text-amber-600 dark:text-amber-400 mt-0.5">
                          {state?.rerank_summary.serendipity_eval.save_rate !== null &&
                          state?.rerank_summary.serendipity_eval.save_rate !== undefined
                            ? `${(state.rerank_summary.serendipity_eval.save_rate * 100).toFixed(1)}% (${state.rerank_summary.serendipity_eval.n_saved}/${state.rerank_summary.serendipity_eval.n_votes})`
                            : '暂无记录'}
                        </div>
                      </div>
                    </div>

                    {bt.fitted && bt.beta_micro5 && bt.beta_labels && (
                      <div className="pt-2 border-t border-border/60 flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="text-muted-foreground font-medium">同风格执行权重 β：</span>
                        {bt.beta_labels.map((lbl, idx) => {
                          const w = bt.beta_micro5?.[idx] ?? 0;
                          return (
                            <span
                              key={lbl}
                              className={`mono px-2 py-0.5 rounded border ${
                                w > 0.05
                                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                                  : w < -0.05
                                    ? 'border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-400'
                                    : 'border-border bg-card text-muted-foreground'
                              }`}
                            >
                              {lbl} {w >= 0 ? `+${w.toFixed(2)}` : w.toFixed(2)}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
                当前分层暂无更多未评候选对，可切换其他分层或查看完成度标准。
              </div>
            )
          ) : tab === 'anchors' ? (
            /* Tab 3: 完成度标准 (常选风格参考 + 反差风格参考) & 10 Medoids */
            <div className="space-y-6">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-primary" />
                    <span>8 域「完成度标准」参考样张（反差参考经 OKLab 色彩 / 4×4 构图 ≥P90 像素筛选）</span>
                  </h3>
                  <span className="text-[11px] text-muted-foreground">
                    反差参考拆为两问独立复核：完成度够入选吗？+ 风格差别明显吗？
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {state &&
                    Object.values(state.anchors.domains).map((dom) => (
                      <div key={dom.domain} className="rounded-xl border border-border bg-secondary/15 p-3 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-foreground">{dom.domain_label}</span>
                          {dom.contrast_anchor.low_personal_prior && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                              个人原图偏少，建议人工确认
                            </span>
                          )}
                        </div>

                        <div className="grid grid-cols-2 gap-2.5">
                          {/* 常选风格参考 */}
                          <div className="rounded-lg border border-border bg-card overflow-hidden flex flex-col">
                            <div className="aspect-[4/3] bg-zinc-950 relative overflow-hidden">
                              <img
                                src={dom.familiar_anchor.image_url}
                                alt={dom.familiar_anchor.title}
                                className="w-full h-full object-cover"
                                loading="lazy"
                              />
                              <span className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-black/75 text-white text-[10px] font-medium">
                                常选风格参考
                              </span>
                            </div>
                            <div className="p-2 space-y-1.5 flex-1 flex flex-col justify-between">
                              <div className="text-[11px] truncate text-foreground font-medium">
                                {dom.familiar_anchor.title}
                              </div>
                              <button
                                type="button"
                                disabled={submitting}
                                onClick={() =>
                                  void handleAnchorAction({
                                    domain: dom.domain,
                                    role: 'familiar_anchor',
                                    craft_confirmed: !dom.familiar_anchor.craft_confirmed,
                                  })
                                }
                                className={`w-full py-1 px-2 rounded text-[11px] font-semibold border inline-flex items-center justify-center gap-1 transition-colors ${
                                  dom.familiar_anchor.craft_confirmed
                                    ? 'border-emerald-500 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                                    : 'border-border bg-secondary/40 hover:border-primary text-muted-foreground hover:text-foreground'
                                }`}
                              >
                                <CheckCircle2 className="w-3 h-3" />
                                <span>{dom.familiar_anchor.craft_confirmed ? '完成度已确认' : '完成度够入选？'}</span>
                              </button>
                            </div>
                          </div>

                          {/* 反差风格参考 */}
                          <div className="rounded-lg border border-border bg-card overflow-hidden flex flex-col">
                            <div className="aspect-[4/3] bg-zinc-950 relative overflow-hidden">
                              <img
                                src={dom.contrast_anchor.image_url}
                                alt={dom.contrast_anchor.title}
                                className="w-full h-full object-cover"
                                loading="lazy"
                              />
                              <span className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-amber-500/90 text-zinc-950 text-[10px] font-bold">
                                反差风格参考
                              </span>
                              <button
                                type="button"
                                disabled={submitting}
                                title="换一张像素反差候选"
                                onClick={() =>
                                  void handleAnchorAction({
                                    domain: dom.domain,
                                    role: 'contrast_anchor',
                                    cycle_next: true,
                                  })
                                }
                                className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/75 hover:bg-black text-white text-[10px] inline-flex items-center gap-0.5"
                              >
                                <Shuffle className="w-2.5 h-2.5" />
                                <span>换一张</span>
                              </button>
                            </div>
                            <div className="p-2 space-y-1.5 flex-1 flex flex-col justify-between">
                              <div>
                                <div className="text-[11px] truncate text-foreground font-medium">
                                  {dom.contrast_anchor.title}
                                </div>
                                <div
                                  className="text-[10px] text-amber-600 dark:text-amber-400 truncate mt-0.5"
                                  title={dom.contrast_anchor.contrast_reason_zh}
                                >
                                  {dom.contrast_anchor.contrast_reason_zh}
                                </div>
                              </div>
                              <div className="grid grid-cols-2 gap-1">
                                <button
                                  type="button"
                                  disabled={submitting}
                                  onClick={() =>
                                    void handleAnchorAction({
                                      domain: dom.domain,
                                      role: 'contrast_anchor',
                                      craft_confirmed: !dom.contrast_anchor.craft_confirmed,
                                    })
                                  }
                                  className={`py-1 px-1.5 rounded text-[10px] font-semibold border truncate transition-colors ${
                                    dom.contrast_anchor.craft_confirmed
                                      ? 'border-emerald-500 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                                      : 'border-border bg-secondary/40 hover:border-primary text-muted-foreground'
                                  }`}
                                >
                                  {dom.contrast_anchor.craft_confirmed ? '✓ 完成度够' : '完成度够？'}
                                </button>
                                <button
                                  type="button"
                                  disabled={submitting}
                                  onClick={() =>
                                    void handleAnchorAction({
                                      domain: dom.domain,
                                      role: 'contrast_anchor',
                                      contrast_confirmed: !dom.contrast_anchor.contrast_confirmed,
                                    })
                                  }
                                  className={`py-1 px-1.5 rounded text-[10px] font-semibold border truncate transition-colors ${
                                    dom.contrast_anchor.contrast_confirmed
                                      ? 'border-amber-500 bg-amber-500/20 text-amber-600 dark:text-amber-300'
                                      : 'border-border bg-secondary/40 hover:border-amber-500 text-muted-foreground'
                                  }`}
                                >
                                  {dom.contrast_anchor.contrast_confirmed ? '✓ 反差明显' : '反差明显？'}
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* 10 Personal Medoids Preview */}
              {state && (
                <div className="space-y-2">
                  <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-primary" />
                    <span>PinnerSage K=10 个人审美子簇 Medoids（用于多路召回与跨域桥接）</span>
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                    {state.profile.medoids.map((m) => (
                      <div key={m.medoid_id} className="rounded-lg border border-border bg-card overflow-hidden">
                        <div className="aspect-square bg-zinc-950 relative overflow-hidden">
                          <img src={m.image_url} alt={m.title} className="w-full h-full object-cover" loading="lazy" />
                          <span className="absolute top-1.5 left-1.5 mono text-[10px] px-1.5 py-0.5 rounded bg-black/75 text-white font-bold">
                            {m.medoid_id} · {m.cluster_size}张
                          </span>
                        </div>
                        <div className="p-2 space-y-0.5">
                          <div className="text-[11px] font-semibold text-foreground truncate">{m.title}</div>
                          <div className="text-[10px] text-muted-foreground truncate">
                            {m.archetype_label} · {m.aesthetic_style_zh}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Tab 4: 7 Cross-Board Personal Aesthetic Families + Live Reason Convergence */
            <div className="space-y-6">
              {state?.aesthetic_families ? (
                <>
                  <div className="rounded-xl border border-border bg-secondary/20 p-4 space-y-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h3 className="text-sm font-bold text-foreground">
                        390 张个人原生 Pinterest · 7 大跨画板审美引力家族
                      </h3>
                      <span className="text-xs text-muted-foreground mono">
                        纯净审美 {state.aesthetic_families.total_personal_pins - state.aesthetic_families.pragmatic_noise_count} 张 · 杂乱资料 {state.aesthetic_families.pragmatic_noise_count} 张
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      打破原有 28 个业务画板，按真实视觉吸引力重聚：底层保留 K=10 Medoids 跑 &lt;20ms 召回，上层用 7 大家族与你勾选的喜欢原因收敛个人倾向。
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-border/70">
                      <div className="space-y-2">
                        <div className="text-[11px] font-semibold text-muted-foreground">最常同框共现的「双重张力」</div>
                        <div className="flex flex-wrap gap-1.5">
                          {state.aesthetic_families.top_tensions.map((t) => (
                            <span
                              key={t.pair}
                              className="px-2.5 py-1 rounded-md bg-card border border-border text-[11px] text-foreground"
                            >
                              {t.pair} <strong className="mono text-primary ml-1">{t.count}张</strong>
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="text-[11px] font-semibold text-muted-foreground">
                          你在校准台亲手勾选的喜欢原因收敛（含「两张同样喜欢」{state.aesthetic_families.reason_attribution.tie_like_votes_with_reasons} 票）
                        </div>
                        {state.aesthetic_families.reason_attribution.top_reasons.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {state.aesthetic_families.reason_attribution.top_reasons.slice(0, 6).map((r) => (
                              <span
                                key={r.label}
                                className="px-2.5 py-1 rounded-md bg-primary/10 border border-primary/40 text-[11px] text-foreground"
                              >
                                {r.label} <strong className="mono text-primary ml-1">×{r.count}</strong>
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[11px] text-muted-foreground">
                            在 ①/② 投票时点选上方「喜欢的原因候选」，这里会实时收敛你最常被击中的原因。
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {state.aesthetic_families.families.map((fam) => (
                      <div key={fam.key} className="rounded-xl border border-border bg-card p-4 space-y-3">
                        <div className="flex items-baseline justify-between gap-2">
                          <h4 className="text-sm font-bold text-foreground">
                            {fam.num}. {fam.name}
                          </h4>
                          <span className="mono text-xs text-primary font-semibold shrink-0">
                            {fam.count} 张 · {fam.pct}%
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">{fam.desc}</p>
                        <div className="grid grid-cols-4 gap-2">
                          {fam.samples.map((s) => (
                            <div
                              key={s.asset_id}
                              className="aspect-square rounded-lg bg-zinc-950 border border-border/60 overflow-hidden relative group"
                              title={`${s.asset_id} (${s.board_name}) · ${s.verdict_why}`}
                            >
                              <img src={s.image_url} alt={s.title} className="w-full h-full object-cover" loading="lazy" />
                              <span className="absolute bottom-1 left-1 right-1 px-1 py-0.5 rounded bg-black/70 text-[9px] text-zinc-100 truncate">
                                {s.board_name}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="py-12 text-center text-xs text-muted-foreground">暂未加载 390 原生家族档案</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
