'use client';

import React, { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  Box,
  Check,
  Copy,
  Layers,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Sparkles,
  X,
} from 'lucide-react';
import {
  ALL_AXIS_IDS,
  compileConflictFreeAstClient,
  computeSalienceGatedDistance,
  distanceToMatchPercent,
  type AestheticAssetContract,
  type SpectrumAxisId,
} from '../engine/salienceMetric';
import { matchesAssetText, parseFuzzyIntent } from '../engine/intentParser';
import type {
  AetherVaultShowcaseBundle,
  AssetDomain,
  AstComparisonBundle,
  AstComparisonPair,
  CuratedShowcaseAsset,
  SpectrumAxisMeta,
} from '../types/aethervault';
import { AstComparisonDrawer } from './AstComparisonDrawer';
import { BeforeAfterSlider } from './BeforeAfterSlider';
import { trackShowcaseEvent } from '../utils/analytics';

const AetherVaultManifold3D = dynamic(
  () => import('./three/AetherVaultManifold3D').then((m) => m.AetherVaultManifold3D),
  {
    ssr: false,
    loading: () => (
      <div className="h-[440px] rounded-xl border border-border bg-card flex items-center justify-center text-xs text-muted-foreground">
        正在加载 Three.js 500 标本 3D 美学光谱流形...
      </div>
    ),
  }
);
import { GoldenAnchorDrawer } from './GoldenAnchorDrawer';
import { SpecimenLightbox, type AstSlotKey } from './SpecimenLightbox';
import {
  VisualCalibrationPanel,
  type CalibrationChoiceOption,
  type CalibrationRoundSpec,
} from './VisualCalibrationPanel';

interface AetherVaultWorkspaceProps {
  bundle: AetherVaultShowcaseBundle;
  comparisonBundle: AstComparisonBundle | null;
  isLiveEngine: boolean;
}

type ScopeFilter = 'all' | 'cross_domain' | 'architecture_only';
type OriginFilter = 'all' | 'pinterest_personal' | 'profile_expansion';

function resolveValidSlots(
  assets: CuratedShowcaseAsset[],
  assetsById: Record<string, CuratedShowcaseAsset>,
  preferred: { optics: string; material: string; lighting: string },
  targetScores: Record<SpectrumAxisId, number>,
): { optics: string; material: string; lighting: string } {
  if (assets.length === 0) return preferred;
  const pickBest = (
    preferredId: string,
    preferredDomains: AssetDomain[],
    exclude: Set<string>,
  ): string => {
    if (assetsById[preferredId]) return preferredId;
    const domainPool = assets.filter(
      (a) => preferredDomains.includes(a.subject_isolation.domain) && !exclude.has(a.asset_id),
    );
    const pool = domainPool.length > 0 ? domainPool : assets.filter((a) => !exclude.has(a.asset_id));
    const candidates = pool.length > 0 ? pool : assets;
    let best = candidates[0];
    let bestDist = Infinity;
    for (const a of candidates) {
      const d = computeSalienceGatedDistance(targetScores, a.style_spectrums);
      if (d < bestDist) {
        bestDist = d;
        best = a;
      }
    }
    return best.asset_id;
  };
  const used = new Set<string>();
  const optics = pickBest(preferred.optics, ['architecture'], used);
  used.add(optics);
  const material = pickBest(preferred.material, ['industrial', 'craft'], used);
  used.add(material);
  const lighting = pickBest(preferred.lighting, ['editorial', 'graphic', 'architecture'], used);
  return { optics, material, lighting };
}

const DEFAULT_QUERY_SCORES: Record<SpectrumAxisId, number> = {
  tectonic_honesty: 0.8,
  surface_entropy: 0.25,
  spatial_density: -0.55,
  geometric_order: 0.75,
  lighting_drama: -0.6,
  chromatic_tension: -0.7,
  thermal_mood: -0.45,
  reality_abstraction: -0.65,
};

const PRESET_INTENTS: Array<{
  key: string;
  label: string;
  query: string;
  subjectCore: string;
  scores: Record<SpectrumAxisId, number>;
  slots: { optics: string; material: string; lighting: string };
}> = [
  {
    key: 'brutalist_cafe',
    label: '预设 1 · 荒野粗粝与精密机械节点',
    query: '荒野 粗粝 克制 精密机械 徕卡 金属节点',
    subjectCore: 'Compact 25sqm outdoor modular pop-up coffee kiosk set in open coastal basalt terrain',
    scores: { ...DEFAULT_QUERY_SCORES },
    slots: { optics: 'arch_01', material: 'ind_02', lighting: 'edit_01' },
  },
  {
    key: 'warm_gallery',
    label: '预设 2 · 静谧东方留白与温润漫射光',
    query: '静谧 东方 留白 茶饮 器物 温润漫射光',
    subjectCore: 'Quiet 90sqm neighborhood tea and ceramic exhibition pavilion with recessed courtyard',
    scores: {
      tectonic_honesty: 0.2,
      surface_entropy: 0.4,
      spatial_density: -0.75,
      geometric_order: 0.55,
      lighting_drama: -0.55,
      chromatic_tension: -0.6,
      thermal_mood: 0.7,
      reality_abstraction: -0.65,
    },
    slots: { optics: 'arch_04', material: 'craft_04', lighting: 'craft_03' },
  },
  {
    key: 'tech_pavilion',
    label: '预设 3 · 高技派轻盈张拉与冷峻实验室',
    query: '高技派 张拉 精密金属 冷峻 实验室',
    subjectCore: 'High-tech modular brand pavilion featuring tension steel struts and glazed lab showcase',
    scores: {
      tectonic_honesty: 0.95,
      surface_entropy: -0.7,
      spatial_density: -0.25,
      geometric_order: 0.9,
      lighting_drama: -0.2,
      chromatic_tension: -0.65,
      thermal_mood: -0.8,
      reality_abstraction: -0.75,
    },
    slots: { optics: 'arch_14', material: 'ind_01', lighting: 'ind_07' },
  },
  {
    key: 'constructivist_flagship',
    label: '预设 4 · 黑曜石暗调与构成主义烈橙秩序',
    query: '黑曜石 暗调 烈橙 构成 几何模数',
    subjectCore: 'Contemporary concept retail facade with matte dark metal rainscreen and sharp portal',
    scores: {
      tectonic_honesty: 0.65,
      surface_entropy: -0.45,
      spatial_density: -0.45,
      geometric_order: 0.9,
      lighting_drama: 0.35,
      chromatic_tension: 0.5,
      thermal_mood: -0.4,
      reality_abstraction: 0.1,
    },
    slots: { optics: 'arch_15', material: 'ind_05', lighting: 'graph_11' },
  },
];

const DOMAIN_OPTIONS: Array<{ key: 'all' | AssetDomain; label: string }> = [
  { key: 'all', label: '全部门类' },
  { key: 'architecture', label: '建筑空间' },
  { key: 'industrial', label: '精密工业' },
  { key: 'editorial', label: '高定摄影' },
  { key: 'craft', label: '东方器物' },
  { key: 'graphic', label: '构成插画' },
];

const AXIS_INTACT_LABELS: Record<SpectrumAxisId, string> = {
  tectonic_honesty: '构造诚实',
  surface_entropy: '肌理时间',
  spatial_density: '空间留白',
  geometric_order: '几何秩序',
  lighting_drama: '光影反差',
  chromatic_tension: '色彩张力',
  thermal_mood: '情绪色温',
  reality_abstraction: '抽象程度',
};

const SLIDER_GROUPS: Array<{ title: string; axes: SpectrumAxisId[] }> = [
  { title: '构筑与秩序', axes: ['tectonic_honesty', 'geometric_order', 'spatial_density'] },
  { title: '表皮与光影', axes: ['surface_entropy', 'lighting_drama'] },
  { title: '色彩与抽象', axes: ['chromatic_tension', 'thermal_mood', 'reality_abstraction'] },
];

function toContract(asset: CuratedShowcaseAsset): AestheticAssetContract {
  return {
    assetId: asset.asset_id,
    title: asset.title,
    domain: asset.subject_isolation.domain,
    domainLabel: asset.subject_isolation.domain_label,
    isPersonalPrior: asset.subject_isolation.is_personal_prior,
    palette: asset.granular_descriptors.color_palette,
    imageUrl: asset.image_url,
    spectrums: asset.style_spectrums,
    opticsCamera: asset.granular_descriptors.optics_camera,
    materialStack: asset.granular_descriptors.material_stack,
    lightingRig: asset.granular_descriptors.lighting_rig,
    negativeGuardrails: asset.compiler_primitives.negative_guardrails,
  };
}

export const AetherVaultWorkspace: React.FC<AetherVaultWorkspaceProps> = ({
  bundle,
  comparisonBundle,
  isLiveEngine,
}) => {
  const comparePairs = comparisonBundle?.pairs ?? [];
  const defaultCompareId = useMemo(() => {
    const sixth = comparePairs.find((p) => p.pair_id.toLowerCase() === 'cmp_06');
    return sixth?.pair_id ?? comparePairs[comparePairs.length - 1]?.pair_id ?? '';
  }, [comparePairs]);

  const [heroPairId, setHeroPairId] = useState<string>('');
  const activeHeroPair = useMemo(
    () =>
      comparePairs.find((p) => p.pair_id === (heroPairId || defaultCompareId)) ??
      comparePairs[0] ??
      null,
    [comparePairs, heroPairId, defaultCompareId],
  );

  // Core retrieval & mixer state
  const [activePresetKey, setActivePresetKey] = useState<string>(PRESET_INTENTS[0].key);
  const [fuzzyInput, setFuzzyInput] = useState('');
  const [intentSummary, setIntentSummary] = useState<string | null>(null);
  const [literalTermsFilter, setLiteralTermsFilter] = useState<string[]>([]);

  const [subjectCore, setSubjectCore] = useState(PRESET_INTENTS[0].subjectCore);
  const [queryScores, setQueryScores] = useState<Record<SpectrumAxisId, number>>({
    ...DEFAULT_QUERY_SCORES,
  });
  const [attentionWeights, setAttentionWeights] = useState<Partial<Record<SpectrumAxisId, number>>>({});
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all');
  const [originFilter, setOriginFilter] = useState<OriginFilter>('all');
  const [domainFilter, setDomainFilter] = useState<'all' | AssetDomain>('all');
  const [subCategoryFilter, setSubCategoryFilter] = useState<string>('all');
  const [boardFilter, setBoardFilter] = useState<string>('all');
  const [onlyPersonalPrior, setOnlyPersonalPrior] = useState(false);
  const [visibleLimit, setVisibleLimit] = useState(24);
  const [selectedSlots, setSelectedSlots] = useState(() => {
    const map: Record<string, CuratedShowcaseAsset> = {};
    for (const a of bundle.assets) map[a.asset_id] = a;
    return resolveValidSlots(bundle.assets, map, PRESET_INTENTS[0].slots, PRESET_INTENTS[0].scores);
  });
  const [profileExpanded, setProfileExpanded] = useState(true);

  // Overlay & drawer state
  const [calibOpen, setCalibOpen] = useState(false);
  const [calibRound, setCalibRound] = useState<1 | 2 | 'done'>(1);
  const [calibChosen, setCalibChosen] = useState<string[]>([]);
  const [spectrumDrawerOpen, setSpectrumDrawerOpen] = useState(false);
  const [activeAnchorAxis, setActiveAnchorAxis] = useState<SpectrumAxisId | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compilerOpen, setCompilerOpen] = useState(false);
  const [show3DManifold, setShow3DManifold] = useState(true);
  const [lightboxAsset, setLightboxAsset] = useState<CuratedShowcaseAsset | null>(null);

  // Copy & toast & live verification state
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [promptCopied, setPromptCopied] = useState(false);
  const [liveCompileLoading, setLiveCompileLoading] = useState(false);
  const [liveCompileStatus, setLiveCompileStatus] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
  };

  useEffect(() => {
    if (!toastMessage) return;
    const t = setTimeout(() => setToastMessage(null), 2200);
    return () => clearTimeout(t);
  }, [toastMessage]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (activeAnchorAxis) {
          setActiveAnchorAxis(null);
        } else if (lightboxAsset) {
          setLightboxAsset(null);
        } else if (calibOpen) {
          setCalibOpen(false);
        } else if (compareOpen) {
          setCompareOpen(false);
        } else if (compilerOpen) {
          setCompilerOpen(false);
        } else if (spectrumDrawerOpen) {
          setSpectrumDrawerOpen(false);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [activeAnchorAxis, lightboxAsset, calibOpen, compareOpen, compilerOpen, spectrumDrawerOpen]);

  const assetsById = useMemo(() => {
    const map: Record<string, CuratedShowcaseAsset> = {};
    for (const a of bundle.assets) map[a.asset_id] = a;
    return map;
  }, [bundle.assets]);

  const axesMetaById = useMemo(() => {
    const map: Record<string, SpectrumAxisMeta> = {};
    for (const ax of bundle.axes) map[ax.axis_id] = ax;
    return map;
  }, [bundle.axes]);

  // Scoped base pool & dynamic domain/origin/sub-category counts (never stale or contradictory)
  const originCounts = useMemo(() => {
    let pin = 0;
    let exp = 0;
    for (const a of bundle.assets) {
      if (a.source_origin === 'pinterest_personal' || (!a.source_origin && a.subject_isolation.is_personal_prior)) {
        pin += 1;
      } else {
        exp += 1;
      }
    }
    return { all: bundle.assets.length, pinterest_personal: pin, profile_expansion: exp };
  }, [bundle.assets]);

  const scopedAssets = useMemo(() => {
    return bundle.assets.filter((asset) => {
      const dom = asset.subject_isolation.domain;
      if (scopeFilter === 'cross_domain' && dom === 'architecture') return false;
      if (scopeFilter === 'architecture_only' && dom !== 'architecture') return false;
      const isPin =
        asset.source_origin === 'pinterest_personal' ||
        (!asset.source_origin && asset.subject_isolation.is_personal_prior);
      if (originFilter === 'pinterest_personal' && !isPin) return false;
      if (originFilter === 'profile_expansion' && isPin) return false;
      if (onlyPersonalPrior && !asset.subject_isolation.is_personal_prior) return false;
      if (boardFilter !== 'all' && asset.board_name !== boardFilter) return false;
      return true;
    });
  }, [bundle.assets, scopeFilter, originFilter, onlyPersonalPrior, boardFilter]);

  const dynamicDomainCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: scopedAssets.length,
      architecture: 0,
      industrial: 0,
      editorial: 0,
      craft: 0,
      graphic: 0,
    };
    for (const a of scopedAssets) {
      counts[a.subject_isolation.domain] = (counts[a.subject_isolation.domain] ?? 0) + 1;
    }
    return counts;
  }, [scopedAssets]);

  const dynamicSubCategories = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const a of scopedAssets) {
      if (domainFilter !== 'all' && a.subject_isolation.domain !== domainFilter) continue;
      if (a.sub_category) {
        counts[a.sub_category] = (counts[a.sub_category] ?? 0) + 1;
      }
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [scopedAssets, domainFilter]);

  // High-speed <20ms client-side salience-gated re-ranking
  const { rankedAssets, matchByAssetId, rerankLatencyMs } = useMemo(() => {
    const t0 = performance.now();
    const filtered = scopedAssets.filter((asset) => {
      if (domainFilter !== 'all' && asset.subject_isolation.domain !== domainFilter) return false;
      if (subCategoryFilter !== 'all' && asset.sub_category !== subCategoryFilter) return false;
      if (literalTermsFilter.length > 0 && !matchesAssetText(asset, literalTermsFilter)) {
        return false;
      }
      return true;
    });

    const matchMap: Record<string, number> = {};
    const scored = filtered.map((asset) => {
      const dist = computeSalienceGatedDistance(queryScores, asset.style_spectrums, attentionWeights);
      const matchScore = distanceToMatchPercent(dist);
      matchMap[asset.asset_id] = matchScore;
      return { asset, dist, matchScore };
    });
    scored.sort((a, b) => a.dist - b.dist);
    const elapsed = Math.max(0.05, performance.now() - t0);
    return { rankedAssets: scored, matchByAssetId: matchMap, rerankLatencyMs: elapsed };
  }, [scopedAssets, domainFilter, subCategoryFilter, literalTermsFilter, queryScores, attentionWeights]);

  const opticsAsset = assetsById[selectedSlots.optics] ?? bundle.assets[0];
  const materialAsset = assetsById[selectedSlots.material] ?? bundle.assets[1] ?? bundle.assets[0];
  const lightingAsset = assetsById[selectedSlots.lighting] ?? bundle.assets[2] ?? bundle.assets[0];

  const compiledAst = useMemo(() => {
    if (!opticsAsset || !materialAsset || !lightingAsset) {
      return { compiledPrompt: '', negativePrompt: '', conflictsIsolatedCount: 0 };
    }
    return compileConflictFreeAstClient(
      subjectCore,
      toContract(opticsAsset),
      toContract(materialAsset),
      toContract(lightingAsset),
      queryScores,
    );
  }, [subjectCore, opticsAsset, materialAsset, lightingAsset, queryScores]);

  const applyIntentQuery = (rawQuery: string) => {
    const parsed = parseFuzzyIntent(rawQuery);
    if (!parsed.raw) {
      setLiteralTermsFilter([]);
      setIntentSummary(null);
      return;
    }

    if (parsed.hasSemanticHits) {
      setActivePresetKey('custom');
      setQueryScores((prev) => ({ ...prev, ...parsed.targetScores }));
      setAttentionWeights(parsed.boostWeights);
      setLiteralTermsFilter([]);
      setIntentSummary(`已将「${parsed.matchedLabels.join(' · ')}」映射至 8 轴意图向量`);
    } else {
      setLiteralTermsFilter(parsed.literalTerms);
      setIntentSummary(`按关键词「${parsed.raw}」过滤材质与样本名称`);
    }
    setLiveCompileStatus(null);
  };

  const handleIntentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = fuzzyInput.trim();
    if (!trimmed) {
      applyIntentQuery('');
      return;
    }
    if (!isLiveEngine) {
      applyIntentQuery(trimmed);
      return;
    }
    try {
      const res = await fetch('/api/aethervault/parse-intent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: trimmed, use_llm: false }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const targetScores = data.target_scores as Record<SpectrumAxisId, number> | undefined;
      if (targetScores && Object.keys(targetScores).length > 0) {
        setActivePresetKey('custom');
        setQueryScores((prev) => ({ ...prev, ...targetScores }));
        setAttentionWeights(data.attention_weights ?? {});
        setLiteralTermsFilter([]);
        setIntentSummary(
          `[Live Engine] 已实时解析「${(data.matched_tokens ?? []).join(' · ')}」并同步至 8 轴光谱与 3D 流形`
        );
        return;
      }
    } catch {
      // Fall back cleanly to deterministic browser intent parser
    }
    applyIntentQuery(trimmed);
  };

  const handlePresetChange = (presetKey: string) => {
    const preset = PRESET_INTENTS.find((p) => p.key === presetKey);
    if (!preset) return;
    setActivePresetKey(preset.key);
    setFuzzyInput(preset.query);
    setLiteralTermsFilter([]);
    setIntentSummary(`已切换场景预设：${preset.label}`);
    setSubjectCore(preset.subjectCore);
    setQueryScores({ ...preset.scores });
    setAttentionWeights({});
    setSelectedSlots(resolveValidSlots(bundle.assets, assetsById, preset.slots, preset.scores));
    setLiveCompileStatus(null);
    showToast(`已切换「${preset.label}」`);
  };

  const handleApplyPersonalProfile = () => {
    const sig = bundle.aesthetic_profile?.axis_signature;
    if (!sig) return;
    const nextScores = { ...DEFAULT_QUERY_SCORES };
    for (const ax of ALL_AXIS_IDS) {
      if (sig[ax]) {
        nextScores[ax] = Number(sig[ax].weighted_mean.toFixed(2));
      }
    }
    setActivePresetKey('custom');
    setFuzzyInput('');
    setLiteralTermsFilter([]);
    setQueryScores(nextScores);
    setAttentionWeights({
      tectonic_honesty: 1.4,
      thermal_mood: 1.3,
      geometric_order: 1.25,
      lighting_drama: 1.2,
    });
    setIntentSummary('已套用您的个人 Pinterest 523 图审美画像 8 轴重心向量');
    showToast('已同步 8 轴滑块至您的个人审美画像重心');
  };

  const handleScopeChange = (nextScope: ScopeFilter) => {
    setScopeFilter(nextScope);
    setVisibleLimit(24);
    if (nextScope === 'cross_domain' && domainFilter === 'architecture') {
      setDomainFilter('all');
    } else if (nextScope === 'architecture_only') {
      setDomainFilter('all');
    }
  };

  const handleResetAllFilters = () => {
    setActivePresetKey(PRESET_INTENTS[0].key);
    setFuzzyInput('');
    setIntentSummary(null);
    setLiteralTermsFilter([]);
    setScopeFilter('all');
    setOriginFilter('all');
    setDomainFilter('all');
    setSubCategoryFilter('all');
    setBoardFilter('all');
    setOnlyPersonalPrior(false);
    setQueryScores({ ...DEFAULT_QUERY_SCORES });
    setAttentionWeights({});
    setVisibleLimit(24);
    showToast('已重置全部筛选条件与 8 轴光谱');
  };

  const handleAssignSlot = (slot: AstSlotKey, assetId: string) => {
    setSelectedSlots((prev) => ({ ...prev, [slot]: assetId }));
    setLiveCompileStatus(null);
    const slotLabel = slot === 'optics' ? '镜头参考' : slot === 'material' ? '材质参考' : '光影参考';
    const assetTitle = assetsById[assetId]?.title ?? assetId;
    showToast(`已将「${assetTitle}」设为${slotLabel}`);
  };

  const handleLoadComparisonPair = (pair: AstComparisonPair) => {
    setSelectedSlots(resolveValidSlots(bundle.assets, assetsById, pair.slots, queryScores));
    setSubjectCore(pair.subject_core);
    setLiveCompileStatus(null);
    showToast(`已载入 ${pair.pair_id.toUpperCase()}（${pair.title_zh}）三槽位至底部托盘`);
  };

  const handleSelectCalibration = (round: CalibrationRoundSpec, opt: CalibrationChoiceOption) => {
    setActivePresetKey('custom');
    setQueryScores((prev) => ({ ...prev, ...opt.targetDelta }));
    setAttentionWeights((prev) => ({ ...prev, ...opt.boostWeights }));
    setCalibChosen((prev) => {
      const next = [...prev.slice(0, round.roundIndex - 1), opt.headline];
      return next;
    });
    if (round.roundIndex === 1) {
      setCalibRound(2);
    } else {
      setCalibRound('done');
    }
  };

  const handleBackCalibration = () => {
    if (calibRound === 2 || calibRound === 'done') {
      setCalibRound(1);
    }
  };

  const resetCalibration = () => {
    setCalibRound(1);
    setCalibChosen([]);
    setAttentionWeights({});
  };

  const copyHex = async (hex: string) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(hex);
        showToast(`已复制色值 ${hex}`);
      } else {
        showToast(`当前环境不支持剪贴板写入（${hex}）`);
      }
    } catch {
      showToast(`复制失败，请手动记录色值 ${hex}`);
    }
  };

  const copyCompiledAst = async () => {
    const fullText = `${compiledAst.compiledPrompt}\n\n${compiledAst.negativePrompt}`;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable');
      await navigator.clipboard.writeText(fullText);
      setPromptCopied(true);
      showToast('已复制完整 AST 结构化指令与负向护栏');
      setTimeout(() => setPromptCopied(false), 1600);
    } catch {
      showToast('剪贴板权限受限，请直接全选下方指令代码块复制');
    }
  };

  const handleLiveBackendVerify = async () => {
    if (!opticsAsset || !materialAsset || !lightingAsset) return;
    setLiveCompileLoading(true);
    try {
      const toBackendAsset = (a: CuratedShowcaseAsset) => ({
        asset_id: a.asset_id,
        title: a.title,
        subject_isolation: a.subject_isolation,
        style_spectrums: a.style_spectrums,
        granular_descriptors: a.granular_descriptors,
        compiler_primitives: a.compiler_primitives,
      });
      const resp = await fetch('/api/aethervault/compile-ast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subject_core: subjectCore,
          optics_asset: toBackendAsset(opticsAsset),
          material_asset: toBackendAsset(materialAsset),
          lighting_asset: toBackendAsset(lightingAsset),
          target_spectrums: queryScores,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setLiveCompileStatus({
        ok: true,
        message: `Live FastAPI 校验通过：独立源槽位 ${data.distinct_source_slots} 组，隔离词条冲突 ${data.conflicts_isolated_count} 项。`,
      });
    } catch (err) {
      setLiveCompileStatus({
        ok: false,
        message: `本地 Live FastAPI 引擎未连接（${err instanceof Error ? err.message : String(err)}）。当前页面已启用静态零延迟同构编译器完成前端编译。`,
      });
    } finally {
      setLiveCompileLoading(false);
    }
  };

  // Radar SVG geometry with intact 4-char labels
  const radarData = useMemo(() => {
    const cx = 150;
    const cy = 122;
    const maxR = 76;
    const n = ALL_AXIS_IDS.length;
    const axesPoints = ALL_AXIS_IDS.map((axisId, i) => {
      const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
      const xEnd = cx + maxR * Math.cos(angle);
      const yEnd = cy + maxR * Math.sin(angle);
      const lx = cx + (maxR + 30) * Math.cos(angle);
      const ly = cy + (maxR + 20) * Math.sin(angle);
      const val = queryScores[axisId] ?? 0;
      const norm = (val + 1) / 2;
      const rVal = maxR * (0.18 + 0.82 * norm);
      const px = cx + rVal * Math.cos(angle);
      const py = cy + rVal * Math.sin(angle);
      return {
        axisId,
        xEnd,
        yEnd,
        lx,
        ly,
        px,
        py,
        label: AXIS_INTACT_LABELS[axisId],
      };
    });
    const polygonPoints = axesPoints.map((p) => `${p.px.toFixed(1)},${p.py.toFixed(1)}`).join(' ');
    return { cx, cy, maxR, axesPoints, polygonPoints };
  }, [queryScores]);

  const activeRubric = activeAnchorAxis ? bundle.golden_anchors[activeAnchorAxis] ?? null : null;
  const observedCostPerImg =
    bundle.vlm_scoring_report?.cost_metrics.observed_online_cny_per_img ??
    bundle.cost_ledger.effective_cost_cny_per_img;

  const hasCustomFilters =
    fuzzyInput.trim().length > 0 ||
    scopeFilter !== 'all' ||
    originFilter !== 'all' ||
    domainFilter !== 'all' ||
    subCategoryFilter !== 'all' ||
    boardFilter !== 'all' ||
    onlyPersonalPrior ||
    activePresetKey === 'custom' ||
    Object.keys(attentionWeights).length > 0;

  return (
    <>
      <div className="space-y-12">
      {/* ACT I · ABOVE-THE-FOLD PROOF STAGE */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-7 lg:gap-9 pb-10 border-b border-border items-center">
        {/* Left 5 Cols · Architectural Thesis & Actions */}
        <div className="lg:col-span-5 space-y-6">
          <h1 className="font-display text-3xl sm:text-4xl lg:text-[42px] font-extrabold leading-[1.12] tracking-[-0.03em] text-foreground">
            把只可意会的审美直觉，编译为无冲突的空间语言
          </h1>
          <p className="text-[15px] text-muted-foreground leading-relaxed max-w-[46ch]">
            AetherVault 将主体语义与 8 维连续美学光谱正交解耦，基于您的个人 Pinterest 全图库审美画像扩展至 {bundle.total_assets} 件跨五门类锚定标本，实现亚毫秒重排与无冲突 AST 编译。
          </p>

          {/* 3 Tabular Proof Benchmarks separated by top/vertical Swiss hairlines */}
          <div className="grid grid-cols-3 border-y border-border divide-x divide-border">
            <div className="py-3.5 pr-3">
              <div className="mono text-lg sm:text-xl font-bold text-foreground tabular-nums">
                {rerankLatencyMs.toFixed(2)} ms
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">前端向量重排</div>
            </div>
            <div className="py-3.5 px-3">
              <div className="mono text-lg sm:text-xl font-bold text-foreground tabular-nums">
                {bundle.total_assets} 件
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">个人画像+扩展样本</div>
            </div>
            <div className="py-3.5 pl-3">
              <div className="mono text-lg sm:text-xl font-bold text-primary tabular-nums">
                ¥{observedCostPerImg.toFixed(4)}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">实测单图入库</div>
            </div>
          </div>

          {/* Primary Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setCalibOpen(true)}
              className="min-h-[44px] px-5 rounded-md shadow-sm bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-semibold inline-flex items-center gap-2 transition-colors"
            >
              <Sparkles className="w-4 h-4" strokeWidth={1.75} />
              <span>
                启动 2 轮视觉校准{calibRound === 'done' ? '（已收敛）' : ''}
              </span>
            </button>
            <a
              href="#specimen-gallery"
              onClick={() => setShow3DManifold(true)}
              className="min-h-[44px] px-5 rounded-md border border-border bg-card text-foreground hover:bg-secondary text-sm font-medium inline-flex items-center gap-2 transition-colors"
            >
              <Box className="w-4 h-4 text-primary" strokeWidth={1.75} />
              <span>探索 3D 美学流形 &amp; {bundle.total_assets} 标本</span>
            </a>
          </div>
        </div>

        {/* Right 7 Cols · Live Before/After Orthogonal AST Curtain */}
        <div className="lg:col-span-7 space-y-3">
          {activeHeroPair ? (
            <>
              <BeforeAfterSlider
                beforeSrc={activeHeroPair.naive_image_url}
                afterSrc={activeHeroPair.ast_image_url}
                beforeAlt={`${activeHeroPair.title_zh} 多图直喂对比`}
                afterAlt={`${activeHeroPair.title_zh} 正交 AST 编译对比`}
              />

              {/* Caption + Actions */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
                <div className="min-w-0">
                  <div className="text-sm font-bold text-foreground truncate">
                    {activeHeroPair.pair_id.toUpperCase()} · {activeHeroPair.title_zh}
                  </div>
                  <p className="text-xs text-muted-foreground truncate">
                    已隔离 {activeHeroPair.conflicts_isolated_count} 项词条冲突 · {activeHeroPair.subtitle_zh}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => handleLoadComparisonPair(activeHeroPair)}
                    className="min-h-[36px] px-3.5 rounded-md border border-border hover:border-primary/60 bg-card hover:bg-secondary/60 text-xs font-semibold text-foreground hover:text-primary transition-colors"
                  >
                    载入此组槽位
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCompareOpen(true);
                      trackShowcaseEvent('ast_compare_switch', { pair_id: activeHeroPair.pair_id });
                    }}
                    className="min-h-[36px] px-3.5 rounded-md border border-border hover:border-primary/60 bg-card hover:bg-secondary/60 text-xs font-semibold text-foreground transition-colors"
                  >
                    查看 3 源图与编译细节
                  </button>
                </div>
              </div>

              {/* Crisp 01-06 Index Bar */}
              <div
                role="group"
                aria-label="切换 6 组正交编译对比样本"
                className="grid grid-cols-6 rounded-md border border-border divide-x divide-border overflow-hidden"
              >
                {comparePairs.map((pair, idx) => {
                  const isActive = activeHeroPair.pair_id === pair.pair_id;
                  return (
                    <button
                      key={pair.pair_id}
                      type="button"
                      aria-pressed={isActive}
                      aria-label={`查看第 ${idx + 1} 组对比：${pair.title_zh}`}
                      title={pair.title_zh}
                      onClick={() => setHeroPairId(pair.pair_id)}
                      className={`min-h-[38px] text-xs mono font-semibold transition-colors ${
                        isActive
                          ? 'bg-accent text-primary border-b-2 border-b-primary'
                          : 'bg-card text-muted-foreground hover:bg-secondary/60 hover:text-foreground'
                      }`}
                    >
                      {String(idx + 1).padStart(2, '0')}
                    </button>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="aspect-[4/3] border border-border bg-secondary/60 flex items-center justify-center text-sm text-muted-foreground">
              对比样本数据加载中…
            </div>
          )}
        </div>
      </section>

      {/* ACT II · BORDERLESS 80-SPECIMEN GALLERY */}
      <section id="specimen-gallery" className="space-y-6">
        <div className="space-y-4 border-b border-border pb-5">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-2">
            <div>
              <h2 className="font-display text-2xl font-bold tracking-[-0.02em] text-foreground">
                跨门类高审美视觉标本库
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                点击任意影像放大检视全部 8 轴读数与材质描述；或直接点选下方三槽位进行无冲突组装。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                aria-pressed={show3DManifold}
                onClick={() => setShow3DManifold((v) => !v)}
                className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors ${
                  show3DManifold
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border bg-card text-foreground hover:bg-secondary'
                }`}
              >
                <Box className="w-3.5 h-3.5" />
                <span>{show3DManifold ? '隐藏 3D 美学流形' : '展开 Three.js 3D 流形'}</span>
              </button>
              <div className="text-xs text-muted-foreground mono tabular-nums">
                命中 {rankedAssets.length} / {bundle.total_assets} 件 · 排序耗时 {rerankLatencyMs.toFixed(2)} ms
              </div>
            </div>
          </div>

          {/* Control Row 1: Working Intent Search + Presets Dropdown + 8-Axis Drawer Button */}
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center gap-3">
            <form
              onSubmit={handleIntentSubmit}
              className="flex-1 flex items-center h-[42px] rounded-md border border-border focus-within:border-primary bg-card overflow-hidden"
            >
              <label htmlFor="intent-search" className="sr-only">
                输入空间或审美意图关键词
              </label>
              <div className="pl-3 flex items-center text-muted-foreground" aria-hidden="true">
                <Search className="w-4 h-4" />
              </div>
              <input
                id="intent-search"
                type="text"
                value={fuzzyInput}
                onChange={(e) => {
                  const val = e.target.value;
                  setFuzzyInput(val);
                  applyIntentQuery(val);
                }}
                placeholder={`输入审美意图或材质关键词（如：精密金属 留白 暖木 荒野），实时重排 ${bundle.total_assets} 件样本…`}
                className="flex-1 min-w-0 h-full px-3 text-sm text-foreground bg-transparent placeholder:text-muted-foreground focus:outline-none"
              />
              {fuzzyInput && (
                <button
                  type="button"
                  aria-label="清空意图关键词"
                  onClick={() => {
                    setFuzzyInput('');
                    setLiteralTermsFilter([]);
                    setIntentSummary(null);
                  }}
                  className="h-full px-2.5 text-muted-foreground hover:text-foreground flex items-center"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
              <button
                type="submit"
                className="h-full px-4 bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold shrink-0 transition-colors"
              >
                解析意图
              </button>
            </form>

            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <div className="flex items-center">
                <label htmlFor="preset-select" className="sr-only">
                  切换意图场景预设
                </label>
                <select
                  id="preset-select"
                  value={activePresetKey}
                  onChange={(e) => handlePresetChange(e.target.value)}
                  className="h-[42px] rounded-md px-3 border border-border hover:border-primary/60 bg-card text-xs font-medium text-foreground whitespace-nowrap"
                >
                  {activePresetKey === 'custom' && (
                    <option value="custom">当前：自定义调谐光谱</option>
                  )}
                  {PRESET_INTENTS.map((p) => (
                    <option key={p.key} value={p.key}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={() => setSpectrumDrawerOpen(true)}
                className="h-[42px] rounded-md px-4 border border-border hover:border-primary/60 bg-card hover:bg-secondary/60 text-xs font-semibold text-foreground inline-flex items-center gap-2 transition-colors"
              >
                <SlidersHorizontal className="w-3.5 h-3.5 text-primary" />
                <span>8 轴光谱调谐</span>
              </button>

              {hasCustomFilters && (
                <button
                  type="button"
                  onClick={handleResetAllFilters}
                  className="h-[42px] rounded-md px-3 border border-border hover:border-primary/60 bg-card text-xs font-medium text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>重置</span>
                </button>
              )}
            </div>
          </div>

          {/* Control Row 2: Origin Switcher (500 = 390 Pinterest + 110 Expansion) + Scope + Domain + Sub-Category */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5">
              {/* Origin Switcher */}
              <div
                role="group"
                aria-label="图库来源筛选"
                className="inline-flex h-9 rounded-md border border-border divide-x divide-border overflow-hidden"
              >
                {(
                  [
                    { key: 'all', label: `全部 (${originCounts.all})` },
                    { key: 'pinterest_personal', label: `我的 Pinterest 原图 (${originCounts.pinterest_personal})` },
                    { key: 'profile_expansion', label: `画像扩展新图 (${originCounts.profile_expansion})` },
                  ] as const
                ).map((item) => {
                  const active = originFilter === item.key;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      aria-pressed={active}
                      onClick={() => {
                        setOriginFilter(item.key);
                        setBoardFilter('all');
                        setVisibleLimit(24);
                      }}
                      className={`h-full px-3 text-xs font-medium transition-colors ${
                        active
                          ? 'bg-primary text-primary-foreground font-semibold'
                          : 'bg-card text-foreground hover:bg-secondary/60'
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>

              {/* 3-State Scope */}
              <div
                role="group"
                aria-label="跨界检索范围"
                className="inline-flex h-9 rounded-md border border-border divide-x divide-border overflow-hidden"
              >
                {(
                  [
                    { key: 'all', label: '全门类' },
                    { key: 'cross_domain', label: '跨界非建筑' },
                    { key: 'architecture_only', label: '仅建筑空间' },
                  ] as const
                ).map((item) => {
                  const active = scopeFilter === item.key;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      aria-pressed={active}
                      onClick={() => handleScopeChange(item.key)}
                      className={`h-full px-3 text-xs font-medium transition-colors ${
                        active
                          ? 'bg-foreground text-background'
                          : 'bg-card text-foreground hover:bg-secondary/60'
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>

              {scopeFilter !== 'architecture_only' && (
                <div className="flex items-center">
                  <label htmlFor="domain-filter-select" className="sr-only">
                    按门类细分筛选
                  </label>
                  <select
                    id="domain-filter-select"
                    value={domainFilter}
                    onChange={(e) => {
                      setDomainFilter(e.target.value as 'all' | AssetDomain);
                      setSubCategoryFilter('all');
                      setVisibleLimit(24);
                    }}
                    className="h-9 rounded-md px-3 border border-border hover:border-primary/60 bg-card text-xs font-medium text-foreground whitespace-nowrap"
                  >
                    {DOMAIN_OPTIONS.filter((opt) => {
                      if (scopeFilter === 'cross_domain' && opt.key === 'architecture') return false;
                      return true;
                    }).map((opt) => (
                      <option key={opt.key} value={opt.key}>
                        {opt.label} ({dynamicDomainCounts[opt.key] ?? 0})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {dynamicSubCategories.length > 0 && (
                <div className="flex items-center">
                  <label htmlFor="subcategory-filter-select" className="sr-only">
                    按细分类别筛选
                  </label>
                  <select
                    id="subcategory-filter-select"
                    value={subCategoryFilter}
                    onChange={(e) => {
                      setSubCategoryFilter(e.target.value);
                      setVisibleLimit(24);
                    }}
                    className="h-9 rounded-md px-3 border border-border hover:border-primary/60 bg-card text-xs font-medium text-foreground whitespace-nowrap"
                  >
                    <option value="all">全部细分类 ({dynamicSubCategories.length} 类)</option>
                    {dynamicSubCategories.map(([cat, cnt]) => (
                      <option key={cat} value={cat}>
                        {cat} ({cnt})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {intentSummary && (
              <div className="text-xs font-medium text-primary">
                {intentSummary}
              </div>
            )}
          </div>
        </div>

        {/* Personal Pinterest Aesthetic Profile Insights Card */}
        {bundle.aesthetic_profile && (
          <div className="rounded-xl border border-border bg-card p-4 sm:p-5 space-y-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-primary" aria-hidden="true" />
                  <h3 className="font-display text-sm font-bold text-foreground">
                    个人 Pinterest 全图库深度研究 · 审美画像（Personal Aesthetic Profile）
                  </h3>
                </div>
                <p className="text-xs text-muted-foreground">
                  已全量 VLM 研究 {bundle.aesthetic_profile.total_pinterest_analyzed} 张 Pinterest 原图 → 精选保留{' '}
                  <span className="mono font-semibold text-foreground">{bundle.aesthetic_profile.kept_pinterest_count}</span> 张核心美学样本 + 按画像跨源扩展{' '}
                  <span className="mono font-semibold text-primary">{bundle.aesthetic_profile.expansion_count}</span> 张新图 ={' '}
                  <span className="mono font-semibold text-foreground">{bundle.total_assets}</span> 件。
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleApplyPersonalProfile}
                  className="min-h-[34px] px-3.5 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold transition-colors"
                >
                  套用我的审美画像向量
                </button>
                <button
                  type="button"
                  onClick={() => setProfileExpanded((v) => !v)}
                  className="min-h-[34px] px-3 rounded-md border border-border hover:border-primary/60 text-xs font-medium text-foreground transition-colors"
                >
                  {profileExpanded ? '收起画像' : '展开画像'}
                </button>
              </div>
            </div>

            {profileExpanded && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-3 border-t border-border">
                {/* 8-Axis Weighted Signature */}
                <div className="lg:col-span-5 space-y-2">
                  <div className="text-xs font-semibold text-foreground">8 轴加权审美重心（核心倾向）</div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {ALL_AXIS_IDS.map((ax) => {
                      const val = bundle.aesthetic_profile?.axis_signature[ax]?.weighted_mean ?? 0;
                      const strong = Math.abs(val) >= 0.2;
                      return (
                        <div
                          key={ax}
                          className={`rounded-md px-2.5 py-2 border ${
                            strong ? 'border-primary/50 bg-accent/40' : 'border-border bg-secondary/40'
                          }`}
                        >
                          <div className="text-[11px] text-muted-foreground">{AXIS_INTACT_LABELS[ax]}</div>
                          <div
                            className={`mono text-xs font-bold tabular-nums mt-0.5 ${
                              strong ? 'text-primary' : 'text-foreground'
                            }`}
                          >
                            {val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Dominant Color Clusters */}
                <div className="lg:col-span-3 space-y-2">
                  <div className="text-xs font-semibold text-foreground">高频建筑色彩基底（点击复制）</div>
                  <div className="grid grid-cols-5 gap-1.5">
                    {bundle.aesthetic_profile.dominant_color_clusters.slice(0, 10).map((c) => (
                      <button
                        key={c.hex}
                        type="button"
                        onClick={() => copyHex(c.hex)}
                        title={`点击复制 ${c.hex}（出现 ${c.count} 次）`}
                        className="group rounded-sm overflow-hidden border border-border hover:border-primary/60 transition-colors text-center"
                      >
                        <div className="h-7 w-full" style={{ backgroundColor: c.hex }} />
                        <div className="px-0.5 py-0.5 mono text-[10px] text-muted-foreground">
                          {c.hex}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Top Pinterest Boards Quick Filter */}
                <div className="lg:col-span-4 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-foreground">主要 Pinterest 画板快捷筛选</span>
                    {boardFilter !== 'all' && (
                      <button
                        type="button"
                        onClick={() => setBoardFilter('all')}
                        className="text-primary hover:underline"
                      >
                        清除画板 ({boardFilter})
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {bundle.aesthetic_profile.top_boards.slice(0, 10).map((b) => {
                      const active = boardFilter === b.board;
                      return (
                        <button
                          key={b.board}
                          type="button"
                          aria-pressed={active}
                          onClick={() => {
                            setBoardFilter(active ? 'all' : b.board);
                            if (!active) setOriginFilter('pinterest_personal');
                            setVisibleLimit(24);
                          }}
                          className={`rounded-md px-2 py-1 text-[11px] border transition-colors ${
                            active
                              ? 'border-primary bg-primary text-primary-foreground font-semibold'
                              : 'border-border bg-secondary/50 text-foreground hover:border-primary/60'
                          }`}
                        >
                          {b.board} <span className="mono opacity-75">({b.count})</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Interactive Three.js 3D Aesthetic Spectrum Manifold */}
        {show3DManifold && rankedAssets.length > 0 && (
          <AetherVaultManifold3D
            rankedAssets={rankedAssets.map((r) => ({
              asset: r.asset,
              matchPct: r.matchScore,
              distance: r.dist,
            }))}
            axes={bundle.axes}
            queryScores={queryScores}
            onSelectAsset={(asset) => setLightboxAsset(asset)}
            onAssignSlot={(slot, assetId) => {
              setSelectedSlots((prev) => ({ ...prev, [slot]: assetId }));
              showToast(`已从 3D 流形将样本填入「${slot === 'optics' ? '光学镜头' : slot === 'material' ? '材质构造' : '光影氛围'}」槽位`);
            }}
          />
        )}

        {/* Borderless 4-Column Monograph Photography Grid */}
        {rankedAssets.length === 0 ? (
          <div className="rounded-xl py-16 px-6 border border-border bg-secondary/60 text-center space-y-4">
            <div className="text-base font-bold text-foreground">未找到符合当前条件组合的视觉样本</div>
            <p className="text-xs text-muted-foreground">
              请放宽跨界范围、关键词过滤或个人审美先验限制后重新检索。
            </p>
            <button
              type="button"
              onClick={handleResetAllFilters}
              className="min-h-[40px] px-5 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold transition-colors"
            >
              重置全部筛选与光谱
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-10">
            {rankedAssets.slice(0, visibleLimit).map(({ asset, matchScore }) => {
              const isOpt = selectedSlots.optics === asset.asset_id;
              const isMat = selectedSlots.material === asset.asset_id;
              const isLit = selectedSlots.lighting === asset.asset_id;

              return (
                <article key={asset.asset_id} className="flex flex-col">
                  {/* Unobstructed Edge-to-Edge Plate — ZERO image badges */}
                  <button
                    type="button"
                    onClick={() => setLightboxAsset(asset)}
                    aria-label={`放大检视 ${asset.title}`}
                    className="group block w-full aspect-[4/3] rounded-md overflow-hidden border border-border/60 bg-secondary/60 text-left"
                  >
                    <img
                      src={asset.image_url}
                      alt={asset.title}
                      loading="lazy"
                      className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
                    />
                  </button>

                  {/* Below-Frame Swiss Metadata & Controls */}
                  <div className="pt-3 space-y-2.5">
                    <div className="flex items-baseline justify-between gap-2">
                      <h3 className="text-sm font-semibold text-foreground truncate" title={asset.title}>
                        {asset.title}
                      </h3>
                      <span className="mono text-sm font-semibold text-primary tabular-nums shrink-0">
                        {matchScore}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span className="truncate" title={asset.sub_category ?? asset.subject_isolation.domain_label}>
                        {asset.sub_category ?? asset.subject_isolation.domain_label}
                      </span>
                      {asset.source_origin === 'pinterest_personal' ? (
                        <span className="font-medium text-foreground shrink-0 truncate max-w-[110px]" title={asset.board_name}>
                          Pin · {asset.board_name ?? '原图'}
                        </span>
                      ) : asset.source_origin === 'profile_expansion' ? (
                        <span className="font-medium text-primary shrink-0">画像扩展</span>
                      ) : asset.subject_isolation.is_personal_prior ? (
                        <span className="font-medium text-foreground shrink-0">个人先验</span>
                      ) : null}
                    </div>

                    {/* 5-Color Continuous OKLab Palette Bar (click to copy) */}
                    <div
                      role="group"
                      aria-label={`${asset.title} 主色板`}
                      className="flex h-7 w-full rounded-sm border border-border overflow-hidden"
                    >
                      {asset.granular_descriptors.color_palette.slice(0, 5).map((hex) => (
                        <button
                          key={hex}
                          type="button"
                          onClick={() => copyHex(hex)}
                          title={`点击复制 ${hex}`}
                          aria-label={`复制主色 ${hex}`}
                          style={{ backgroundColor: hex }}
                          className="flex-1 h-full hover:opacity-85 transition-opacity"
                        />
                      ))}
                    </div>

                    {/* Crisp 3-Slot Orthogonal Assignment Strip */}
                    <div className="grid grid-cols-3 rounded-md border border-border divide-x divide-border overflow-hidden">
                      {(
                        [
                          { slot: 'optics' as const, label: '镜头', active: isOpt },
                          { slot: 'material' as const, label: '材质', active: isMat },
                          { slot: 'lighting' as const, label: '光影', active: isLit },
                        ] as const
                      ).map((btn) => (
                        <button
                          key={btn.slot}
                          type="button"
                          aria-pressed={btn.active}
                          aria-label={`将 ${asset.title} 设为${btn.label}参考`}
                          onClick={() => handleAssignSlot(btn.slot, asset.asset_id)}
                          className={`min-h-[36px] text-xs font-medium transition-colors ${
                            btn.active
                              ? 'bg-primary text-primary-foreground font-semibold'
                              : 'bg-card text-foreground hover:bg-secondary/60'
                          }`}
                        >
                          {btn.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {visibleLimit < rankedAssets.length && (
          <div className="pt-2 flex justify-center">
            <button
              type="button"
              onClick={() => setVisibleLimit((v) => v + 24)}
              className="min-h-[44px] px-8 rounded-md border border-border hover:border-primary/60 bg-card hover:bg-secondary/60 text-xs font-semibold text-foreground transition-colors"
            >
              展开更多样张（剩余 {rankedAssets.length - visibleLimit} 件）
            </button>
          </div>
        )}
      </section>
      </div>

      {/* ACT III · RIGHT SLIDE-OVER 8-AXIS SPECTRUM TUNING DRAWER */}
      {spectrumDrawerOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="spectrum-drawer-title"
          onClick={() => setSpectrumDrawerOpen(false)}
          className="fixed inset-0 z-[60] bg-black/65 backdrop-blur-[2px] flex justify-end"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-card border-l border-border shadow-2xl w-full max-w-lg h-full flex flex-col overflow-hidden"
          >
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 id="spectrum-drawer-title" className="font-display text-base font-bold text-foreground">
                  8 轴正交光谱调谐器
                </h2>
                <p className="text-xs text-muted-foreground">
                  实时更新 {bundle.total_assets} 件跨界图库排序（当前耗时 {rerankLatencyMs.toFixed(2)} ms）
                </p>
              </div>
              <button
                type="button"
                aria-label="关闭光谱调谐器"
                onClick={() => setSpectrumDrawerOpen(false)}
                className="w-10 h-10 rounded-md border border-border hover:border-primary/60 flex items-center justify-center text-foreground transition-colors"
              >
                <X className="w-4 h-4" strokeWidth={1.75} />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-6 flex-1">
              {/* Compact 8-Axis Radar with intact 4-char labels */}
              <div className="rounded-lg bg-secondary/60 border border-border p-4 flex flex-col items-center">
                <svg viewBox="0 0 300 245" className="w-full max-w-[300px] h-auto select-none">
                  {[0.25, 0.55, 0.85, 1.0].map((rFactor) => (
                    <circle
                      key={rFactor}
                      cx={radarData.cx}
                      cy={radarData.cy}
                      r={radarData.maxR * rFactor}
                      fill="none"
                      stroke="hsl(var(--border))"
                      strokeWidth="1"
                      strokeDasharray={rFactor === 0.55 ? '3 3' : undefined}
                    />
                  ))}
                  {radarData.axesPoints.map((pt) => (
                    <line
                      key={pt.axisId}
                      x1={radarData.cx}
                      y1={radarData.cy}
                      x2={pt.xEnd}
                      y2={pt.yEnd}
                      stroke="hsl(var(--border))"
                      strokeWidth="1"
                    />
                  ))}
                  <polygon
                    points={radarData.polygonPoints}
                    fill="hsl(var(--primary) / 0.16)"
                    stroke="hsl(var(--primary))"
                    strokeWidth="1.75"
                  />
                  {radarData.axesPoints.map((pt) => (
                    <g key={pt.axisId}>
                      <circle cx={pt.px} cy={pt.py} r="3.5" fill="hsl(var(--primary))" />
                      <text
                        x={pt.lx}
                        y={pt.ly}
                        fill="hsl(var(--foreground))"
                        fontSize="11.5"
                        fontWeight="600"
                        textAnchor="middle"
                        dominantBaseline="middle"
                      >
                        {pt.label}
                      </text>
                    </g>
                  ))}
                </svg>
                <p className="text-xs text-muted-foreground">
                  点击下方各轴「5 点标尺」可对照客观视觉基准定标
                </p>
              </div>

              {/* 3 Grouped Slider Sections */}
              {SLIDER_GROUPS.map((group) => (
                <div key={group.title} className="space-y-4 pt-4 border-t border-border">
                  <h3 className="text-xs font-bold text-foreground">{group.title}</h3>
                  {group.axes.map((axisId) => {
                    const meta = axesMetaById[axisId];
                    const val = queryScores[axisId] ?? 0;
                    const label = AXIS_INTACT_LABELS[axisId];
                    return (
                      <div key={axisId} className="space-y-1.5">
                        <div className="flex items-center justify-between gap-2 text-xs">
                          <label htmlFor={`slider-${axisId}`} className="font-semibold text-foreground">
                            {label}
                          </label>
                          <div className="flex items-center gap-2.5">
                            <span className="mono font-semibold text-primary tabular-nums">
                              {val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2)}
                            </span>
                            <button
                              type="button"
                              aria-label={`查看 ${label} 5 点黄金锚点标尺`}
                              onClick={() => setActiveAnchorAxis(axisId)}
                              className="min-h-[30px] rounded-md px-2.5 border border-border hover:border-primary text-xs font-medium text-foreground hover:text-primary transition-colors"
                            >
                              5 点标尺
                            </button>
                          </div>
                        </div>
                        <input
                          id={`slider-${axisId}`}
                          type="range"
                          min={-1}
                          max={1}
                          step={0.05}
                          value={val}
                          onChange={(e) => {
                            const next = parseFloat(e.target.value);
                            setActivePresetKey('custom');
                            setQueryScores((prev) => ({ ...prev, [axisId]: next }));
                            trackShowcaseEvent('rerank_slider', { axis: axisId, value: next });
                          }}
                          className="w-full"
                        />
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>{meta?.neg_label ?? '-1.0'}</span>
                          <span>{meta?.pos_label ?? '+1.0'}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>

            <div className="p-4 border-t border-border bg-secondary/60 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={handleResetAllFilters}
                className="min-h-[40px] rounded-md px-4 border border-border bg-card hover:border-primary/60 text-xs font-semibold text-foreground transition-colors"
              >
                重置默认光谱
              </button>
              <button
                type="button"
                onClick={() => {
                  setSpectrumDrawerOpen(false);
                  setCalibOpen(true);
                }}
                className="min-h-[40px] rounded-md px-4 bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold transition-colors"
              >
                启动 2 轮视觉校准
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ACT IV · PERSISTENT BOTTOM SPECIMEN DOCK */}
      <div
        role="region"
        aria-label="三槽位 AST 编译托盘"
        className="fixed bottom-0 inset-x-0 z-30 border-t border-border bg-card/95 backdrop-blur-md shadow-[0_-2px_10px_rgba(0,0,0,0.04)]"
      >
        <div className="max-w-7xl mx-auto px-3 sm:px-6 h-14 sm:h-16 flex items-center justify-between gap-2 sm:gap-3">
          <div className="flex items-center gap-1.5 sm:gap-4 min-w-0 overflow-x-auto no-scrollbar">
            {(
              [
                { slot: 'optics', label: '镜头', short: '镜', asset: opticsAsset },
                { slot: 'material', label: '材质', short: '材', asset: materialAsset },
                { slot: 'lighting', label: '光影', short: '光', asset: lightingAsset },
              ] as const
            ).map((item) => (
              <button
                key={item.slot}
                type="button"
                onClick={() => item.asset && setLightboxAsset(item.asset)}
                title={item.asset ? `点击检视 ${item.label}：${item.asset.title}` : item.label}
                className="flex items-center gap-1.5 sm:gap-2 min-w-0 shrink-0 sm:max-w-[200px] rounded-md border border-border hover:border-primary pr-2 sm:pr-2.5 bg-card overflow-hidden transition-colors"
              >
                <div className="w-7 h-6 sm:w-9 sm:h-7 bg-secondary/60 shrink-0 overflow-hidden">
                  {item.asset && (
                    <img
                      src={item.asset.image_url}
                      alt={item.asset.title}
                      className="w-full h-full object-cover"
                    />
                  )}
                </div>
                <div className="text-left min-w-0">
                  <span className="text-xs font-semibold text-primary sm:hidden">{item.short}</span>
                  <div className="hidden sm:block text-xs text-foreground font-medium truncate">
                    <span className="text-muted-foreground mr-1">{item.label}:</span>
                    {item.asset?.title ?? item.slot}
                  </div>
                </div>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <span className="hidden md:inline text-xs mono text-muted-foreground tabular-nums">
              已隔离 {compiledAst.conflictsIsolatedCount} 项冲突
            </span>
            <button
              type="button"
              onClick={() => setCompilerOpen(true)}
              className="min-h-[40px] px-3 sm:px-4 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold inline-flex items-center gap-1.5 sm:gap-2 transition-colors whitespace-nowrap"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>展开 AST 编译器</span>
            </button>
          </div>
        </div>
      </div>

      {/* AST COMPILER EXPANDABLE SHEET */}
      {compilerOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="ast-sheet-title"
          onClick={() => setCompilerOpen(false)}
          className="fixed inset-0 z-50 bg-black/65 backdrop-blur-[2px] flex justify-end"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-card border-l border-border shadow-2xl w-full max-w-2xl h-full flex flex-col overflow-hidden"
          >
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 id="ast-sheet-title" className="font-display text-lg font-bold text-foreground">
                  正交特征 AST 混音编译器
                </h2>
                <p className="text-xs text-muted-foreground">
                  独立抽取镜头、材质、光影三层特征，屏蔽非选中维度词条泄漏
                </p>
              </div>
              <button
                type="button"
                aria-label="关闭 AST 编译器"
                onClick={() => setCompilerOpen(false)}
                className="w-10 h-10 rounded-md border border-border hover:border-primary/60 flex items-center justify-center text-foreground transition-colors"
              >
                <X className="w-4 h-4" strokeWidth={1.75} />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-5 flex-1 text-xs">
              {/* Subject Core Input */}
              <div className="space-y-1.5">
                <label htmlFor="ast-subject-core" className="block font-semibold text-foreground">
                  目标空间主体描述 (Subject Core)
                </label>
                <input
                  id="ast-subject-core"
                  type="text"
                  value={subjectCore}
                  onChange={(e) => setSubjectCore(e.target.value)}
                  className="w-full min-h-[40px] px-3 rounded-md bg-card border border-border focus:border-primary text-xs text-foreground focus:outline-none"
                />
              </div>

              {/* 3 Isolated Slots */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { label: '镜头透视槽位', asset: opticsAsset, desc: opticsAsset?.granular_descriptors.optics_camera },
                  { label: '材质构筑槽位', asset: materialAsset, desc: materialAsset?.granular_descriptors.material_stack },
                  { label: '光影氛围槽位', asset: lightingAsset, desc: lightingAsset?.granular_descriptors.lighting_rig },
                ].map((s) => (
                  <div key={s.label} className="rounded-lg border border-border p-3 space-y-2">
                    <div className="font-semibold text-primary">{s.label}</div>
                    {s.asset && (
                      <div className="aspect-[4/3] rounded-md bg-secondary/60 overflow-hidden">
                        <img src={s.asset.image_url} alt={s.asset.title} className="w-full h-full object-cover" />
                      </div>
                    )}
                    <div className="font-semibold text-foreground truncate">{s.asset?.title}</div>
                    <p className="text-muted-foreground leading-relaxed line-clamp-3">{s.desc}</p>
                  </div>
                ))}
              </div>

              {/* Compiled Prompt Output */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-foreground">
                    编译输出（已隔离 {compiledAst.conflictsIsolatedCount} 项作用域冲突）
                  </span>
                  <button
                    type="button"
                    onClick={copyCompiledAst}
                    className="min-h-[34px] rounded-md px-3 border border-border hover:border-primary/60 inline-flex items-center gap-1.5 font-semibold text-foreground transition-colors"
                  >
                    {promptCopied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-teal-ok" />
                        <span>已复制</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>复制指令</span>
                      </>
                    )}
                  </button>
                </div>
                <pre className="p-3.5 rounded-lg bg-secondary/60 border border-border mono text-xs text-foreground whitespace-pre-wrap leading-relaxed">
                  {compiledAst.compiledPrompt}
                </pre>
                <div className="p-3 rounded-lg bg-secondary/60 border border-border mono text-xs text-destructive">
                  {compiledAst.negativePrompt}
                </div>
              </div>

              {/* Live FastAPI Verification Status */}
              {liveCompileStatus && (
                <div
                  role="status"
                  className={`p-3.5 rounded-lg border text-xs leading-relaxed ${
                    liveCompileStatus.ok
                      ? 'border-teal-ok bg-card text-teal-ok'
                      : 'border-destructive bg-card text-destructive'
                  }`}
                >
                  {liveCompileStatus.message}
                </div>
              )}
            </div>

            <div className="p-4 border-t border-border bg-secondary/60 flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => {
                  setCompilerOpen(false);
                  setCompareOpen(true);
                }}
                className="min-h-[40px] rounded-md px-4 border border-border hover:border-primary/60 bg-card hover:bg-secondary/60 text-xs font-semibold text-foreground transition-colors"
              >
                对照 6 组多图污染实证
              </button>
              <button
                type="button"
                disabled={liveCompileLoading}
                onClick={handleLiveBackendVerify}
                className={`min-h-[40px] rounded-md px-4 text-xs font-semibold transition-colors ${
                  isLiveEngine
                    ? 'bg-teal-ok hover:opacity-90 text-white dark:text-slate-950'
                    : 'bg-primary hover:bg-primary/90 text-primary-foreground'
                }`}
              >
                {liveCompileLoading
                  ? '正在校验后端接口…'
                  : isLiveEngine
                    ? '执行 Live FastAPI 实时校验'
                    : '探测 Live FastAPI 校验接口'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Feedback Banner */}
      {toastMessage && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-20 right-4 sm:right-6 z-40 rounded-md shadow-lg px-4 py-2.5 bg-foreground text-background text-xs font-medium border border-border"
        >
          {toastMessage}
        </div>
      )}

      {/* Modals & Drawers */}
      <SpecimenLightbox
        asset={lightboxAsset}
        matchScore={lightboxAsset ? matchByAssetId[lightboxAsset.asset_id] : undefined}
        axesMetaById={axesMetaById}
        selectedSlots={selectedSlots}
        onAssignSlot={handleAssignSlot}
        onCopyHex={copyHex}
        onClose={() => setLightboxAsset(null)}
      />

      <VisualCalibrationPanel
        isOpen={calibOpen}
        currentRound={calibRound}
        chosenLabels={calibChosen}
        assetsById={assetsById}
        onSelectOption={handleSelectCalibration}
        onBackRound={handleBackCalibration}
        onReset={resetCalibration}
        onClose={() => setCalibOpen(false)}
      />

      <GoldenAnchorDrawer
        rubric={activeRubric}
        currentValue={activeAnchorAxis ? queryScores[activeAnchorAxis] ?? 0 : 0}
        assetsById={assetsById}
        onApplyAnchorLevel={(axisId, level) => {
          setActivePresetKey('custom');
          setQueryScores((prev) => ({ ...prev, [axisId]: level }));
          showToast(`已对齐「${AXIS_INTACT_LABELS[axisId]}」至标尺档位 ${level > 0 ? `+${level}` : level}`);
        }}
        onClose={() => setActiveAnchorAxis(null)}
      />

      <AstComparisonDrawer
        isOpen={compareOpen}
        initialPairId={activeHeroPair?.pair_id}
        onClose={() => setCompareOpen(false)}
        comparisonBundle={comparisonBundle}
        assetsById={assetsById}
        currentSlots={selectedSlots}
        currentCompiledPrompt={compiledAst.compiledPrompt}
        currentNegativePrompt={compiledAst.negativePrompt}
        currentConflictsCount={compiledAst.conflictsIsolatedCount}
        onLoadSlotsIntoMixer={handleLoadComparisonPair}
      />
    </>
  );
};
