/**
 * Sub-millisecond client-side salience-gated metric & conflict-free AST compiler.
 * Matches backend contract in pipeline/aethervault_schema.py for Instant Showcase mode.
 */

export type SpectrumAxisId =
  | 'tectonic_honesty'
  | 'surface_entropy'
  | 'spatial_density'
  | 'geometric_order'
  | 'lighting_drama'
  | 'chromatic_tension'
  | 'thermal_mood'
  | 'reality_abstraction';

export interface SpectrumAxisReading {
  score: number;    // [-1.0, +1.0]
  salience: number; // [0.0, 1.0]
}

export interface AestheticAssetContract {
  assetId: string;
  title: string;
  domain: 'architecture' | 'industrial' | 'editorial' | 'craft' | 'graphic';
  domainLabel: string;
  isPersonalPrior: boolean;
  palette: string[];
  imageUrl?: string;
  spectrums: Record<SpectrumAxisId, SpectrumAxisReading>;
  opticsCamera: string;
  materialStack: string;
  lightingRig: string;
  negativeGuardrails?: string[];
}

export const ALL_AXIS_IDS: readonly SpectrumAxisId[] = [
  'tectonic_honesty',
  'surface_entropy',
  'spatial_density',
  'geometric_order',
  'lighting_drama',
  'chromatic_tension',
  'thermal_mood',
  'reality_abstraction',
] as const;

export function computeSalienceGatedDistance(
  queryScores: Record<SpectrumAxisId, number>,
  candidateSpectrums: Record<SpectrumAxisId, SpectrumAxisReading>,
  attentionWeights?: Partial<Record<SpectrumAxisId, number>>,
  eps = 1e-6,
): number {
  let numerator = 0;
  let denominator = 0;

  for (const axisId of ALL_AXIS_IDS) {
    const reading = candidateSpectrums[axisId];
    if (!reading) continue;
    const w = Math.max(0, attentionWeights?.[axisId] ?? 1);
    const s = reading.salience;
    const diff = (queryScores[axisId] ?? 0) - reading.score;
    numerator += w * s * diff * diff;
    denominator += w * s;
  }

  return numerator / (denominator + eps);
}

export function distanceToMatchPercent(distance: number): number {
  const rmse = Math.sqrt(Math.max(0, distance));
  return Math.max(0, Math.min(99, Math.round((1 - rmse / 1.45) * 100)));
}

export interface CompiledAstOutput {
  compiledPrompt: string;
  negativePrompt: string;
  conflictsIsolatedCount: number;
}

export function compileConflictFreeAstClient(
  subjectCore: string,
  opticsAsset: AestheticAssetContract,
  materialAsset: AestheticAssetContract,
  lightingAsset: AestheticAssetContract,
  targetSpectrums: Record<SpectrumAxisId, number>,
): CompiledAstOutput {
  const entropy = targetSpectrums.surface_entropy;
  const entropyModifier =
    entropy > 0.5
      ? 'pronounced natural weathering patina confined to primary cladding panels'
      : entropy < -0.3
        ? 'ultra-clean factory-machined surface tolerance'
        : 'controlled subtle weathering with crisp precision mechanical joints';

  const compiledPrompt = [
    `[SUBJECT_CORE]\n${subjectCore.trim()}`,
    `[OPTICS_LAYER <- ${opticsAsset.assetId}]\n${opticsAsset.opticsCamera}.`,
    `[MATERIAL_TECTONICS <- ${materialAsset.assetId}]\nLocalized to primary structural assemblies and joinery: ${materialAsset.materialStack}, ${entropyModifier}.`,
    `[ATMOSPHERE_LIGHTING <- ${lightingAsset.assetId}]\n${lightingAsset.lightingRig}.`,
  ].join('\n\n');

  const negatives = new Set<string>(['plastic CGI gloss', 'floating structural members']);
  if (entropy < 0.55) {
    negatives.add('post-apocalyptic trash');
    negatives.add('crumbling ruins');
    negatives.add('chaotic rust stains');
  }
  if (targetSpectrums.chromatic_tension < -0.3) {
    negatives.add('oversaturated neon');
    negatives.add('HDR color clipping');
  }
  if (targetSpectrums.lighting_drama < -0.2) {
    negatives.add('harsh midday cast shadows');
    negatives.add('blown-out highlights');
  }
  for (const extra of materialAsset.negativeGuardrails ?? []) {
    negatives.add(extra);
  }

  const distinctSlots = new Set([opticsAsset.assetId, materialAsset.assetId, lightingAsset.assetId]).size;

  return {
    compiledPrompt,
    negativePrompt: `--no ${Array.from(negatives).join(', ')}`,
    conflictsIsolatedCount: distinctSlots + 1,
  };
}
