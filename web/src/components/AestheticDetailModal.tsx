'use client';

import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, Copy, Compass, Database, Heart, Layers, Plus, Sparkles, SunMedium, X } from 'lucide-react';
import type { SpectrumAxisId } from '@/engine/salienceMetric';
import type { CuratedShowcaseAsset } from '@/types/aethervault';
import { AestheticMiniRadar } from './AestheticMiniRadar';

interface AestheticDetailModalProps {
  asset: CuratedShowcaseAsset | null;
  allAssetsById?: Record<string, CuratedShowcaseAsset>;
  profileBaselineScores?: Partial<Record<SpectrumAxisId, number>>;
  currentIndex: number;
  totalFiltered: number;
  isInFusion?: boolean;
  onToggleFusion?: (assetId: string) => void;
  onSelectNeighbor?: (assetId: string) => void;
  onPrev: () => void;
  onNext: () => void;
  onCopyHex: (hex: string) => Promise<void> | void;
  onClose: () => void;
}

export const AestheticDetailModal: React.FC<AestheticDetailModalProps> = ({
  asset,
  allAssetsById,
  profileBaselineScores,
  currentIndex,
  totalFiltered,
  isInFusion = false,
  onToggleFusion,
  onSelectNeighbor,
  onPrev,
  onNext,
  onCopyHex,
  onClose,
}) => {
  const [copiedHex, setCopiedHex] = useState<string | null>(null);
  const [copiedRag, setCopiedRag] = useState(false);
  const dialogScrollRef = useRef<HTMLDivElement | null>(null);

  const isOpen = Boolean(asset);

  useEffect(() => {
    if (!isOpen) return;
    const html = document.documentElement;
    const body = document.body;
    const scrollY = window.scrollY;
    const prevHtmlOverflow = html.style.overflow;
    const prevOverscroll = html.style.overscrollBehavior;
    const prevBodyPosition = body.style.position;
    const prevBodyTop = body.style.top;
    const prevBodyLeft = body.style.left;
    const prevBodyRight = body.style.right;
    const prevBodyOverflow = body.style.overflow;

    html.style.overflow = 'hidden';
    html.style.overscrollBehavior = 'contain';
    body.style.position = 'fixed';
    body.style.top = `-${scrollY}px`;
    body.style.left = '0';
    body.style.right = '0';
    body.style.overflow = 'hidden';

    return () => {
      html.style.overflow = prevHtmlOverflow;
      html.style.overscrollBehavior = prevOverscroll;
      body.style.position = prevBodyPosition;
      body.style.top = prevBodyTop;
      body.style.left = prevBodyLeft;
      body.style.right = prevBodyRight;
      body.style.overflow = prevBodyOverflow;
      window.scrollTo({ top: scrollY, behavior: 'instant' as ScrollBehavior });
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') onPrev();
      else if (e.key === 'ArrowRight') onNext();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose, onPrev, onNext]);

  useEffect(() => {
    if (asset && dialogScrollRef.current) {
      dialogScrollRef.current.scrollTop = 0;
    }
  }, [asset?.asset_id]);

  if (!asset) return null;

  const critique = asset.aesthetic_critique;
  const assetScores: Partial<Record<SpectrumAxisId, number>> = {
    tectonic_honesty: asset.style_spectrums.tectonic_honesty?.score ?? 0,
    surface_entropy: asset.style_spectrums.surface_entropy?.score ?? 0,
    spatial_density: asset.style_spectrums.spatial_density?.score ?? 0,
    geometric_order: asset.style_spectrums.geometric_order?.score ?? 0,
    lighting_drama: asset.style_spectrums.lighting_drama?.score ?? 0,
    chromatic_tension: asset.style_spectrums.chromatic_tension?.score ?? 0,
    thermal_mood: asset.style_spectrums.thermal_mood?.score ?? 0,
    reality_abstraction: asset.style_spectrums.reality_abstraction?.score ?? 0,
  };

  const handleHexClick = async (hex: string) => {
    await onCopyHex(hex);
    setCopiedHex(hex);
    setTimeout(() => setCopiedHex(null), 1400);
  };

  const handleCopyRagDoc = async () => {
    if (!asset.rag_doc) return;
    const payload = JSON.stringify(
      {
        ...asset.rag_doc,
        title: asset.title,
        headline_insight: critique?.headline_insight ?? '',
        why_you_love_it: critique?.why_you_love_it ?? '',
      },
      null,
      2
    );
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(payload);
      }
      setCopiedRag(true);
      setTimeout(() => setCopiedRag(false), 1600);
    } catch {
      setCopiedRag(true);
      setTimeout(() => setCopiedRag(false), 1600);
    }
  };

  const sourceText =
    asset.source_origin === 'pinterest_personal'
      ? `Pinterest · ${asset.board_name ?? '个人画板'}`
      : `画像扩展 · ${asset.license}`;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="aesthetic-modal-title"
      onClick={onClose}
      className="fixed inset-0 z-[60] !mt-0 bg-black/70 backdrop-blur-[2px] flex items-center justify-center p-3 sm:p-6 overscroll-contain"
    >
      <div
        ref={dialogScrollRef}
        onClick={(e) => e.stopPropagation()}
        className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-6xl max-h-[92vh] overflow-y-auto overscroll-contain grid grid-cols-1 lg:grid-cols-12"
      >
        {/* Mobile Sticky Top Header with Accessible Top-Right Close Button */}
        <div className="lg:hidden sticky top-0 z-10 flex items-center justify-between gap-3 px-4 py-3 border-b border-border bg-card/95 backdrop-blur-md">
          <div className="min-w-0 flex items-center gap-2">
            {asset.archetype_label && (
              <span className="rounded-md bg-primary/10 text-primary px-2 py-0.5 text-[11px] font-semibold shrink-0">
                {asset.archetype_label}
              </span>
            )}
            <span className="text-sm font-bold text-foreground truncate">{asset.title}</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭美学深度解析"
            className="w-8 h-8 shrink-0 rounded-md border border-border hover:border-primary/60 flex items-center justify-center text-foreground transition-colors"
          >
            <X className="w-4 h-4" strokeWidth={1.75} />
          </button>
        </div>

        {/* Left Column: Full-Proportion Uncropped Plate & Palette */}
        <div className="lg:col-span-6 bg-secondary/40 border-b lg:border-b-0 lg:border-r border-border p-4 sm:p-6 flex flex-col justify-between gap-4">
          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span className="truncate">{sourceText}</span>
            <span className="mono shrink-0">
              比例 {asset.aspect_label ?? '4:3'}
              {asset.width && asset.height ? ` (${asset.width}×${asset.height})` : ''}
            </span>
          </div>

          <div className="rounded-lg border border-border bg-secondary/50 flex items-center justify-center p-3 min-h-[280px] sm:min-h-[420px]">
            <img
              src={asset.image_url}
              alt={asset.title}
              className="max-h-[62vh] w-auto max-w-full object-contain rounded-sm"
            />
          </div>

          <div className="space-y-3">
            {/* 5-Color OKLab Palette Swatches */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-foreground">OKLab 主色调秩序（点击复制色值）</span>
                <span className="mono text-muted-foreground">{asset.asset_id}</span>
              </div>
              <div className="grid grid-cols-5 gap-1.5">
                {asset.granular_descriptors.color_palette.slice(0, 5).map((hex, idx) => {
                  const isCopied = copiedHex === hex;
                  return (
                    <button
                      key={`${hex}-${idx}`}
                      type="button"
                      onClick={() => handleHexClick(hex)}
                      aria-label={`复制色值 ${hex}`}
                      className="group rounded-md overflow-hidden border border-border hover:border-primary/60 bg-card transition-colors"
                    >
                      <div className="relative h-8 w-full" style={{ backgroundColor: hex }}>
                        <span
                          className={`absolute inset-0 flex items-center justify-center transition-opacity ${
                            isCopied
                              ? 'opacity-100 bg-black/45 text-white'
                              : 'opacity-0 group-hover:opacity-100 bg-black/35 text-white'
                          }`}
                          aria-hidden="true"
                        >
                          {isCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                        </span>
                      </div>
                      <div className="px-1 py-1 text-center text-[11px] mono text-foreground whitespace-nowrap">
                        {isCopied ? '已复制' : hex}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Prev / Next Navigation Bar */}
            {totalFiltered > 1 && (
              <div className="flex items-center justify-between gap-2 pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={onPrev}
                  className="min-h-[36px] px-3 rounded-md border border-border hover:border-primary/60 bg-card text-xs font-medium text-foreground inline-flex items-center gap-1.5 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>上一张</span>
                </button>
                <span className="mono text-xs text-muted-foreground tabular-nums">
                  {currentIndex + 1} / {totalFiltered}
                </span>
                <button
                  type="button"
                  onClick={onNext}
                  className="min-h-[36px] px-3 rounded-md border border-border hover:border-primary/60 bg-card text-xs font-medium text-foreground inline-flex items-center gap-1.5 transition-colors"
                >
                  <span>下一张</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Deep Aesthetic Criticism & Personal Resonance */}
        <div className="lg:col-span-6 p-5 sm:p-7 space-y-5">
          {/* Top Header */}
          <div className="flex items-start justify-between gap-3 pb-4 border-b border-border">
            <div className="space-y-2 min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                {asset.archetype_label && (
                  <span className="rounded-md bg-primary/10 text-primary px-2.5 py-0.5 text-xs font-semibold">
                    {asset.archetype_label}
                  </span>
                )}
                {(asset.aesthetic_style_zh || asset.sub_style || asset.sub_category) && (
                  <span className="rounded-md border border-border bg-secondary/60 text-foreground px-2.5 py-0.5 text-xs font-medium">
                    {asset.aesthetic_style_zh ?? asset.sub_style ?? asset.sub_category}
                    {asset.native_style_primary || asset.aesthetic_style_en ? (
                      <span className="mono text-[11px] text-muted-foreground ml-1.5">
                        {asset.native_style_primary ?? asset.aesthetic_style_en}
                      </span>
                    ) : null}
                  </span>
                )}
                {typeof asset.is_canonical_ism === 'boolean' && (
                  <span className="rounded-md border border-border/80 bg-card text-muted-foreground px-2 py-0.5 text-[11px]">
                    {asset.is_canonical_ism ? '设计主义' : '视觉体系'}
                  </span>
                )}
              </div>
              <h2
                id="aesthetic-modal-title"
                className="font-display text-xl font-extrabold text-foreground leading-snug"
              >
                {asset.title}
              </h2>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {onToggleFusion && (
                <button
                  type="button"
                  onClick={() => onToggleFusion(asset.asset_id)}
                  className={`h-9 px-3 rounded-md border text-xs font-semibold inline-flex items-center gap-1.5 transition-colors ${
                    isInFusion
                      ? 'border-amber-500 bg-amber-500/15 text-amber-600 dark:text-amber-400'
                      : 'border-border hover:border-primary/60 bg-card text-foreground'
                  }`}
                >
                  {isInFusion ? <Check className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                  <span>{isInFusion ? '已在融合槽' : '加入融合'}</span>
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                aria-label="关闭美学深度解析"
                className="hidden lg:flex w-9 h-9 shrink-0 rounded-md border border-border hover:border-primary/60 items-center justify-center text-foreground transition-colors"
              >
                <X className="w-4 h-4" strokeWidth={1.75} />
              </button>
            </div>
          </div>

          {/* Headline Aesthetic Thesis */}
          {critique?.headline_insight && (
            <div className="rounded-lg border border-border bg-secondary/50 px-4 py-3 text-sm font-medium text-foreground leading-relaxed">
              {critique.headline_insight}
            </div>
          )}

          {/* Highlight Card: Why You Love It (Core Match vs Contrast Inspiration) */}
          {critique?.why_you_love_it && (
            <div
              className={`rounded-lg border p-4 space-y-1.5 ${
                critique.resonance_mode === 'contrast_inspiration'
                  ? 'border-amber-500/40 bg-amber-500/10'
                  : 'border-primary/30 bg-accent/40'
              }`}
            >
              <div
                className={`flex items-center justify-between gap-2 text-xs font-bold ${
                  critique.resonance_mode === 'contrast_inspiration'
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-primary'
                }`}
              >
                <span className="inline-flex items-center gap-1.5">
                  <Heart className="w-3.5 h-3.5" />
                  <span>
                    {critique.resonance_mode === 'contrast_inspiration'
                      ? '破圈反差灵感（跳出日常基调的审美补给）'
                      : '为什么它让你觉得好看（个人审美核心同频）'}
                  </span>
                </span>
              </div>
              <p className="text-[13px] text-foreground leading-relaxed">
                {critique.why_you_love_it}
              </p>
            </div>
          )}

          {/* Bounded 4-Key RAG Index Card */}
          {asset.rag_facets && (
            <div className="rounded-lg border border-border bg-secondary/35 p-3.5 space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                  <Database className="w-3.5 h-3.5 text-primary" />
                  <span>RAG 受控索引（Gemini 视觉直读 · 4 键元数据）</span>
                </div>
                {asset.rag_doc && (
                  <button
                    type="button"
                    onClick={handleCopyRagDoc}
                    className="h-7 px-2.5 rounded-md border border-border hover:border-primary/60 bg-card text-[11px] font-medium text-foreground inline-flex items-center gap-1 transition-colors"
                  >
                    {copiedRag ? <Check className="w-3 h-3 text-primary" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedRag ? '已复制 RAG JSON' : '复制 RAG JSON'}</span>
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-md border border-border/80 bg-card px-2.5 py-1.5">
                  <span className="text-[11px] text-muted-foreground block">视觉媒介 (medium)</span>
                  <span className="font-semibold text-foreground">{asset.rag_facets.medium}</span>
                </div>
                <div className="rounded-md border border-border/80 bg-card px-2.5 py-1.5">
                  <span className="text-[11px] text-muted-foreground block">内容品类 (typology)</span>
                  <span className="font-semibold text-foreground">{asset.rag_facets.typology}</span>
                </div>
                <div className="rounded-md border border-border/80 bg-card px-2.5 py-1.5">
                  <span className="text-[11px] text-muted-foreground block">材质与技法 (materials)</span>
                  <span className="font-semibold text-foreground">{asset.rag_facets.materials.join(' · ')}</span>
                </div>
                <div className="rounded-md border border-border/80 bg-card px-2.5 py-1.5">
                  <span className="text-[11px] text-muted-foreground block">光影色域 (lighting)</span>
                  <span className="font-semibold text-foreground">{asset.rag_facets.lighting}</span>
                </div>
              </div>

              {asset.rag_doc?.model_prompt_tokens && asset.rag_doc.model_prompt_tokens.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-0.5">
                  {asset.rag_doc.model_prompt_tokens.map((tok) => (
                    <span
                      key={tok}
                      className="mono rounded px-1.5 py-0.5 text-[10px] border border-border bg-card text-muted-foreground"
                    >
                      {tok}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 3 Anatomy Sections */}
          <div className="space-y-4">
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                <Compass className="w-3.5 h-3.5 text-primary" />
                <span>比例、尺度与几何秩序</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {critique?.proportion_and_order ??
                  `画面比例 ${asset.aspect_label ?? '4:3'}，呈现平衡的几何分割与空间留白秩序。`}
              </p>
            </div>

            <div className="space-y-1 pt-3 border-t border-border">
              <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                <Layers className="w-3.5 h-3.5 text-primary" />
                <span>材质肌理与细部收口</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {critique?.material_and_detail ?? asset.granular_descriptors.material_stack}
              </p>
            </div>

            <div className="space-y-1 pt-3 border-t border-border">
              <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                <SunMedium className="w-3.5 h-3.5 text-primary" />
                <span>光影层次与色彩配比</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {critique?.light_and_palette ?? asset.granular_descriptors.lighting_rig}
              </p>
            </div>
          </div>

          {/* 3 Design Takeaways + Lightweight 8-Axis Radar Comparison */}
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-4 pt-3 border-t border-border items-center">
            {critique?.design_takeaways && critique.design_takeaways.length > 0 && (
              <div className="sm:col-span-7 space-y-2">
                <div className="text-xs font-bold text-foreground">可迁移设计法则</div>
                <ol className="space-y-2">
                  {critique.design_takeaways.map((tip, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground leading-relaxed">
                      <span className="mono font-semibold text-primary shrink-0">0{i + 1}</span>
                      <span>{tip}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            <div className={critique?.design_takeaways?.length ? 'sm:col-span-5' : 'sm:col-span-12'}>
              <AestheticMiniRadar
                primaryScores={assetScores}
                baselineScores={profileBaselineScores}
                sizeClass="w-full max-w-[215px]"
              />
            </div>
          </div>

          {/* 6 Closest Visual Neighbors Strip (Gemini Embedding 2) */}
          {allAssetsById && onSelectNeighbor && asset.similar_ids && asset.similar_ids.length > 0 && (
            <div className="pt-4 border-t border-border space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-foreground inline-flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-primary" />
                  <span>最像视觉邻居漫游（Gemini Embedding 2）</span>
                </span>
                <span className="text-[11px] text-muted-foreground">点击直接跳转</span>
              </div>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                {asset.similar_ids.slice(0, 6).map((nb) => {
                  const target = allAssetsById[nb.asset_id];
                  if (!target) return null;
                  return (
                    <button
                      key={nb.asset_id}
                      type="button"
                      onClick={() => onSelectNeighbor(nb.asset_id)}
                      title={`${target.title}（相似度 ${Math.round(nb.score * 100)}%）`}
                      className="group text-left space-y-1 rounded-md overflow-hidden focus-visible:outline-none"
                    >
                      <div className="relative aspect-square w-full rounded-md overflow-hidden border border-border group-hover:border-primary transition-colors bg-secondary/40">
                        <img
                          src={target.image_url}
                          alt={target.title}
                          loading="lazy"
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                        />
                        <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 py-0.5 mono text-[9px] text-white">
                          {Math.round(nb.score * 100)}%
                        </span>
                      </div>
                      <div className="text-[10px] text-muted-foreground group-hover:text-foreground truncate">
                        {target.title}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
