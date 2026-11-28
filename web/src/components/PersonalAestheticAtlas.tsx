'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Database,
  Download,
  Image as ImageIcon,
  ImagePlus,
  LayoutGrid,
  Loader2,
  Orbit,
  Plus,
  RotateCcw,
  Scale,
  Search,
  Sparkles,
  Wand2,
  X,
} from 'lucide-react';
import { ALL_AXIS_IDS, type SpectrumAxisId } from '@/engine/salienceMetric';
import type { AetherVaultShowcaseBundle, AestheticStyleId, AssetArchetype, CuratedShowcaseAsset, RagFacetKey } from '@/types/aethervault';
import { AestheticDetailModal } from './AestheticDetailModal';
import { AestheticMiniRadar } from './AestheticMiniRadar';
import { DropInIngestModal, NanoBananaFusionModal } from './AtlasStudioModals';
import { TasteCalibrationModal } from './TasteCalibrationModal';

const AestheticConstellation3D = dynamic(
  () => import('./three/AestheticConstellation3D').then((m) => m.AestheticConstellation3D),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-2xl border border-zinc-800 bg-[#07090e] h-[680px] flex items-center justify-center text-xs text-zinc-400">
        正在初始化 3D 点阵审美星图...
      </div>
    ),
  }
);

interface PersonalAestheticAtlasProps {
  bundle: AetherVaultShowcaseBundle;
}

type OriginFilter = 'all' | 'pinterest_personal' | 'profile_expansion';

const ARCHETYPE_ORDER: Array<{ key: AssetArchetype; label: string }> = [
  { key: 'interior', label: '室内设计' },
  { key: 'architecture', label: '建筑设计' },
  { key: 'graphic_typography', label: '平面与字体' },
  { key: 'craft', label: '器物工艺' },
  { key: 'industrial', label: '工业设计' },
  { key: 'landscape', label: '景观空间' },
  { key: 'illustration_character', label: '插画与角色' },
  { key: 'fashion_photography', label: '时尚摄影' },
];

const RAG_FACET_KEYS: Array<{ key: RagFacetKey; label: string; hint: string }> = [
  { key: 'medium', label: '视觉媒介', hint: '摄影、数字插画、字体海报、配色色板、导视实拍等' },
  { key: 'typology', label: '内容品类', hint: '建筑立面、实验字体、二次元立绘、灯具照明、空间导视等' },
  { key: 'materials', label: '材质与技法', hint: '清水混凝土/原木等实体材质，或点阵像素/赛璐璐/水墨水彩等技法' },
  { key: 'lighting', label: '光影色域', hint: '棚拍匀光、戏剧硬影、暖调氛围、漫射柔光、高饱和撞色' },
];

function assetMatchesFacet(asset: CuratedShowcaseAsset, key: RagFacetKey, value: string): boolean {
  const facets = asset.rag_facets;
  if (!facets) return false;
  if (key === 'medium') return facets.medium === value;
  if (key === 'typology') return facets.typology === value;
  if (key === 'lighting') return facets.lighting === value;
  return facets.materials.includes(value);
}

export const PersonalAestheticAtlas: React.FC<PersonalAestheticAtlasProps> = ({ bundle }) => {
  const [liveAssets, setLiveAssets] = useState<CuratedShowcaseAsset[]>(bundle.assets);
  const [searchQuery, setSearchQuery] = useState('');
  const [originFilter, setOriginFilter] = useState<OriginFilter>('all');
  const [archetypeFilter, setArchetypeFilter] = useState<'all' | AssetArchetype>('all');
  const [styleFilter, setStyleFilter] = useState<'all' | AestheticStyleId>('all');
  const [activeFacetKey, setActiveFacetKey] = useState<RagFacetKey>('typology');
  const [selectedFacets, setSelectedFacets] = useState<Partial<Record<RagFacetKey, string>>>({});
  const [viewMode, setViewMode] = useState<'grid' | 'constellation'>('grid');
  const [visibleLimit, setVisibleLimit] = useState(24);
  const [dnaOpen, setDnaOpen] = useState(true);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [copiedHex, setCopiedHex] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Multimodal Semantic & Image-to-Image Search State (Gemini Embedding 2)
  const imageSearchInputRef = useRef<HTMLInputElement | null>(null);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticError, setSemanticError] = useState<string | null>(null);
  const [semanticMode, setSemanticMode] = useState<string | null>(null);
  const [semanticImageName, setSemanticImageName] = useState<string | null>(null);
  const [semanticScores, setSemanticScores] = useState<Record<string, number> | null>(null);
  const [semanticLatencyMs, setSemanticLatencyMs] = useState<number | null>(null);
  const [queryMap3d, setQueryMap3d] = useState<{ x: number; y: number; z: number } | null>(null);

  // Nano Banana 2.1 Fusion, Drop-In Ingest & Taste Calibration Bench State
  const [fusionIds, setFusionIds] = useState<string[]>([]);
  const [fusionOpen, setFusionOpen] = useState(false);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [calibrationOpen, setCalibrationOpen] = useState(false);

  useEffect(() => {
    setLiveAssets(bundle.assets);
  }, [bundle.assets]);

  useEffect(() => {
    if (!toastMsg) return;
    const t = setTimeout(() => setToastMsg(null), 2200);
    return () => clearTimeout(t);
  }, [toastMsg]);

  const allAssetsById = useMemo(() => {
    const map: Record<string, CuratedShowcaseAsset> = {};
    for (const a of liveAssets) map[a.asset_id] = a;
    return map;
  }, [liveAssets]);

  const fusionAssets = useMemo(
    () => fusionIds.map((id) => allAssetsById[id]).filter((a): a is CuratedShowcaseAsset => Boolean(a)),
    [fusionIds, allAssetsById]
  );

  const handleToggleFusion = (assetId: string) => {
    setFusionIds((prev) => {
      if (prev.includes(assetId)) {
        setToastMsg('已从融合参考槽移除');
        return prev.filter((id) => id !== assetId);
      }
      if (prev.length >= 3) {
        setToastMsg('融合槽最多选 3 张，已替换最早 1 张');
        return [...prev.slice(1), assetId];
      }
      setToastMsg(`已加入融合参考槽 (${prev.length + 1}/3)`);
      return [...prev, assetId];
    });
  };

  const handleBatchSelectFusion = (ids: string[]) => {
    const clean = ids.slice(0, 3);
    setFusionIds(clean);
    setToastMsg(`已框选 ${clean.length} 张参考图，可直接点击「融合出图」`);
    setFusionOpen(true);
  };

  const handleRunSemanticSearch = async (uploadedFile?: File | null) => {
    const q = searchQuery.trim();
    if (!q && !uploadedFile) {
      setToastMsg('请输入语义描述，或点击右侧相机图标上传参考图以图搜图');
      return;
    }
    setSemanticLoading(true);
    setSemanticError(null);
    try {
      const form = new FormData();
      form.append('query', q);
      form.append('top_k', '24');
      if (uploadedFile) {
        form.append('image', uploadedFile);
      }
      const res = await fetch('/api/atlas/semantic-search', {
        method: 'POST',
        body: form,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || `语义检索失败 (HTTP ${res.status})`);
      }
      const scoreMap: Record<string, number> = {};
      for (const r of data.results ?? []) {
        scoreMap[r.asset_id] = r.score;
      }
      setSemanticScores(scoreMap);
      setQueryMap3d(data.query_map_3d ?? null);
      setSemanticMode(data.mode ?? 'text');
      setSemanticLatencyMs(data.latency_ms ?? null);
      if (uploadedFile) setSemanticImageName(uploadedFile.name);
      else setSemanticImageName(null);
      setVisibleLimit(24);
      setToastMsg(
        `Gemini Embedding 2 召回 Top-${Object.keys(scoreMap).length}（${Math.round(data.latency_ms ?? 0)} ms）`
      );
    } catch (err) {
      setSemanticError(
        err instanceof Error
          ? err.message
          : '请确认本地 FastAPI (127.0.0.1:8780) 已启动。'
      );
    } finally {
      setSemanticLoading(false);
    }
  };

  const clearSemanticSearch = () => {
    setSemanticScores(null);
    setQueryMap3d(null);
    setSemanticMode(null);
    setSemanticImageName(null);
    setSemanticLatencyMs(null);
    setSemanticError(null);
  };

  const profileBaselineScores = useMemo(() => {
    const sig = bundle.aesthetic_profile?.axis_signature;
    const out: Record<SpectrumAxisId, number> = {
      tectonic_honesty: 0.4,
      surface_entropy: 0.02,
      spatial_density: -0.07,
      geometric_order: 0.26,
      lighting_drama: 0.21,
      chromatic_tension: 0.09,
      thermal_mood: 0.3,
      reality_abstraction: 0.19,
    };
    if (sig) {
      for (const ax of ALL_AXIS_IDS) {
        if (sig[ax]) out[ax] = Number(sig[ax].weighted_mean.toFixed(2));
      }
    }
    return out;
  }, [bundle.aesthetic_profile]);

  const originCounts = useMemo(() => {
    let pin = 0;
    let exp = 0;
    for (const a of liveAssets) {
      if (a.source_origin === 'pinterest_personal' || a.subject_isolation.is_personal_prior) pin += 1;
      else exp += 1;
    }
    return { all: liveAssets.length, pinterest_personal: pin, profile_expansion: exp };
  }, [liveAssets]);

  const lexicalIndex = useMemo(() => {
    const idx = new Map<string, string>();
    for (const a of liveAssets) {
      const critique = a.aesthetic_critique;
      idx.set(
        a.asset_id,
        [
          a.title,
          a.archetype_label,
          a.aesthetic_style_zh,
          a.aesthetic_style_en,
          a.native_style_primary,
          a.native_style_secondary,
          a.sub_style ?? a.sub_category,
          a.board_name,
          a.rag_facets?.medium,
          a.rag_facets?.typology,
          a.rag_facets?.lighting,
          ...(a.rag_facets?.materials ?? []),
          ...(a.visual_traits ?? []),
          ...(a.rag_doc?.model_prompt_tokens ?? []),
          critique?.headline_insight,
          critique?.proportion_and_order,
          critique?.material_and_detail,
          critique?.light_and_palette,
          critique?.why_you_love_it,
          a.granular_descriptors.material_stack,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase(),
      );
    }
    return idx;
  }, [liveAssets]);

  const originScopedAssets = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const useLexical = q.length > 0 && !semanticScores;
    return liveAssets.filter((a) => {
      const isPin = a.source_origin === 'pinterest_personal' || a.subject_isolation.is_personal_prior;
      if (originFilter === 'pinterest_personal' && !isPin) return false;
      if (originFilter === 'profile_expansion' && isPin) return false;
      if (useLexical) {
        const hay = lexicalIndex.get(a.asset_id) ?? '';
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [liveAssets, lexicalIndex, originFilter, searchQuery, semanticScores]);

  const archetypeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: originScopedAssets.length };
    for (const a of originScopedAssets) {
      const key = a.archetype ?? 'architecture';
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  }, [originScopedAssets]);

  const archetypeScopedAssets = useMemo(() => {
    if (archetypeFilter === 'all') return originScopedAssets;
    return originScopedAssets.filter((a) => a.archetype === archetypeFilter);
  }, [originScopedAssets, archetypeFilter]);

  const styleOptions = useMemo(() => {
    const map = new Map<
      AestheticStyleId,
      { id: AestheticStyleId; zh: string; en: string; count: number }
    >();
    for (const a of archetypeScopedAssets) {
      const sid = a.aesthetic_style;
      if (!sid) continue;
      const existing = map.get(sid);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(sid, {
          id: sid,
          zh: a.aesthetic_style_zh ?? a.sub_style ?? sid,
          en: a.aesthetic_style_en ?? sid,
          count: 1,
        });
      }
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  }, [archetypeScopedAssets]);

  const styleScopedAssets = useMemo(() => {
    if (styleFilter === 'all') return archetypeScopedAssets;
    return archetypeScopedAssets.filter((a) => a.aesthetic_style === styleFilter);
  }, [archetypeScopedAssets, styleFilter]);

  const activeFacetOptions = useMemo(() => {
    // Count values for activeFacetKey while honoring OTHER active facet keys
    const counts: Record<string, number> = {};
    for (const a of styleScopedAssets) {
      let matchesOthers = true;
      for (const [fk, fv] of Object.entries(selectedFacets) as Array<[RagFacetKey, string | undefined]>) {
        if (!fv || fk === activeFacetKey) continue;
        if (!assetMatchesFacet(a, fk, fv)) {
          matchesOthers = false;
          break;
        }
      }
      if (!matchesOthers || !a.rag_facets) continue;
      const val = a.rag_facets[activeFacetKey];
      if (Array.isArray(val)) {
        for (const item of val) counts[item] = (counts[item] ?? 0) + 1;
      } else if (val) {
        counts[val] = (counts[val] ?? 0) + 1;
      }
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [styleScopedAssets, selectedFacets, activeFacetKey]);

  const facetScopedAssets = useMemo(() => {
    const activeEntries = (Object.entries(selectedFacets) as Array<[RagFacetKey, string | undefined]>).filter(
      (entry): entry is [RagFacetKey, string] => Boolean(entry[1])
    );
    return activeEntries.length === 0
      ? styleScopedAssets
      : styleScopedAssets.filter((a) => activeEntries.every(([fk, fv]) => assetMatchesFacet(a, fk, fv)));
  }, [styleScopedAssets, selectedFacets]);

  const filteredAssets = useMemo(() => {
    let list = facetScopedAssets;
    if (semanticScores) {
      const matched = list.filter((a) => semanticScores[a.asset_id] !== undefined);
      if (matched.length > 0) {
        list = [...matched].sort(
          (a, b) => (semanticScores[b.asset_id] ?? 0) - (semanticScores[a.asset_id] ?? 0)
        );
      }
    }
    return list;
  }, [facetScopedAssets, semanticScores]);

  const selectedIndex = useMemo(() => {
    if (!selectedAssetId) return -1;
    return filteredAssets.findIndex((a) => a.asset_id === selectedAssetId);
  }, [filteredAssets, selectedAssetId]);

  const activeModalAsset: CuratedShowcaseAsset | null = useMemo(() => {
    if (!selectedAssetId) return null;
    if (selectedIndex >= 0) return filteredAssets[selectedIndex];
    return allAssetsById[selectedAssetId] ?? null;
  }, [selectedAssetId, selectedIndex, filteredAssets, allAssetsById]);

  const handleCopyHex = async (hex: string) => {
    setCopiedHex(hex);
    setTimeout(() => setCopiedHex(null), 1300);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(hex);
        setToastMsg(`已复制色值 ${hex}`);
      }
    } catch {
      setToastMsg(`色值 ${hex}`);
    }
  };

  const activeFacetEntries = useMemo(
    () =>
      (Object.entries(selectedFacets) as Array<[RagFacetKey, string | undefined]>).filter(
        (entry): entry is [RagFacetKey, string] => Boolean(entry[1])
      ),
    [selectedFacets]
  );

  const hasFilters =
    searchQuery.trim().length > 0 ||
    originFilter !== 'all' ||
    archetypeFilter !== 'all' ||
    styleFilter !== 'all' ||
    activeFacetEntries.length > 0 ||
    Boolean(semanticScores);

  const handleReset = () => {
    setSearchQuery('');
    setOriginFilter('all');
    setArchetypeFilter('all');
    setStyleFilter('all');
    setSelectedFacets({});
    clearSemanticSearch();
    setVisibleLimit(24);
  };

  const handleExportRagJsonl = () => {
    const lines = filteredAssets.map((a) =>
      JSON.stringify({
        ...(a.rag_doc ?? {
          doc_id: a.asset_id,
          archetype: a.archetype,
          style_id: a.aesthetic_style,
          style_zh: a.aesthetic_style_zh,
          style_en: a.aesthetic_style_en,
          facets: a.rag_facets,
        }),
        title: a.title,
        headline_insight: a.aesthetic_critique?.headline_insight ?? '',
        why_you_love_it: a.aesthetic_critique?.why_you_love_it ?? '',
      })
    );
    const blob = new Blob([lines.join('\n') + '\n'], { type: 'application/x-ndjson;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `aethervault_rag_${filteredAssets.length}_docs.jsonl`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setToastMsg(`已导出 ${filteredAssets.length} 条受控 RAG 索引 (.jsonl)`);
  };

  return (
    <>
      <div className="space-y-8">
      {/* Personal Aesthetic DNA Summary Header Card */}
      <section className="rounded-xl border border-border bg-card p-5 sm:p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1.5 max-w-3xl">
            <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-[-0.02em] text-foreground">
              个人视觉审美图谱 · {liveAssets.length} 张高审美档案深度解构
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              基于全量 523 张个人 Pinterest 原图提炼审美基因，精选保留 {originCounts.pinterest_personal} 张个人核心与{' '}
              {originCounts.profile_expansion} 张当代 Pinterest 同频扩展——全库经 Gemini 4 Hydrogen 原图直读与 Gemini Embedding 2 多模态向量索引，支持语义/以图搜图、3D 点阵引力星图漫游与 Nano Banana 2.1 跨界融合出图。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 self-start sm:self-center shrink-0">
            <button
              type="button"
              onClick={() => setCalibrationOpen(true)}
              className="min-h-[36px] px-3 rounded-md border border-primary/50 hover:border-primary bg-primary/10 hover:bg-primary/15 text-xs font-semibold text-primary inline-flex items-center gap-1.5 transition-colors"
            >
              <Scale className="w-3.5 h-3.5" />
              <span>品味校准台</span>
            </button>
            <button
              type="button"
              onClick={() => setIngestOpen(true)}
              className="min-h-[36px] px-3 rounded-md border border-border hover:border-primary/60 bg-card text-xs font-semibold text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <ImagePlus className="w-3.5 h-3.5 text-primary" />
              <span>导入新图</span>
            </button>
            <button
              type="button"
              onClick={() => setFusionOpen(true)}
              className={`min-h-[36px] px-3 rounded-md border text-xs font-semibold inline-flex items-center gap-1.5 transition-colors ${
                fusionIds.length > 0
                  ? 'border-amber-500 bg-amber-500/15 text-amber-600 dark:text-amber-400'
                  : 'border-border hover:border-primary/60 bg-card text-foreground'
              }`}
            >
              <Wand2 className="w-3.5 h-3.5" />
              <span>融合出图 ({fusionIds.length}/3)</span>
            </button>
            <button
              type="button"
              onClick={() => setDnaOpen((v) => !v)}
              className="min-h-[36px] px-3 rounded-md border border-border hover:border-primary/60 bg-card text-xs font-semibold text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              {dnaOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              <span>{dnaOpen ? '收起画像' : '展开画像'}</span>
            </button>
          </div>
        </div>

        {dnaOpen && bundle.aesthetic_profile && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-4 border-t border-border items-center">
            <div className="lg:col-span-5 space-y-2.5">
              <div className="text-xs font-bold text-foreground">你的核心审美指纹</div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                在连续光谱统计中，你的审美最看重
                <strong className="text-foreground">
                  真实构筑与材质交接（{profileBaselineScores.tectonic_honesty >= 0 ? '+' : ''}
                  {profileBaselineScores.tectonic_honesty.toFixed(2)}）
                </strong>
                、
                <strong className="text-foreground">
                  温润原木/石土触觉（{profileBaselineScores.thermal_mood >= 0 ? '+' : ''}
                  {profileBaselineScores.thermal_mood.toFixed(2)}）
                </strong>
                与
                <strong className="text-foreground">
                  清晰几何比例秩序（{profileBaselineScores.geometric_order >= 0 ? '+' : ''}
                  {profileBaselineScores.geometric_order.toFixed(2)}）
                </strong>
                ；偏好高明度中性矿石基底搭配柔和自然光影，克制低留白压迫感。
              </p>
              <div className="flex flex-wrap gap-2 pt-1 text-xs">
                {[
                  { label: '构造诚实', val: profileBaselineScores.tectonic_honesty },
                  { label: '温润材质', val: profileBaselineScores.thermal_mood },
                  { label: '几何秩序', val: profileBaselineScores.geometric_order },
                  { label: '光影层次', val: profileBaselineScores.lighting_drama },
                ].map((item) => (
                  <span
                    key={item.label}
                    className="rounded-md border border-border bg-secondary/50 px-2.5 py-1 text-xs text-foreground"
                  >
                    {item.label}{' '}
                    <span className="mono font-semibold text-primary">
                      {item.val > 0 ? `+${item.val.toFixed(2)}` : item.val.toFixed(2)}
                    </span>
                  </span>
                ))}
              </div>
            </div>

            {/* 10 Dominant Swatches */}
            <div className="lg:col-span-4 space-y-2">
              <div className="text-xs font-bold text-foreground">高频色盘基底（点击复制）</div>
              <div className="grid grid-cols-5 gap-1.5">
                {bundle.aesthetic_profile.dominant_color_clusters.slice(0, 10).map((c) => {
                  const isCopied = copiedHex === c.hex;
                  return (
                    <button
                      key={c.hex}
                      type="button"
                      onClick={() => handleCopyHex(c.hex)}
                      title={`点击复制 ${c.hex}（出现 ${c.count} 次）`}
                      className="group rounded-md overflow-hidden border border-border hover:border-primary/60 bg-card transition-colors text-center"
                    >
                      <div className="relative h-7 w-full" style={{ backgroundColor: c.hex }}>
                        <span
                          className={`absolute inset-0 flex items-center justify-center transition-opacity ${
                            isCopied
                              ? 'opacity-100 bg-black/45 text-white'
                              : 'opacity-0 group-hover:opacity-100 bg-black/30 text-white'
                          }`}
                          aria-hidden="true"
                        >
                          {isCopied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        </span>
                      </div>
                      <div className="px-0.5 py-0.5 mono text-[10px] text-muted-foreground whitespace-nowrap">
                        {isCopied ? '已复制' : c.hex}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Lightweight 8-Axis Mini-Radar */}
            <div className="lg:col-span-3 flex justify-center">
              <AestheticMiniRadar
                primaryScores={profileBaselineScores}
                sizeClass="w-full max-w-[210px]"
              />
            </div>
          </div>
        )}
      </section>

      {/* Two-Tier Taxonomy + Search + Grid/3D Switcher */}
      <section className="space-y-4">
        {/* Control Row 1 */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center gap-3">
          <div className="flex-1 flex items-center h-10 rounded-md border border-border focus-within:border-primary bg-card overflow-hidden">
            <label htmlFor="atlas-search" className="sr-only">
              关键词过滤或输入自然语言语义搜图
            </label>
            <div className="pl-3 text-muted-foreground" aria-hidden="true">
              <Search className="w-4 h-4" />
            </div>
            <input
              id="atlas-search"
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                if (semanticScores && !semanticImageName) clearSemanticSearch();
                setVisibleLimit(24);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && searchQuery.trim()) {
                  e.preventDefault();
                  handleRunSemanticSearch(null);
                }
              }}
              placeholder="输入关键词实时筛，或按回车「语义搜图」（如：像春雨那种点阵秩序用在金属导视上）..."
              className="flex-1 min-w-0 h-full px-3 text-sm bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
            {(searchQuery || semanticScores) && (
              <button
                type="button"
                aria-label="清空搜索"
                onClick={() => {
                  setSearchQuery('');
                  clearSemanticSearch();
                }}
                className="h-full px-2 text-muted-foreground hover:text-foreground flex items-center"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            <button
              type="button"
              disabled={semanticLoading}
              onClick={() => handleRunSemanticSearch(null)}
              title="使用 Gemini Embedding 2 执行多模态语义搜图"
              className="h-full px-2.5 border-l border-border bg-secondary/40 hover:bg-secondary text-xs font-semibold text-primary inline-flex items-center gap-1 shrink-0 transition-colors"
            >
              {semanticLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">语义搜图</span>
            </button>
            <input
              ref={imageSearchInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleRunSemanticSearch(f);
                e.currentTarget.value = '';
              }}
            />
            <button
              type="button"
              disabled={semanticLoading}
              onClick={() => imageSearchInputRef.current?.click()}
              title="上传任意参考图以图搜图（Gemini Embedding 2）"
              aria-label="以图搜图"
              className="h-full px-2.5 border-l border-border bg-card hover:bg-secondary/60 text-xs font-medium text-foreground inline-flex items-center gap-1 shrink-0 transition-colors"
            >
              <ImageIcon className="w-3.5 h-3.5 text-primary" />
              <span className="hidden md:inline">以图搜图</span>
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <div
              role="group"
              aria-label="来源筛选"
              className="inline-flex h-10 rounded-md border border-border divide-x divide-border overflow-hidden"
            >
              {(
                [
                  { key: 'all', label: `全部 (${originCounts.all})` },
                  { key: 'pinterest_personal', label: `Pinterest (${originCounts.pinterest_personal})` },
                  { key: 'profile_expansion', label: `同频扩展 (${originCounts.profile_expansion})` },
                ] as const
              ).map((it) => {
                const active = originFilter === it.key;
                return (
                  <button
                    key={it.key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setOriginFilter(it.key);
                      setVisibleLimit(24);
                    }}
                    className={`h-full px-3 text-xs font-medium whitespace-nowrap transition-colors ${
                      active
                        ? 'bg-primary text-primary-foreground font-semibold'
                        : 'bg-card text-foreground hover:bg-secondary/60'
                    }`}
                  >
                    {it.label}
                  </button>
                );
              })}
            </div>

            <div
              role="group"
              aria-label="视图切换"
              className="inline-flex h-10 rounded-md border border-border divide-x divide-border overflow-hidden"
            >
              <button
                type="button"
                aria-pressed={viewMode === 'grid'}
                onClick={() => setViewMode('grid')}
                className={`h-full px-3 text-xs font-medium inline-flex items-center gap-1.5 transition-colors ${
                  viewMode === 'grid'
                    ? 'bg-foreground text-background font-semibold'
                    : 'bg-card text-foreground hover:bg-secondary/60'
                }`}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span>画廊网格</span>
              </button>
              <button
                type="button"
                aria-pressed={viewMode === 'constellation'}
                onClick={() => setViewMode('constellation')}
                className={`h-full px-3 text-xs font-medium inline-flex items-center gap-1.5 transition-colors ${
                  viewMode === 'constellation'
                    ? 'bg-foreground text-background font-semibold'
                    : 'bg-card text-foreground hover:bg-secondary/60'
                }`}
              >
                <Orbit className="w-3.5 h-3.5" />
                <span>3D 审美星图</span>
              </button>
            </div>

            {hasFilters && (
              <button
                type="button"
                onClick={handleReset}
                className="h-10 rounded-md px-3 border border-border hover:border-primary/60 bg-card text-xs font-medium text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>重置</span>
              </button>
            )}
          </div>
        </div>

        {/* Active Multimodal Semantic / Image Search Status Banner */}
        {(semanticScores || semanticError) && (
          <div
            className={`rounded-lg border px-3.5 py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs ${
              semanticError
                ? 'border-destructive/50 bg-destructive/10 text-destructive'
                : 'border-primary/40 bg-primary/10 text-foreground'
            }`}
          >
            {semanticError ? (
              <span>{semanticError}</span>
            ) : (
              <span className="inline-flex flex-wrap items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-primary shrink-0" />
                <strong>
                  Gemini Embedding 2 {semanticMode === 'image' ? '以图搜图' : semanticMode === 'multimodal' ? '图文多模态检索' : '语义检索'}
                </strong>
                {semanticImageName && (
                  <span className="rounded bg-card border border-border px-1.5 py-0.5 mono text-[11px]">
                    参考图: {semanticImageName}
                  </span>
                )}
                <span className="text-muted-foreground">
                  已按余弦相似度重排 Top-{Object.keys(semanticScores ?? {}).length}（{Math.round(semanticLatencyMs ?? 0)} ms）· 切换「2D 语义画布」可查看落点与连线
                </span>
              </span>
            )}
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                clearSemanticSearch();
              }}
              className="text-xs font-semibold text-primary hover:underline shrink-0"
            >
              退出语义检索
            </button>
          </div>
        )}

        {/* Tier 1: 7 Primary Archetype Pills + Tier 2: 12 Model-Native Aesthetic Styles + Tier 3: Bounded 4-Key RAG Facets */}
        <div className="space-y-3 pt-1">
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="一级设计门类 (Archetype)">
            <button
              type="button"
              aria-pressed={archetypeFilter === 'all'}
              onClick={() => {
                setArchetypeFilter('all');
                setStyleFilter('all');
                setVisibleLimit(24);
              }}
              className={`min-h-[34px] rounded-md px-3.5 text-xs font-semibold border transition-colors ${
                archetypeFilter === 'all'
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-card text-foreground hover:border-primary/60'
              }`}
            >
              全部门类 <span className="mono opacity-80">({archetypeCounts.all ?? 0})</span>
            </button>
            {ARCHETYPE_ORDER.map((arch) => {
              const cnt = archetypeCounts[arch.key] ?? 0;
              if (cnt === 0) return null;
              const active = archetypeFilter === arch.key;
              return (
                <button
                  key={arch.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    setArchetypeFilter(arch.key);
                    setStyleFilter('all');
                    setVisibleLimit(24);
                  }}
                  className={`min-h-[34px] rounded-md px-3.5 text-xs font-medium border transition-colors ${
                    active
                      ? 'border-primary bg-primary text-primary-foreground font-semibold'
                      : 'border-border bg-card text-foreground hover:border-primary/60'
                  }`}
                >
                  {arch.label} <span className="mono opacity-75">({cnt})</span>
                </button>
              );
            })}
          </div>

          {/* Tier 2: Canonical Model-Native Aesthetic Styles (12 Bounded Movements) */}
          {styleOptions.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="二级美学风格（模型原生词）">
              <span className="text-[11px] text-muted-foreground mr-1 inline-flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-primary" />
                美学风格：
              </span>
              <button
                type="button"
                aria-pressed={styleFilter === 'all'}
                onClick={() => {
                  setStyleFilter('all');
                  setVisibleLimit(24);
                }}
                className={`rounded-full px-3 py-1 text-xs border transition-colors ${
                  styleFilter === 'all'
                    ? 'border-primary bg-primary text-primary-foreground font-semibold'
                    : 'border-border bg-secondary/40 text-foreground hover:border-primary/60'
                }`}
              >
                不限 <span className="mono opacity-80">({archetypeScopedAssets.length})</span>
              </button>
              {(archetypeFilter === 'all' ? styleOptions.slice(0, 12) : styleOptions).map((st) => {
                const active = styleFilter === st.id;
                return (
                  <button
                    key={st.id}
                    type="button"
                    aria-pressed={active}
                    title={`模型原生风格词：${st.en}`}
                    onClick={() => {
                      setStyleFilter(active ? 'all' : st.id);
                      setVisibleLimit(24);
                    }}
                    className={`rounded-full px-3 py-1 text-xs border transition-colors ${
                      active
                        ? 'border-primary bg-primary text-primary-foreground font-semibold'
                        : 'border-border bg-secondary/40 text-foreground hover:border-primary/60'
                    }`}
                  >
                    {st.zh}{' '}
                    <span className="mono text-[10px] opacity-75">
                      {st.en} · {st.count}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Tier 3: Bounded 4-Key RAG Faceted Tag Filter & Export */}
          {bundle.rag_schema && (
            <div className="rounded-lg border border-border bg-secondary/30 p-3 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="RAG 受控标签维度（限 4 键）">
                  <span className="text-[11px] font-semibold text-foreground mr-1 inline-flex items-center gap-1">
                    <Database className="w-3 h-3 text-primary" />
                    RAG 标签键：
                  </span>
                  {RAG_FACET_KEYS.map((fk) => {
                    const active = activeFacetKey === fk.key;
                    const hasSelection = Boolean(selectedFacets[fk.key]);
                    return (
                      <button
                        key={fk.key}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        title={fk.hint}
                        onClick={() => setActiveFacetKey(fk.key)}
                        className={`h-7 rounded-md px-2.5 text-xs border transition-colors inline-flex items-center gap-1.5 ${
                          active
                            ? 'border-foreground bg-foreground text-background font-semibold'
                            : 'border-border bg-card text-foreground hover:border-primary/60'
                        }`}
                      >
                        <span>{fk.label}</span>
                        <span className="mono text-[10px] opacity-70">{fk.key}</span>
                        {hasSelection && (
                          <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" aria-hidden="true" />
                        )}
                      </button>
                    );
                  })}
                </div>

                <button
                  type="button"
                  onClick={handleExportRagJsonl}
                  className="h-7 rounded-md px-2.5 border border-border hover:border-primary/60 bg-card text-xs font-medium text-foreground inline-flex items-center gap-1.5 transition-colors shrink-0"
                >
                  <Download className="w-3 h-3 text-primary" />
                  <span>导出 RAG JSONL ({filteredAssets.length})</span>
                </button>
              </div>

              {/* Active Facet Value Chips for Current Key */}
              <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={`RAG ${activeFacetKey} 候选标签`}>
                {activeFacetOptions.map(([val, cnt]) => {
                  const active = selectedFacets[activeFacetKey] === val;
                  return (
                    <button
                      key={val}
                      type="button"
                      aria-pressed={active}
                      onClick={() => {
                        setSelectedFacets((prev) => ({
                          ...prev,
                          [activeFacetKey]: prev[activeFacetKey] === val ? undefined : val,
                        }));
                        setVisibleLimit(24);
                      }}
                      className={`rounded-md px-2.5 py-1 text-[11px] border transition-colors ${
                        active
                          ? 'border-primary bg-primary text-primary-foreground font-semibold'
                          : 'border-border bg-card text-foreground hover:border-primary/60'
                      }`}
                    >
                      {val} <span className="mono opacity-75">({cnt})</span>
                    </button>
                  );
                })}
              </div>

              {/* Active Cross-Key RAG Filter Pills */}
              {activeFacetEntries.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-border/70 text-[11px]">
                  <span className="text-muted-foreground">已选 RAG 过滤：</span>
                  {activeFacetEntries.map(([fk, fv]) => {
                    const keyLabel = RAG_FACET_KEYS.find((x) => x.key === fk)?.label ?? fk;
                    return (
                      <button
                        key={fk}
                        type="button"
                        onClick={() => {
                          setSelectedFacets((prev) => ({ ...prev, [fk]: undefined }));
                          setVisibleLimit(24);
                        }}
                        className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 text-primary px-2.5 py-0.5 font-medium hover:bg-primary/20 transition-colors"
                      >
                        <span>
                          {keyLabel}: {fv}
                        </span>
                        <X className="w-3 h-3" />
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Main Content: 3D Dot-Matrix Aesthetic Constellation OR Clean Editorial Grid */}
      {viewMode === 'constellation' ? (
        facetScopedAssets.length > 0 ? (
          <AestheticConstellation3D
            assets={facetScopedAssets}
            fusionIds={fusionIds}
            queryMap3d={queryMap3d}
            semanticScores={semanticScores}
            onSelectAsset={(asset) => setSelectedAssetId(asset.asset_id)}
            onToggleFusion={handleToggleFusion}
            onBatchSelectFusion={handleBatchSelectFusion}
          />
        ) : (
          <div className="rounded-xl border border-border bg-secondary/50 p-12 text-center text-sm text-muted-foreground">
            当前筛选条件下暂无样本，请重置筛选后查看 3D 审美星图。
          </div>
        )
      ) : filteredAssets.length === 0 ? (
        <div className="rounded-xl border border-border bg-secondary/50 py-16 px-6 text-center space-y-3">
          <div className="text-base font-bold text-foreground">未找到匹配的审美档案</div>
          <p className="text-xs text-muted-foreground">可清空关键词或切换门类查看全部 {liveAssets.length} 件图库样本。</p>
          <button
            type="button"
            onClick={handleReset}
            className="min-h-[38px] rounded-md px-5 bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold transition-colors"
          >
            查看全部样本
          </button>
        </div>
      ) : (
        <div className="space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-9 items-stretch">
            {filteredAssets.slice(0, visibleLimit).map((asset) => {
              const headline =
                asset.aesthetic_critique?.headline_insight ?? asset.granular_descriptors.material_stack;
              const imgObjPos =
                asset.archetype === 'illustration_character' || asset.archetype === 'fashion_photography'
                  ? 'object-top'
                  : 'object-center';
              const isPinnedFusion = fusionIds.includes(asset.asset_id);
              const semScore = semanticScores?.[asset.asset_id];
              return (
                <article key={asset.asset_id} className="group/card relative flex flex-col h-full">
                  <button
                    type="button"
                    onClick={() => handleToggleFusion(asset.asset_id)}
                    title={isPinnedFusion ? '从融合参考槽移除' : '加入 Nano Banana 2.1 融合参考槽'}
                    aria-label={isPinnedFusion ? `从融合槽移除 ${asset.title}` : `将 ${asset.title} 加入融合槽`}
                    className={`absolute top-2 right-2 z-10 h-7 px-2 rounded-md border text-[11px] font-semibold inline-flex items-center gap-1 shadow-sm transition-opacity ${
                      isPinnedFusion
                        ? 'opacity-100 border-amber-500 bg-amber-500 text-white'
                        : 'opacity-0 group-hover/card:opacity-100 focus-visible:opacity-100 border-white/30 bg-black/70 text-white hover:bg-primary'
                    }`}
                  >
                    {isPinnedFusion ? <Check className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                    <span>{isPinnedFusion ? '已选' : '融合'}</span>
                  </button>
                  {semScore !== undefined && (
                    <span className="pointer-events-none absolute top-2 left-2 z-10 rounded bg-primary/90 text-primary-foreground px-1.5 py-0.5 mono text-[10px] font-semibold shadow-sm">
                      {Math.round(semScore * 100)}% 相似
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setSelectedAssetId(asset.asset_id)}
                    aria-label={`查看「${asset.title}」的深度美学分析`}
                    className="group flex-1 flex flex-col text-left focus-visible:outline-none"
                  >
                    <div className="aspect-[4/3] w-full shrink-0 rounded-md overflow-hidden border border-border/60 bg-secondary/50">
                      <img
                        src={asset.image_url}
                        alt={asset.title}
                        loading="lazy"
                        className={`w-full h-full object-cover ${imgObjPos} group-hover:scale-[1.02] transition-transform duration-300`}
                      />
                    </div>
                    <div className="mt-2.5 flex-1 flex flex-col space-y-1 w-full">
                      <h2 className="text-sm font-bold text-foreground truncate group-hover:text-primary transition-colors" title={asset.title}>
                        {asset.title}
                      </h2>
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-primary font-medium truncate">
                          {asset.archetype_label ?? asset.subject_isolation.domain_label} ·{' '}
                          {asset.aesthetic_style_zh ?? asset.sub_style ?? asset.sub_category}
                        </span>
                        {asset.aspect_label && (
                          <span className="mono text-[11px] text-muted-foreground shrink-0">
                            {asset.aspect_label}
                          </span>
                        )}
                      </div>
                      {asset.rag_facets && (
                        <div className="flex items-center gap-1 h-5 overflow-hidden">
                          <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-foreground shrink-0">
                            {asset.rag_facets.typology}
                          </span>
                          {asset.rag_facets.materials[0] && (
                            <span className="rounded border border-border/80 bg-card px-1.5 py-0.5 text-[10px] text-muted-foreground shrink-0">
                              {asset.rag_facets.materials[0]}
                            </span>
                          )}
                          {asset.rag_facets.medium && (
                            <span className="rounded border border-border/80 bg-card px-1.5 py-0.5 text-[10px] text-muted-foreground truncate">
                              {asset.rag_facets.medium}
                            </span>
                          )}
                        </div>
                      )}
                      <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed min-h-[2.45rem]">
                        {headline}
                      </p>
                    </div>
                  </button>

                  {/* Continuous OKLab 5-color swatch strip (pinned flush to card bottom) */}
                  <div
                    role="group"
                    aria-label={`${asset.title} 主色板`}
                    className="mt-2.5 flex h-4 w-full shrink-0 rounded-sm border border-border overflow-hidden"
                  >
                    {asset.granular_descriptors.color_palette.slice(0, 5).map((hex, idx) => (
                      <button
                        key={`${hex}-${idx}`}
                        type="button"
                        onClick={() => handleCopyHex(hex)}
                        title={`点击复制 ${hex}`}
                        aria-label={`复制主色 ${hex}`}
                        style={{ backgroundColor: hex }}
                        className="flex-1 h-full hover:opacity-80 transition-opacity"
                      />
                    ))}
                  </div>
                </article>
              );
            })}
          </div>

          {visibleLimit < filteredAssets.length && (
            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => setVisibleLimit((v) => v + 24)}
                className="min-h-[42px] rounded-md px-6 border border-border hover:border-primary/60 bg-card hover:bg-secondary/60 text-xs font-semibold text-foreground transition-colors"
              >
                展开更多 (+24，当前 {Math.min(visibleLimit, filteredAssets.length)} / {filteredAssets.length})
              </button>
              <button
                type="button"
                onClick={() => setVisibleLimit(filteredAssets.length)}
                className="min-h-[42px] rounded-md px-5 border border-border hover:border-primary/60 bg-secondary/40 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                显示当前分类全部 ({filteredAssets.length} 件)
              </button>
            </div>
          )}
        </div>
      )}
      </div>

      {/* Deep Aesthetic Critique Modal (outside space-y-8 so margin-top never shifts fixed backdrop) */}
      <AestheticDetailModal
        asset={activeModalAsset}
        allAssetsById={allAssetsById}
        profileBaselineScores={profileBaselineScores}
        currentIndex={Math.max(0, selectedIndex)}
        totalFiltered={filteredAssets.length}
        isInFusion={activeModalAsset ? fusionIds.includes(activeModalAsset.asset_id) : false}
        onToggleFusion={handleToggleFusion}
        onSelectNeighbor={(neighborId) => setSelectedAssetId(neighborId)}
        onPrev={() => {
          if (filteredAssets.length <= 1 || selectedIndex < 0) return;
          const prevIdx = (selectedIndex - 1 + filteredAssets.length) % filteredAssets.length;
          setSelectedAssetId(filteredAssets[prevIdx].asset_id);
        }}
        onNext={() => {
          if (filteredAssets.length <= 1 || selectedIndex < 0) return;
          const nextIdx = (selectedIndex + 1) % filteredAssets.length;
          setSelectedAssetId(filteredAssets[nextIdx].asset_id);
        }}
        onCopyHex={handleCopyHex}
        onClose={() => setSelectedAssetId(null)}
      />

      <NanoBananaFusionModal
        isOpen={fusionOpen}
        selectedAssets={fusionAssets}
        onRemoveAsset={(id) => setFusionIds((prev) => prev.filter((x) => x !== id))}
        onClose={() => setFusionOpen(false)}
      />

      <DropInIngestModal
        isOpen={ingestOpen}
        onIngested={(newAssets) => {
          setLiveAssets((prev) => {
            const seen = new Set(prev.map((a) => a.asset_id));
            const fresh = newAssets.filter((a) => !seen.has(a.asset_id));
            return [...fresh, ...prev];
          });
          setToastMsg(`已新增 ${newAssets.length} 张参考图并即时投影至 2D 语义画布`);
        }}
        onClose={() => setIngestOpen(false)}
      />

      <TasteCalibrationModal isOpen={calibrationOpen} onClose={() => setCalibrationOpen(false)} />

      {toastMsg && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-5 right-5 z-[70] rounded-md shadow-lg px-4 py-2 bg-foreground text-background text-xs font-medium border border-border"
        >
          {toastMsg}
        </div>
      )}
    </>
  );
};
