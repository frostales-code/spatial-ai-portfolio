import type { SpectrumAxisId } from './salienceMetric';
import type { CuratedShowcaseAsset } from '../types/aethervault';

interface IntentKeywordRule {
  id: string;
  label: string;
  patterns: string[];
  scores: Partial<Record<SpectrumAxisId, number>>;
  weights: Partial<Record<SpectrumAxisId, number>>;
}

const INTENT_RULES: readonly IntentKeywordRule[] = [
  {
    id: 'wilderness_patina',
    label: '粗粝风化',
    patterns: ['荒野', '苍凉', '粗粝', '风化', '耐候', '矿石', '沧桑', '肌理', 'rust', 'patina', 'weathered', 'brutalist', 'basalt'],
    scores: { surface_entropy: 0.55, tectonic_honesty: 0.65, chromatic_tension: -0.35 },
    weights: { surface_entropy: 1.7, tectonic_honesty: 1.4 },
  },
  {
    id: 'precision_industrial',
    label: '精密机械',
    patterns: ['精密', '机械', '徕卡', '阳极', '金属', '工业', '仪器', '公差', '数控', 'cnc', 'leica', 'machined', 'metal', 'precision', 'anodized'],
    scores: { surface_entropy: -0.6, tectonic_honesty: 0.85, geometric_order: 0.85 },
    weights: { surface_entropy: 1.8, tectonic_honesty: 1.7, geometric_order: 1.5 },
  },
  {
    id: 'zen_whitespace',
    label: '留白静谧',
    patterns: ['留白', '静谧', '东方', '茶', '器物', '克制', '呼吸', '禅', '侘寂', 'minimal', 'quiet', 'zen', 'tea', 'ceramic', 'void'],
    scores: { spatial_density: -0.75, chromatic_tension: -0.65, geometric_order: 0.45 },
    weights: { spatial_density: 1.8, chromatic_tension: 1.5 },
  },
  {
    id: 'warm_intimate',
    label: '温润暖调',
    patterns: ['暖', '温润', '木', '黄昏', '亲密', '夕阳', '陶土', '暖光', 'warm', 'wood', 'timber', 'dusk', 'intimate'],
    scores: { thermal_mood: 0.75, lighting_drama: 0.25 },
    weights: { thermal_mood: 1.8, lighting_drama: 1.3 },
  },
  {
    id: 'cool_lab',
    label: '冷峻漫射',
    patterns: ['冷', '冷峻', '实验室', '极地', '阴天', '漫射', '银盐', '冷灰', 'cool', 'cold', 'lab', 'overcast', 'diffuse', 'polar'],
    scores: { thermal_mood: -0.7, lighting_drama: -0.5, chromatic_tension: -0.55 },
    weights: { thermal_mood: 1.7, lighting_drama: 1.5 },
  },
  {
    id: 'dramatic_light',
    label: '戏剧光影',
    patterns: ['明暗', '强光', '戏剧', '光影', '反差', '剪影', '束光', 'chiaroscuro', 'dramatic', 'shadow', 'contrast'],
    scores: { lighting_drama: 0.75, spatial_density: 0.1 },
    weights: { lighting_drama: 1.9 },
  },
  {
    id: 'chromatic_signal',
    label: '几何撞色',
    patterns: ['包豪斯', '撞色', '高饱和', '烈橙', '构成', '信号', '秩序', '几何', '模数', 'bauhaus', 'signal', 'cobalt', 'orange', 'grid'],
    scores: { chromatic_tension: 0.75, geometric_order: 0.85, reality_abstraction: 0.35 },
    weights: { chromatic_tension: 1.7, geometric_order: 1.6 },
  },
  {
    id: 'abstract_graphic',
    label: '抽象构成',
    patterns: ['抽象', '平面', '插画', '版画', '图形', '波普', 'graphic', 'abstract', 'poster', 'illustration'],
    scores: { reality_abstraction: 0.8, tectonic_honesty: -0.25 },
    weights: { reality_abstraction: 1.9 },
  },
  {
    id: 'obsidian_dark',
    label: '黑曜暗调',
    patterns: ['黑曜石', '暗调', '哑光黑', '深邃', 'obsidian', 'matte', 'dark'],
    scores: { lighting_drama: 0.4, chromatic_tension: 0.25, thermal_mood: -0.35 },
    weights: { lighting_drama: 1.4, thermal_mood: 1.3 },
  },
  {
    id: 'tectonic_glazing',
    label: '高技建构',
    patterns: ['高技', '张拉', '玻璃', '钢结构', '结构外露', '明缝', '混凝土', 'concrete', 'glass', 'steel', 'tectonic', 'pavilion'],
    scores: { tectonic_honesty: 0.85, spatial_density: -0.3, geometric_order: 0.75 },
    weights: { tectonic_honesty: 1.8, geometric_order: 1.4 },
  },
];

export interface ParsedIntentResult {
  raw: string;
  matchedLabels: string[];
  targetScores: Partial<Record<SpectrumAxisId, number>>;
  boostWeights: Partial<Record<SpectrumAxisId, number>>;
  literalTerms: string[];
  hasSemanticHits: boolean;
}

export function parseFuzzyIntent(rawInput: string): ParsedIntentResult {
  const trimmed = rawInput.trim();
  if (!trimmed) {
    return {
      raw: '',
      matchedLabels: [],
      targetScores: {},
      boostWeights: {},
      literalTerms: [],
      hasSemanticHits: false,
    };
  }

  const lower = trimmed.toLowerCase();
  const matchedLabels: string[] = [];
  const scoreAccumulator: Partial<Record<SpectrumAxisId, number[]>> = {};
  const weightAccumulator: Partial<Record<SpectrumAxisId, number>> = {};

  for (const rule of INTENT_RULES) {
    const hit = rule.patterns.some((p) => lower.includes(p.toLowerCase()));
    if (!hit) continue;
    matchedLabels.push(rule.label);
    for (const [axis, val] of Object.entries(rule.scores) as Array<[SpectrumAxisId, number]>) {
      if (!scoreAccumulator[axis]) scoreAccumulator[axis] = [];
      scoreAccumulator[axis]!.push(val);
    }
    for (const [axis, w] of Object.entries(rule.weights) as Array<[SpectrumAxisId, number]>) {
      weightAccumulator[axis] = Math.max(weightAccumulator[axis] ?? 1, w);
    }
  }

  const targetScores: Partial<Record<SpectrumAxisId, number>> = {};
  for (const [axis, vals] of Object.entries(scoreAccumulator) as Array<[SpectrumAxisId, number[]]>) {
    const avg = vals.reduce((sum, v) => sum + v, 0) / vals.length;
    targetScores[axis] = Math.max(-1, Math.min(1, Math.round(avg * 20) / 20));
  }

  const literalTerms = lower
    .split(/[\s,，、/+|]+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 2);

  return {
    raw: trimmed,
    matchedLabels,
    targetScores,
    boostWeights: weightAccumulator,
    literalTerms,
    hasSemanticHits: matchedLabels.length > 0,
  };
}

export function matchesAssetText(asset: CuratedShowcaseAsset, terms: string[]): boolean {
  if (terms.length === 0) return true;
  const haystack = [
    asset.asset_id,
    asset.title,
    asset.title_en ?? '',
    asset.subject_isolation.domain_label,
    asset.subject_isolation.primary_subject,
    asset.granular_descriptors.material_stack,
    asset.granular_descriptors.optics_camera,
    asset.granular_descriptors.lighting_rig,
    ...asset.compiler_primitives.positive_tokens,
  ]
    .join(' ')
    .toLowerCase();

  return terms.some((term) => haystack.includes(term));
}
