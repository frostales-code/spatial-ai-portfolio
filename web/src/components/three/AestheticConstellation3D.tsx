'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import {
  Compass,
  Eye,
  GitBranch,
  Layers,
  Maximize2,
  Palette,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Wand2,
  X,
} from 'lucide-react';
import type { AssetArchetype, CuratedShowcaseAsset } from '../../types/aethervault';

export type ConstellationMode = 'gravity' | 'terrain' | 'oklab';
export type TerrainElevationAxis = 'contrast' | 'warmth' | 'tectonic';

interface AestheticConstellation3DProps {
  assets: CuratedShowcaseAsset[];
  fusionIds: string[];
  queryMap3d?: { x: number; y: number; z: number } | null;
  semanticScores?: Record<string, number> | null;
  onSelectAsset: (asset: CuratedShowcaseAsset) => void;
  onToggleFusion: (assetId: string) => void;
  onBatchSelectFusion: (assetIds: string[]) => void;
}

interface DomainMeta {
  id: AssetArchetype;
  label: string;
  color: string;
  angle: number;
}

const DOMAIN_LIST: DomainMeta[] = [
  { id: 'interior', label: '室内设计', color: '#E2B887', angle: 0.12 },
  { id: 'architecture', label: '建筑设计', color: '#94A3B8', angle: 0.91 },
  { id: 'graphic_typography', label: '平面与字体', color: '#F472B6', angle: 1.70 },
  { id: 'landscape', label: '景观空间', color: '#4ADE80', angle: 2.48 },
  { id: 'illustration_character', label: '插画与角色', color: '#C084FC', angle: 3.27 },
  { id: 'craft', label: '器物工艺', color: '#F59E0B', angle: 4.05 },
  { id: 'industrial', label: '工业设计', color: '#38BDF8', angle: 4.84 },
  { id: 'fashion_photography', label: '时尚摄影', color: '#FB7185', angle: 5.62 },
];

const DOMAIN_MAP: Record<string, DomainMeta> = Object.fromEntries(
  DOMAIN_LIST.map((d) => [d.id, d])
);

const FLOOR_Y = -4.2;

/** Convert hex string (#RRGGBB) to Bjorn Ottosson OKLab (L, a, b, C, h). */
function hexToOklab(hex: string): { L: number; a: number; b: number; C: number; h: number } {
  const clean = (hex || '#888888').replace('#', '').trim();
  const full =
    clean.length === 3
      ? clean
          .split('')
          .map((c) => c + c)
          .join('')
      : clean.padEnd(6, '8').slice(0, 6);
  const r8 = parseInt(full.slice(0, 2), 16) || 128;
  const g8 = parseInt(full.slice(2, 4), 16) || 128;
  const b8 = parseInt(full.slice(4, 6), 16) || 128;

  const toLinear = (v: number) => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const r = toLinear(r8);
  const g = toLinear(g8);
  const b = toLinear(b8);

  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);

  const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
  const A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  const C = Math.sqrt(A * A + B * B);
  const h = Math.atan2(B, A);
  return { L: Math.max(0, Math.min(1, L)), a: A, b: B, C, h };
}

/** Luminous Obsidian dot-matrix shader: tiny hot pinpoint core + silky dual-layer feathered bloom. */
const OBSIDIAN_DOT_VERT = /* glsl */ `
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aAlpha;
  attribute float aRing;

  varying vec3 vColor;
  varying float vAlpha;
  varying float vRing;

  uniform float uPixelRatio;

  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    float dist = max(4.0, -mvPosition.z);

    // Atmospheric depth attenuation (near nodes crisp & luminous, far nodes softly veiled)
    float depthFade = clamp(1.24 - (dist - 10.0) / 36.0, 0.24, 1.0);

    vColor = aColor;
    vAlpha = aAlpha * depthFade;
    vRing = aRing;

    // Larger quad room so feathered Gaussian bloom never clips at quad edges, while core stays tiny
    float ptSize = aSize * uPixelRatio * (22.0 / dist);
    gl_PointSize = clamp(ptSize, 7.0 * uPixelRatio, 46.0 * uPixelRatio);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const OBSIDIAN_DOT_FRAG = /* glsl */ `
  varying vec3 vColor;
  varying float vAlpha;
  varying float vRing;

  void main() {
    vec2 uv = gl_PointCoord - vec2(0.5);
    float d = length(uv);
    if (d > 0.5) discard;

    // Smooth boundary fade-out to zero at d=0.5 so bloom never shows square quad edges
    float edgeMask = 1.0 - smoothstep(0.36, 0.5, d);

    // 1. Delicate hot pinpoint core (stays small & Obsidian-fine, never a big marble)
    float coreR = vRing > 1.5 ? 0.145 : (vRing > 0.5 ? 0.115 : 0.13);
    float core = 1.0 - smoothstep(coreR * 0.45, coreR * 1.45, d);

    // 2. Dual-layer feathered Gaussian glow (inner luminous corona + wide silky feather)
    float innerGlow = exp(-d * d * (vRing > 1.5 ? 22.0 : 34.0)) * (vRing > 1.5 ? 0.85 : 0.62);
    float outerFeather = exp(-d * d * (vRing > 1.5 ? 7.5 : 10.5)) * (vRing > 1.5 ? 0.48 : 0.28);

    // 3. Optional feathered orbital halo ring (outer contrast satellites & hero nodes)
    float ring = 0.0;
    if (vRing > 0.5) {
      float ringPos = vRing > 1.5 ? 0.265 : 0.245;
      float ringWidth = vRing > 1.5 ? 0.045 : 0.036;
      ring = exp(-pow((d - ringPos) / ringWidth, 2.0)) * (vRing > 1.5 ? 0.72 : 0.44);
    }

    float intensity = clamp(core + innerGlow + outerFeather + ring, 0.0, 1.0) * edgeMask;
    float alpha = intensity * vAlpha;
    if (alpha < 0.008) discard;

    // Luminous incandescent white-hot center fading smoothly into rich saturated domain color
    float hotCenter = clamp(core * 0.52 + innerGlow * 0.18, 0.0, 0.75);
    vec3 col = mix(vColor, vec3(1.0), hotCenter * (vRing > 1.5 ? 1.15 : 0.88));
    gl_FragColor = vec4(col, alpha);
  }
`;

/** Build a hairline circle loop on the horizontal XZ plane at height y. */
function createRingLine(radius: number, y: number, color: number, opacity: number, segments = 120): THREE.LineLoop {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i < segments; i++) {
    const a = (i / segments) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * radius, y, Math.sin(a) * radius));
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity });
  return new THREE.LineLoop(geo, mat);
}

/** Build minimalist dashed-feeling radial tick guides + center crosshair (no bulky wireframe ball!). */
function createOrbitalGuides(): THREE.Group {
  const g = new THREE.Group();
  g.add(createRingLine(3.6, 0, 0x94a3b8, 0.09));
  g.add(createRingLine(6.3, 0, 0xe2b887, 0.2)); // Core Gravity Boundary
  g.add(createRingLine(8.9, 0, 0xfbbf24, 0.09));
  g.add(createRingLine(11.3, 0, 0xfbbf24, 0.16)); // Outer Contrast Orbit

  // Subtle 8-sector meridian hairlines
  const mVerts: number[] = [];
  for (const dom of DOMAIN_LIST) {
    const c = Math.cos(dom.angle);
    const s = Math.sin(dom.angle);
    mVerts.push(c * 1.4, 0, s * 1.4, c * 11.3, 0, s * 11.3);
  }
  const mGeo = new THREE.BufferGeometry();
  mGeo.setAttribute('position', new THREE.Float32BufferAttribute(mVerts, 3));
  g.add(new THREE.LineSegments(mGeo, new THREE.LineBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.1 })));

  // Razor-thin minimalist center origin crosshair (replaces bulky wireframe sphere)
  const crossVerts = [
    -0.55, 0, 0, 0.55, 0, 0,
    0, 0, -0.55, 0, 0, 0.55,
    0, -0.35, 0, 0, 0.35, 0,
  ];
  const cGeo = new THREE.BufferGeometry();
  cGeo.setAttribute('position', new THREE.Float32BufferAttribute(crossVerts, 3));
  g.add(new THREE.LineSegments(cGeo, new THREE.LineBasicMaterial({ color: 0xe2b887, transparent: true, opacity: 0.45 })));
  return g;
}

/** Build architectural floor grid for Semantic Terrain mode. */
function createFloorGrid(halfSize: number, step: number, y: number): THREE.LineSegments {
  const verts: number[] = [];
  for (let v = -halfSize; v <= halfSize + 0.001; v += step) {
    verts.push(-halfSize, y, v, halfSize, y, v);
    verts.push(v, y, -halfSize, v, y, halfSize);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  const mat = new THREE.LineBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.14 });
  return new THREE.LineSegments(geo, mat);
}

/** Compute real Dijkstra shortest visual path over the Top-K cosine neighbor graph. */
function computeDijkstraBridge(
  assets: CuratedShowcaseAsset[],
  startId: string | null,
  endId: string | null
): CuratedShowcaseAsset[] {
  if (!startId || !endId || startId === endId || assets.length < 2) return [];
  const byId = new Map<string, CuratedShowcaseAsset>();
  const adj = new Map<string, Array<{ to: string; cost: number }>>();

  for (const a of assets) {
    byId.set(a.asset_id, a);
    adj.set(a.asset_id, []);
  }
  if (!byId.has(startId) || !byId.has(endId)) return [];

  for (const a of assets) {
    const list = adj.get(a.asset_id)!;
    for (const nb of a.similar_ids ?? []) {
      if (!byId.has(nb.asset_id)) continue;
      const w = Math.pow(Math.max(0.02, 1.0 - nb.score), 1.45) + 0.015;
      list.push({ to: nb.asset_id, cost: w });
      adj.get(nb.asset_id)!.push({ to: a.asset_id, cost: w });
    }
  }

  const dist = new Map<string, number>();
  const prev = new Map<string, string>();
  const visited = new Set<string>();
  dist.set(startId, 0);

  while (visited.size < byId.size) {
    let bestId: string | null = null;
    let bestDist = Infinity;
    for (const [id, d] of dist.entries()) {
      if (!visited.has(id) && d < bestDist) {
        bestDist = d;
        bestId = id;
      }
    }
    if (!bestId || bestId === endId) break;
    visited.add(bestId);
    for (const edge of adj.get(bestId) ?? []) {
      if (visited.has(edge.to)) continue;
      const nd = bestDist + edge.cost;
      if (nd < (dist.get(edge.to) ?? Infinity)) {
        dist.set(edge.to, nd);
        prev.set(edge.to, bestId);
      }
    }
  }

  if (!prev.has(endId)) return [];
  const path: CuratedShowcaseAsset[] = [];
  let cur: string | undefined = endId;
  let guard = 0;
  while (cur && guard < 18) {
    const item = byId.get(cur);
    if (item) path.push(item);
    if (cur === startId) break;
    cur = prev.get(cur);
    guard += 1;
  }
  path.reverse();
  if (path.length > 6) {
    const sampled: CuratedShowcaseAsset[] = [path[0]];
    for (let i = 1; i < 5; i++) {
      const idx = Math.round((i / 5) * (path.length - 1));
      if (sampled[sampled.length - 1].asset_id !== path[idx].asset_id) {
        sampled.push(path[idx]);
      }
    }
    if (sampled[sampled.length - 1].asset_id !== path[path.length - 1].asset_id) {
      sampled.push(path[path.length - 1]);
    }
    return sampled;
  }
  return path;
}

interface ComputedNode {
  asset: CuratedShowcaseAsset;
  index: number;
  domain: DomainMeta;
  isContrast: boolean;
  primaryHex: string;
  oklab: { L: number; a: number; b: number; C: number; h: number };
  gravityPos: THREE.Vector3;
  terrainXZ: { x: number; z: number };
  terrainY: Record<TerrainElevationAxis, number>;
  oklabPos: THREE.Vector3;
  domainColor: THREE.Color;
  paletteColor: THREE.Color;
}

export const AestheticConstellation3D: React.FC<AestheticConstellation3DProps> = ({
  assets,
  fusionIds,
  queryMap3d,
  semanticScores,
  onSelectAsset,
  onToggleFusion,
  onBatchSelectFusion,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [mode, setMode] = useState<ConstellationMode>('gravity');
  const [terrainAxis, setTerrainAxis] = useState<TerrainElevationAxis>('contrast');
  const [showBridge, setShowBridge] = useState<boolean>(true);
  const [showWebEdges, setShowWebEdges] = useState<boolean>(true);
  const [autoRotate, setAutoRotate] = useState<boolean>(true);
  const [focusDomain, setFocusDomain] = useState<AssetArchetype | 'all'>('all');
  const [bridgePairIndex, setBridgePairIndex] = useState<number>(0);
  const [customBridgeA, setCustomBridgeA] = useState<string | null>(null);
  const [customBridgeB, setCustomBridgeB] = useState<string | null>(null);

  const [hoveredState, setHoveredState] = useState<{
    asset: CuratedShowcaseAsset;
    x: number;
    y: number;
  } | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);

  // Precompute all 3 real spatial coordinate sets (< 3ms for 600 items)
  const nodes = useMemo<ComputedNode[]>(() => {
    return assets.map((asset, index) => {
      const dom = DOMAIN_MAP[asset.archetype ?? 'interior'] ?? DOMAIN_LIST[0];
      const resonance = asset.aesthetic_critique?.resonance_mode ?? asset.rag_doc?.resonance_mode;
      const isContrast =
        asset.source_origin === 'profile_expansion' || resonance === 'contrast_inspiration';

      const primaryHex =
        asset.granular_descriptors?.color_palette?.[0] ??
        asset.rag_doc?.palette?.[0] ??
        dom.color;
      const ok = hexToOklab(primaryHex);

      // 1. Real 3D Semantic Vector + Core Gravity Orbital Radius
      const m3 = asset.map_3d ?? {
        x: ((asset.map_2d?.x ?? 0.5) - 0.5) * 1.8,
        y: (ok.L - 0.5) * 1.1,
        z: ((asset.map_2d?.y ?? 0.5) - 0.5) * 1.8,
      };
      const cdist = typeof asset.core_distance === 'number' ? asset.core_distance : isContrast ? 0.72 : 0.3;

      const rawAngle = Math.atan2(m3.z, m3.x);
      const vx = Math.cos(rawAngle) * 0.55 + Math.cos(dom.angle) * 0.45;
      const vz = Math.sin(rawAngle) * 0.55 + Math.sin(dom.angle) * 0.45;
      const theta = Math.atan2(vz, vx);

      // Inner Core Gravity Well [2.0 .. 5.9] vs Outer Contrast Orbit [7.1 .. 11.2]
      const radius = isContrast ? 7.1 + cdist * 4.1 : 2.0 + cdist * 3.9;
      const yGrav = m3.y * (isContrast ? 4.3 : 3.1);
      const gravityPos = new THREE.Vector3(Math.cos(theta) * radius, yGrav, Math.sin(theta) * radius);

      // 2. Semantic Terrain (X-Z real t-SNE floor + selectable Y elevation)
      const tx = ((asset.map_2d?.x ?? 0.5) - 0.5) * 16.8;
      const tz = ((asset.map_2d?.y ?? 0.5) - 0.5) * 16.8;
      const thermalRaw = asset.style_spectrums?.thermal_mood?.score ?? 0;
      const warmthNorm = Math.max(0, Math.min(1, 0.5 + thermalRaw * 0.35 + (ok.a + ok.b) * 1.1));
      const tectonicRaw = asset.style_spectrums?.tectonic_honesty?.score ?? 0;
      const tectonicNorm = Math.max(0, Math.min(1, (tectonicRaw + 1) * 0.5));

      const terrainY: Record<TerrainElevationAxis, number> = {
        contrast: FLOOR_Y + 0.65 + cdist * 7.8,
        warmth: FLOOR_Y + 0.65 + warmthNorm * 7.8,
        tectonic: FLOOR_Y + 0.65 + tectonicNorm * 7.8,
      };

      // 3. Real OKLab 3D Color Cylinder Sculpture
      const chromaR = 0.8 + Math.min(1, Math.pow(ok.C / 0.24, 0.72)) * 8.9;
      const lightY = (ok.L - 0.5) * 9.8;
      const oklabPos = new THREE.Vector3(Math.cos(ok.h) * chromaR, lightY, Math.sin(ok.h) * chromaR);

      return {
        asset,
        index,
        domain: dom,
        isContrast,
        primaryHex,
        oklab: ok,
        gravityPos,
        terrainXZ: { x: tx, z: tz },
        terrainY,
        oklabPos,
        domainColor: new THREE.Color(dom.color),
        paletteColor: new THREE.Color(primaryHex),
      };
    });
  }, [assets]);

  const nodeById = useMemo(() => {
    const m = new Map<string, ComputedNode>();
    for (const n of nodes) m.set(n.asset.asset_id, n);
    return m;
  }, [nodes]);

  // Precompute Obsidian-style sparse semantic graph edges (Top-2 undirected cosine links per node)
  const webEdgePairs = useMemo<Array<[number, number]>>(() => {
    const seen = new Set<string>();
    const pairs: Array<[number, number]> = [];
    for (const n of nodes) {
      const nbs = (n.asset.similar_ids ?? []).slice(0, 2);
      for (const nb of nbs) {
        const target = nodeById.get(nb.asset_id);
        if (!target || target.index === n.index) continue;
        const a = Math.min(n.index, target.index);
        const b = Math.max(n.index, target.index);
        const key = `${a}:${b}`;
        if (!seen.has(key)) {
          seen.add(key);
          pairs.push([a, b]);
        }
      }
    }
    return pairs;
  }, [nodes, nodeById]);

  const domainCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of nodes) {
      counts[n.domain.id] = (counts[n.domain.id] ?? 0) + 1;
    }
    return counts;
  }, [nodes]);

  const autoBridgePairs = useMemo<Array<[string, string]>>(() => {
    const byDom = new Map<AssetArchetype, CuratedShowcaseAsset[]>();
    for (const n of nodes) {
      const arr = byDom.get(n.domain.id) ?? [];
      arr.push(n.asset);
      byDom.set(n.domain.id, arr);
    }
    const desired: Array<[AssetArchetype, AssetArchetype]> = [
      ['graphic_typography', 'interior'],
      ['illustration_character', 'architecture'],
      ['fashion_photography', 'craft'],
      ['industrial', 'landscape'],
      ['craft', 'graphic_typography'],
      ['architecture', 'fashion_photography'],
    ];
    const pairs: Array<[string, string]> = [];
    for (const [dA, dB] of desired) {
      const listA = byDom.get(dA);
      const listB = byDom.get(dB);
      if (listA?.length && listB?.length) {
        pairs.push([listA[Math.min(2, listA.length - 1)].asset_id, listB[Math.min(3, listB.length - 1)].asset_id]);
      }
    }
    if (pairs.length === 0 && nodes.length >= 2) {
      pairs.push([nodes[0].asset.asset_id, nodes[nodes.length - 1].asset.asset_id]);
    }
    return pairs;
  }, [nodes]);

  const activeBridgeEndpoints = useMemo<[string | null, string | null]>(() => {
    if (customBridgeA && customBridgeB && nodeById.has(customBridgeA) && nodeById.has(customBridgeB)) {
      return [customBridgeA, customBridgeB];
    }
    if (autoBridgePairs.length === 0) return [null, null];
    return autoBridgePairs[bridgePairIndex % autoBridgePairs.length];
  }, [customBridgeA, customBridgeB, nodeById, autoBridgePairs, bridgePairIndex]);

  const bridgePath = useMemo<CuratedShowcaseAsset[]>(() => {
    if (!showBridge) return [];
    const [aId, bId] = activeBridgeEndpoints;
    return computeDijkstraBridge(assets, aId, bId);
  }, [assets, showBridge, activeBridgeEndpoints]);

  const bridgeIdSet = useMemo(() => new Set(bridgePath.map((a) => a.asset_id)), [bridgePath]);
  const fusionIdSet = useMemo(() => new Set(fusionIds), [fusionIds]);

  const selectedAsset = useMemo(
    () => (selectedAssetId ? nodeById.get(selectedAssetId)?.asset ?? null : null),
    [selectedAssetId, nodeById]
  );

  // Focus neighborhood set for Obsidian spotlight effect (hovered/selected node + Top-6 neighbors)
  const focusNeighborSet = useMemo(() => {
    const activeId = hoveredState?.asset.asset_id ?? selectedAssetId;
    if (!activeId) return null;
    const node = nodeById.get(activeId);
    if (!node) return null;
    const set = new Set<string>([activeId]);
    for (const nb of (node.asset.similar_ids ?? []).slice(0, 6)) {
      set.add(nb.asset_id);
    }
    return set;
  }, [hoveredState, selectedAssetId, nodeById]);

  const stateRef = useRef({
    mode,
    terrainAxis,
    showBridge,
    showWebEdges,
    autoRotate,
    focusDomain,
    selectedAssetId,
    hoveredAssetId: null as string | null,
    focusNeighborSet,
    fusionIdSet,
    bridgePath,
    bridgeIdSet,
    semanticScores: semanticScores ?? null,
    queryMap3d: queryMap3d ?? null,
  });

  stateRef.current = {
    mode,
    terrainAxis,
    showBridge,
    showWebEdges,
    autoRotate,
    focusDomain,
    selectedAssetId,
    hoveredAssetId: hoveredState?.asset.asset_id ?? null,
    focusNeighborSet,
    fusionIdSet,
    bridgePath,
    bridgeIdSet,
    semanticScores: semanticScores ?? null,
    queryMap3d: queryMap3d ?? null,
  };

  const cameraOrbitRef = useRef({
    theta: 0.68,
    phi: 1.15,
    radius: 23.5,
    targetTheta: 0.68,
    targetPhi: 1.15,
    targetRadius: 23.5,
    lookAt: new THREE.Vector3(0, 0, 0),
    targetLookAt: new THREE.Vector3(0, 0, 0),
  });

  const morphTriggerRef = useRef<() => void>(() => {});

  const handleDomainFocus = useCallback(
    (domId: AssetArchetype | 'all') => {
      const next = domId === focusDomain ? 'all' : domId;
      setFocusDomain(next);
      const cam = cameraOrbitRef.current;
      if (next === 'all') {
        cam.targetLookAt.set(0, 0, 0);
        cam.targetRadius = 23.5;
        cam.targetPhi = mode === 'terrain' ? 1.0 : 1.15;
      } else {
        const subset = nodes.filter((n) => n.domain.id === next);
        if (subset.length > 0) {
          const cx = subset.reduce((s, n) => s + n.gravityPos.x, 0) / subset.length;
          const cy = subset.reduce((s, n) => s + n.gravityPos.y, 0) / subset.length;
          const cz = subset.reduce((s, n) => s + n.gravityPos.z, 0) / subset.length;
          const angle = Math.atan2(cz, cx);
          cam.targetTheta = Math.PI / 2 - angle;
          cam.targetPhi = mode === 'terrain' ? 1.0 : 1.12;
          cam.targetRadius = 17.5;
          cam.targetLookAt.set(cx * 0.25, cy * 0.2, cz * 0.25);
          setAutoRotate(false);
        }
      }
    },
    [focusDomain, mode, nodes]
  );

  const handleModeChange = useCallback((nextMode: ConstellationMode) => {
    setMode(nextMode);
    const cam = cameraOrbitRef.current;
    if (nextMode === 'terrain') {
      cam.targetPhi = 0.98;
      cam.targetRadius = 24.5;
    } else if (nextMode === 'oklab') {
      cam.targetPhi = 1.24;
      cam.targetRadius = 22.0;
    } else {
      cam.targetPhi = 1.15;
      cam.targetRadius = 23.5;
    }
    cam.targetLookAt.set(0, 0, 0);
  }, []);

  const handleResetView = useCallback(() => {
    setFocusDomain('all');
    setSelectedAssetId(null);
    const cam = cameraOrbitRef.current;
    cam.targetTheta = 0.68;
    cam.targetPhi = mode === 'terrain' ? 0.98 : 1.15;
    cam.targetRadius = 23.5;
    cam.targetLookAt.set(0, 0, 0);
    setAutoRotate(true);
  }, [mode]);

  const handleCycleBridge = useCallback(() => {
    setCustomBridgeA(null);
    setCustomBridgeB(null);
    setBridgePairIndex((i) => i + 1);
    setShowBridge(true);
  }, []);

  const handleFuseBridge = useCallback(() => {
    if (bridgePath.length < 2) return;
    const picks: string[] = [bridgePath[0].asset_id];
    if (bridgePath.length >= 3) {
      picks.push(bridgePath[Math.floor(bridgePath.length / 2)].asset_id);
    }
    picks.push(bridgePath[bridgePath.length - 1].asset_id);
    onBatchSelectFusion(Array.from(new Set(picks)).slice(0, 3));
  }, [bridgePath, onBatchSelectFusion]);

  useEffect(() => {
    morphTriggerRef.current();
  }, [mode, terrainAxis]);

  // Main Three.js Obsidian Flat Dot-Matrix + Semantic Graph Lifecycle
  useEffect(() => {
    const container = containerRef.current;
    if (!container || nodes.length === 0) return;

    let stageW = container.clientWidth || 960;
    let stageH = container.clientHeight || 640;
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(44, stageW / stageH, 0.1, 160);
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(stageW, stageH);
    renderer.setClearColor(0x090b10, 0);
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // --- 1. Mode-Specific Minimalist Architectural Guides ---
    const gravityGuides = createOrbitalGuides();
    scene.add(gravityGuides);

    const terrainGuides = new THREE.Group();
    terrainGuides.add(createFloorGrid(10, 2, FLOOR_Y));
    terrainGuides.visible = false;
    scene.add(terrainGuides);

    const oklabGuides = new THREE.Group();
    oklabGuides.add(createRingLine(9.8, -4.9, 0x64748b, 0.14));
    oklabGuides.add(createRingLine(9.8, 0, 0x38bdf8, 0.2));
    oklabGuides.add(createRingLine(9.8, 4.9, 0xf8fafc, 0.18));
    const spineGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, -5.3, 0),
      new THREE.Vector3(0, 5.3, 0),
    ]);
    oklabGuides.add(
      new THREE.Line(spineGeo, new THREE.LineBasicMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.35 }))
    );
    oklabGuides.visible = false;
    scene.add(oklabGuides);

    // --- 2. Obsidian Semantic Web Edges (delicate hairline graph links) ---
    const webEdgeCount = webEdgePairs.length;
    const webPositions = new Float32Array(webEdgeCount * 2 * 3);
    const webColors = new Float32Array(webEdgeCount * 2 * 3);
    const webGeo = new THREE.BufferGeometry();
    webGeo.setAttribute('position', new THREE.BufferAttribute(webPositions, 3));
    webGeo.setAttribute('color', new THREE.BufferAttribute(webColors, 3));
    const webMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.16,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const webLines = new THREE.LineSegments(webGeo, webMat);
    scene.add(webLines);

    // --- 3. Terrain Vertical Elevation Stalks ---
    const count = nodes.length;
    const stalkPositions = new Float32Array(count * 2 * 3);
    const stalkColors = new Float32Array(count * 2 * 3);
    const stalkGeo = new THREE.BufferGeometry();
    stalkGeo.setAttribute('position', new THREE.BufferAttribute(stalkPositions, 3));
    stalkGeo.setAttribute('color', new THREE.BufferAttribute(stalkColors, 3));
    const stalkMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.26,
      depthWrite: false,
    });
    const terrainStalks = new THREE.LineSegments(stalkGeo, stalkMat);
    terrainStalks.visible = false;
    scene.add(terrainStalks);

    // --- 4. Focused Neighbor Filaments (Obsidian bright spotlight links on hover/click) ---
    const neighborMaxLines = 8;
    const neighborPositions = new Float32Array(neighborMaxLines * 2 * 3);
    const neighborGeo = new THREE.BufferGeometry();
    neighborGeo.setAttribute('position', new THREE.BufferAttribute(neighborPositions, 3));
    const neighborMat = new THREE.LineBasicMaterial({
      color: 0xf1f5f9,
      transparent: true,
      opacity: 0.78,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const neighborLines = new THREE.LineSegments(neighborGeo, neighborMat);
    neighborLines.visible = false;
    scene.add(neighborLines);

    // --- 5. A -> B Cross-Domain Inspiration Bridge Line + Subtle Traveling Pinpoint ---
    const bridgeGeo = new THREE.BufferGeometry();
    const bridgeMat = new THREE.LineBasicMaterial({
      color: 0xfde047,
      transparent: true,
      opacity: 0.92,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const bridgeLine = new THREE.Line(bridgeGeo, bridgeMat);
    bridgeLine.visible = false;
    scene.add(bridgeLine);

    // Feathered luminous comet pulse along A -> B bridge
    const pulseGeo = new THREE.BufferGeometry();
    pulseGeo.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0], 3));
    pulseGeo.setAttribute('aColor', new THREE.Float32BufferAttribute([1.0, 0.92, 0.45], 3));
    pulseGeo.setAttribute('aSize', new THREE.Float32BufferAttribute([34.0], 1));
    pulseGeo.setAttribute('aAlpha', new THREE.Float32BufferAttribute([1.0], 1));
    pulseGeo.setAttribute('aRing', new THREE.Float32BufferAttribute([2.0], 1));
    const pulseMat = new THREE.ShaderMaterial({
      vertexShader: OBSIDIAN_DOT_VERT,
      fragmentShader: OBSIDIAN_DOT_FRAG,
      uniforms: { uPixelRatio: { value: pixelRatio } },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const bridgePulse = new THREE.Points(pulseGeo, pulseMat);
    bridgePulse.visible = false;
    scene.add(bridgePulse);

    // --- 6. Semantic Search Beacon Crosshair + Top-6 Laser Rays ---
    const beaconCross = [
      -0.45, 0, 0, 0.45, 0, 0,
      0, -0.45, 0, 0, 0.45, 0,
      0, 0, -0.45, 0, 0, 0.45,
    ];
    const beaconGeo = new THREE.BufferGeometry();
    beaconGeo.setAttribute('position', new THREE.Float32BufferAttribute(beaconCross, 3));
    const beaconMat = new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.9 });
    const searchBeacon = new THREE.LineSegments(beaconGeo, beaconMat);
    searchBeacon.visible = false;
    scene.add(searchBeacon);

    const searchRayPositions = new Float32Array(6 * 2 * 3);
    const searchRayGeo = new THREE.BufferGeometry();
    searchRayGeo.setAttribute('position', new THREE.BufferAttribute(searchRayPositions, 3));
    const searchRayMat = new THREE.LineBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.65,
      depthWrite: false,
    });
    const searchRays = new THREE.LineSegments(searchRayGeo, searchRayMat);
    searchRays.visible = false;
    scene.add(searchRays);

    // --- 7. Main Obsidian Anti-Aliased Flat Dot-Matrix Nodes (THREE.Points + Custom GLSL) ---
    const ptPositions = new Float32Array(count * 3);
    const ptColors = new Float32Array(count * 3);
    const ptSizes = new Float32Array(count);
    const ptAlphas = new Float32Array(count);
    const ptRings = new Float32Array(count);

    const ptGeo = new THREE.BufferGeometry();
    ptGeo.setAttribute('position', new THREE.BufferAttribute(ptPositions, 3));
    ptGeo.setAttribute('aColor', new THREE.BufferAttribute(ptColors, 3));
    ptGeo.setAttribute('aSize', new THREE.BufferAttribute(ptSizes, 1));
    ptGeo.setAttribute('aAlpha', new THREE.BufferAttribute(ptAlphas, 1));
    ptGeo.setAttribute('aRing', new THREE.BufferAttribute(ptRings, 1));

    const ptMat = new THREE.ShaderMaterial({
      vertexShader: OBSIDIAN_DOT_VERT,
      fragmentShader: OBSIDIAN_DOT_FRAG,
      uniforms: { uPixelRatio: { value: pixelRatio } },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const starPoints = new THREE.Points(ptGeo, ptMat);
    scene.add(starPoints);

    // --- 8. Morph Buffers ---
    const curPos = nodes.map((n) => n.gravityPos.clone());
    const fromPos = nodes.map((n) => n.gravityPos.clone());
    const toPos = nodes.map((n) => n.gravityPos.clone());
    let morphProgress = 1.0;

    const getTargetForNode = (n: ComputedNode): THREE.Vector3 => {
      const st = stateRef.current;
      if (st.mode === 'gravity') return n.gravityPos;
      if (st.mode === 'terrain') {
        return new THREE.Vector3(n.terrainXZ.x, n.terrainY[st.terrainAxis], n.terrainXZ.z);
      }
      return n.oklabPos;
    };

    morphTriggerRef.current = () => {
      for (let i = 0; i < count; i++) {
        fromPos[i].copy(curPos[i]);
        toPos[i].copy(getTargetForNode(nodes[i]));
      }
      morphProgress = 0;
    };

    morphTriggerRef.current();
    morphProgress = 1.0;
    for (let i = 0; i < count; i++) curPos[i].copy(toPos[i]);

    // --- 9. Ultra-Accurate Screen-Space Hit Testing for Tiny Obsidian Dots (< 0.15ms) ---
    const projScratch = new THREE.Vector3();
    const pickNodeAtScreen = (px: number, py: number): number => {
      let bestIdx = -1;
      let bestScore = Infinity;
      const hitRadiusPx = 13;
      const st = stateRef.current;

      for (let i = 0; i < count; i++) {
        const n = nodes[i];
        if (st.focusDomain !== 'all' && n.domain.id !== st.focusDomain && !st.bridgeIdSet.has(n.asset.asset_id)) {
          continue;
        }
        projScratch.copy(curPos[i]).project(camera);
        if (projScratch.z < -1 || projScratch.z > 1) continue;
        const sx = (projScratch.x * 0.5 + 0.5) * stageW;
        const sy = (-projScratch.y * 0.5 + 0.5) * stageH;
        const d = Math.hypot(sx - px, sy - py);
        if (d < hitRadiusPx) {
          // Prefer closer-to-camera nodes when overlapping
          const score = d + projScratch.z * 2.5;
          if (score < bestScore) {
            bestScore = score;
            bestIdx = i;
          }
        }
      }
      return bestIdx;
    };

    let isDragging = false;
    let dragMoved = false;
    let lastClientX = 0;
    let lastClientY = 0;
    let lastHoverIdx = -1;

    const onPointerDown = (e: PointerEvent) => {
      isDragging = true;
      dragMoved = false;
      lastClientX = e.clientX;
      lastClientY = e.clientY;
      setAutoRotate(false);
    };

    const onPointerMove = (e: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      const relX = e.clientX - rect.left;
      const relY = e.clientY - rect.top;

      if (isDragging) {
        const dx = e.clientX - lastClientX;
        const dy = e.clientY - lastClientY;
        if (Math.abs(dx) + Math.abs(dy) > 2) dragMoved = true;
        cameraOrbitRef.current.targetTheta -= dx * 0.0068;
        cameraOrbitRef.current.targetPhi = Math.max(
          0.22,
          Math.min(Math.PI - 0.22, cameraOrbitRef.current.targetPhi - dy * 0.0058)
        );
        lastClientX = e.clientX;
        lastClientY = e.clientY;
        if (lastHoverIdx !== -1) {
          lastHoverIdx = -1;
          setHoveredState(null);
        }
        return;
      }

      if (relX < 0 || relY < 0 || relX > rect.width || relY > rect.height) {
        if (lastHoverIdx !== -1) {
          lastHoverIdx = -1;
          renderer.domElement.style.cursor = 'grab';
          setHoveredState(null);
        }
        return;
      }

      const hitIdx = pickNodeAtScreen(relX, relY);
      if (hitIdx >= 0) {
        lastHoverIdx = hitIdx;
        renderer.domElement.style.cursor = 'pointer';
        setHoveredState({ asset: nodes[hitIdx].asset, x: relX, y: relY });
      } else if (lastHoverIdx !== -1) {
        lastHoverIdx = -1;
        renderer.domElement.style.cursor = 'grab';
        setHoveredState(null);
      }
    };

    const onPointerUp = (e: PointerEvent) => {
      const wasClick = isDragging && !dragMoved;
      isDragging = false;
      if (wasClick) {
        const rect = renderer.domElement.getBoundingClientRect();
        const hitIdx = pickNodeAtScreen(e.clientX - rect.left, e.clientY - rect.top);
        if (hitIdx >= 0) {
          setSelectedAssetId(nodes[hitIdx].asset.asset_id);
        }
      }
    };

    const onPointerLeave = () => {
      isDragging = false;
      lastHoverIdx = -1;
      setHoveredState(null);
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      cameraOrbitRef.current.targetRadius = Math.max(
        10.5,
        Math.min(42, cameraOrbitRef.current.targetRadius + e.deltaY * 0.015)
      );
    };

    renderer.domElement.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    renderer.domElement.addEventListener('pointerleave', onPointerLeave);
    renderer.domElement.addEventListener('wheel', onWheel, { passive: false });

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      stageW = Math.max(320, entry.contentRect.width);
      stageH = Math.max(320, entry.contentRect.height);
      camera.aspect = stageW / stageH;
      camera.updateProjectionMatrix();
      renderer.setSize(stageW, stageH);
    });
    resizeObserver.observe(container);

    const tmpColor = new THREE.Color();
    const goldColor = new THREE.Color(0xfde047);
    const cyanColor = new THREE.Color(0x38bdf8);
    const whiteColor = new THREE.Color(0xffffff);
    const activeBridgePts: THREE.Vector3[] = [];
    let rafId = 0;
    let clockTime = 0;

    const animate = () => {
      rafId = requestAnimationFrame(animate);
      clockTime += 0.016;
      const st = stateRef.current;

      const cam = cameraOrbitRef.current;
      if (st.autoRotate && !isDragging) {
        cam.targetTheta += 0.0022;
      }
      cam.theta += (cam.targetTheta - cam.theta) * 0.085;
      cam.phi += (cam.targetPhi - cam.phi) * 0.085;
      cam.radius += (cam.targetRadius - cam.radius) * 0.09;
      cam.lookAt.lerp(cam.targetLookAt, 0.08);

      camera.position.set(
        cam.lookAt.x + cam.radius * Math.sin(cam.phi) * Math.sin(cam.theta),
        cam.lookAt.y + cam.radius * Math.cos(cam.phi),
        cam.lookAt.z + cam.radius * Math.sin(cam.phi) * Math.cos(cam.theta)
      );
      camera.lookAt(cam.lookAt);

      gravityGuides.visible = st.mode === 'gravity';
      terrainGuides.visible = st.mode === 'terrain';
      terrainStalks.visible = st.mode === 'terrain';
      oklabGuides.visible = st.mode === 'oklab';

      if (morphProgress < 1) {
        morphProgress = Math.min(1, morphProgress + 0.036);
        const eased = 1 - Math.pow(1 - morphProgress, 3);
        for (let i = 0; i < count; i++) {
          curPos[i].lerpVectors(fromPos[i], toPos[i], eased);
        }
      }

      const hasSemantic = Boolean(st.semanticScores && Object.keys(st.semanticScores).length > 0);
      const activeFocusId = st.hoveredAssetId ?? st.selectedAssetId;
      const hasSpotlight = Boolean(st.focusNeighborSet);

      // Update Obsidian Dot-Matrix Shader Attributes + Terrain Stalks
      for (let i = 0; i < count; i++) {
        const n = nodes[i];
        const pos = curPos[i];
        const aid = n.asset.asset_id;

        const isBridge = st.showBridge && st.bridgeIdSet.has(aid);
        const isFusion = st.fusionIdSet.has(aid);
        const isSelected = st.selectedAssetId === aid;
        const isHovered = st.hoveredAssetId === aid;
        const isNeighbor = hasSpotlight && st.focusNeighborSet!.has(aid);
        const semScore = hasSemantic ? st.semanticScores?.[aid] : undefined;

        const dimmedByDomain = st.focusDomain !== 'all' && n.domain.id !== st.focusDomain && !isBridge && !isSelected;
        const dimmedBySearch = hasSemantic && semScore === undefined && !isSelected && !isFusion;
        const dimmedBySpotlight = hasSpotlight && !isNeighbor && !isBridge && !isFusion;
        const dimmed = dimmedByDomain || dimmedBySearch || dimmedBySpotlight;

        // Quad sizes sized for silky feathered Gaussian bloom around a tiny pinpoint core
        let sz = n.isContrast ? 22.0 : 17.5;
        let alpha = dimmed ? 0.16 : 0.96;
        let ringFlag = n.isContrast && st.mode === 'gravity' ? 1.0 : 0.0;

        if (semScore !== undefined) {
          sz = 28.0;
          alpha = 1.0;
          ringFlag = 1.0;
        }
        if (isFusion) {
          sz = 31.0;
          alpha = 1.0;
          ringFlag = 2.0;
        }
        if (isBridge) {
          sz = 33.0 + Math.sin(clockTime * 3.2 + i) * 2.2;
          alpha = 1.0;
          ringFlag = 2.0;
        }
        if (isNeighbor && !isHovered && !isSelected) {
          sz = 25.0;
          alpha = 1.0;
        }
        if (isSelected || isHovered) {
          sz = 38.0;
          alpha = 1.0;
          ringFlag = 2.0;
        }

        // Pure flat vibrant color (zero muddy PBR shadows!)
        const baseColor = st.mode === 'oklab' ? n.paletteColor : n.domainColor;
        if (isHovered || isSelected) {
          tmpColor.copy(baseColor).lerp(whiteColor, 0.55);
        } else if (isBridge) {
          tmpColor.copy(goldColor);
        } else if (isFusion) {
          tmpColor.copy(cyanColor);
        } else if (semScore !== undefined) {
          tmpColor.copy(baseColor).lerp(whiteColor, 0.35);
        } else {
          tmpColor.copy(baseColor);
        }

        const i3 = i * 3;
        ptPositions[i3] = pos.x;
        ptPositions[i3 + 1] = pos.y;
        ptPositions[i3 + 2] = pos.z;

        ptColors[i3] = tmpColor.r;
        ptColors[i3 + 1] = tmpColor.g;
        ptColors[i3 + 2] = tmpColor.b;

        ptSizes[i] = sz;
        ptAlphas[i] = alpha;
        ptRings[i] = ringFlag;

        // Vertical drop-stalks in Semantic Terrain mode (domain-tinted!)
        if (st.mode === 'terrain') {
          const s6 = i * 6;
          stalkPositions[s6] = pos.x;
          stalkPositions[s6 + 1] = FLOOR_Y;
          stalkPositions[s6 + 2] = pos.z;
          stalkPositions[s6 + 3] = pos.x;
          stalkPositions[s6 + 4] = dimmed ? FLOOR_Y : pos.y;
          stalkPositions[s6 + 5] = pos.z;

          const dimMul = dimmed ? 0.12 : 0.72;
          stalkColors[s6] = tmpColor.r * 0.2;
          stalkColors[s6 + 1] = tmpColor.g * 0.2;
          stalkColors[s6 + 2] = tmpColor.b * 0.2;
          stalkColors[s6 + 3] = tmpColor.r * dimMul;
          stalkColors[s6 + 4] = tmpColor.g * dimMul;
          stalkColors[s6 + 5] = tmpColor.b * dimMul;
        }
      }

      ptGeo.attributes.position.needsUpdate = true;
      ptGeo.attributes.aColor.needsUpdate = true;
      ptGeo.attributes.aSize.needsUpdate = true;
      ptGeo.attributes.aAlpha.needsUpdate = true;
      ptGeo.attributes.aRing.needsUpdate = true;
      if (st.mode === 'terrain') {
        stalkGeo.attributes.position.needsUpdate = true;
        stalkGeo.attributes.color.needsUpdate = true;
      }

      // --- Update Obsidian Semantic Web Edges ---
      const webVisible = st.showWebEdges && st.mode !== 'oklab';
      webLines.visible = webVisible;
      if (webVisible) {
        webMat.opacity = hasSpotlight || hasSemantic ? 0.045 : 0.14;
        for (let e = 0; e < webEdgeCount; e++) {
          const [aIdx, bIdx] = webEdgePairs[e];
          const na = nodes[aIdx];
          const nb = nodes[bIdx];
          const pa = curPos[aIdx];
          const pb = curPos[bIdx];
          const o = e * 6;

          const hideEdge =
            st.focusDomain !== 'all' &&
            na.domain.id !== st.focusDomain &&
            nb.domain.id !== st.focusDomain;

          if (hideEdge) {
            webPositions[o] = webPositions[o + 1] = webPositions[o + 2] = 0;
            webPositions[o + 3] = webPositions[o + 4] = webPositions[o + 5] = 0;
          } else {
            webPositions[o] = pa.x;
            webPositions[o + 1] = pa.y;
            webPositions[o + 2] = pa.z;
            webPositions[o + 3] = pb.x;
            webPositions[o + 4] = pb.y;
            webPositions[o + 5] = pb.z;

            webColors[o] = na.domainColor.r;
            webColors[o + 1] = na.domainColor.g;
            webColors[o + 2] = na.domainColor.b;
            webColors[o + 3] = nb.domainColor.r;
            webColors[o + 4] = nb.domainColor.g;
            webColors[o + 5] = nb.domainColor.b;
          }
        }
        webGeo.attributes.position.needsUpdate = true;
        webGeo.attributes.color.needsUpdate = true;
      }

      // --- Update Obsidian Spotlight Neighbor Filaments ---
      if (activeFocusId) {
        const focusNode = nodeById.get(activeFocusId);
        if (focusNode) {
          const fp = curPos[focusNode.index];
          const nbs = (focusNode.asset.similar_ids ?? []).slice(0, 6);
          let lineIdx = 0;
          for (const nb of nbs) {
            const targetNode = nodeById.get(nb.asset_id);
            if (!targetNode || lineIdx >= neighborMaxLines) continue;
            const tp = curPos[targetNode.index];
            const o = lineIdx * 6;
            neighborPositions[o] = fp.x;
            neighborPositions[o + 1] = fp.y;
            neighborPositions[o + 2] = fp.z;
            neighborPositions[o + 3] = tp.x;
            neighborPositions[o + 4] = tp.y;
            neighborPositions[o + 5] = tp.z;
            lineIdx += 1;
          }
          for (let k = lineIdx; k < neighborMaxLines; k++) {
            const o = k * 6;
            neighborPositions[o] = neighborPositions[o + 1] = neighborPositions[o + 2] = 0;
            neighborPositions[o + 3] = neighborPositions[o + 4] = neighborPositions[o + 5] = 0;
          }
          neighborGeo.attributes.position.needsUpdate = true;
          neighborLines.visible = lineIdx > 0;
        } else {
          neighborLines.visible = false;
        }
      } else {
        neighborLines.visible = false;
      }

      // --- Update A -> B Bridge Curve & Pinpoint Light Pulse ---
      if (st.showBridge && st.bridgePath.length >= 2) {
        activeBridgePts.length = 0;
        for (const ba of st.bridgePath) {
          const bn = nodeById.get(ba.asset_id);
          if (bn) activeBridgePts.push(curPos[bn.index]);
        }
        if (activeBridgePts.length >= 2) {
          const curve = new THREE.CatmullRomCurve3(activeBridgePts, false, 'catmullrom', 0.25);
          bridgeGeo.setFromPoints(curve.getPoints(56));
          bridgeLine.visible = true;

          const u = (clockTime * 0.2) % 1;
          const pPos = curve.getPointAt(u);
          const posAttr = pulseGeo.attributes.position as THREE.BufferAttribute;
          posAttr.setXYZ(0, pPos.x, pPos.y, pPos.z);
          posAttr.needsUpdate = true;
          bridgePulse.visible = true;
        } else {
          bridgeLine.visible = false;
          bridgePulse.visible = false;
        }
      } else {
        bridgeLine.visible = false;
        bridgePulse.visible = false;
      }

      // --- Update Semantic Search Drop-Pin Beacon + Top-6 Rays ---
      if (hasSemantic && st.semanticScores) {
        const topMatches = Object.entries(st.semanticScores)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 6)
          .map(([id]) => nodeById.get(id))
          .filter((n): n is ComputedNode => Boolean(n));

        if (topMatches.length > 0) {
          const bPos = new THREE.Vector3();
          for (const tm of topMatches) bPos.add(curPos[tm.index]);
          bPos.divideScalar(topMatches.length);
          bPos.y += 1.2 + Math.sin(clockTime * 3.0) * 0.14;

          searchBeacon.position.copy(bPos);
          searchBeacon.rotation.y = clockTime * 1.1;
          searchBeacon.visible = true;

          for (let k = 0; k < 6; k++) {
            const o = k * 6;
            if (k < topMatches.length) {
              const tp = curPos[topMatches[k].index];
              searchRayPositions[o] = bPos.x;
              searchRayPositions[o + 1] = bPos.y;
              searchRayPositions[o + 2] = bPos.z;
              searchRayPositions[o + 3] = tp.x;
              searchRayPositions[o + 4] = tp.y;
              searchRayPositions[o + 5] = tp.z;
            } else {
              searchRayPositions[o] = searchRayPositions[o + 1] = searchRayPositions[o + 2] = 0;
              searchRayPositions[o + 3] = searchRayPositions[o + 4] = searchRayPositions[o + 5] = 0;
            }
          }
          searchRayGeo.attributes.position.needsUpdate = true;
          searchRays.visible = true;
        } else {
          searchBeacon.visible = false;
          searchRays.visible = false;
        }
      } else {
        searchBeacon.visible = false;
        searchRays.visible = false;
      }

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave);
      renderer.domElement.removeEventListener('wheel', onWheel);
      ptGeo.dispose();
      ptMat.dispose();
      webGeo.dispose();
      webMat.dispose();
      stalkGeo.dispose();
      stalkMat.dispose();
      neighborGeo.dispose();
      neighborMat.dispose();
      bridgeGeo.dispose();
      bridgeMat.dispose();
      pulseGeo.dispose();
      pulseMat.dispose();
      beaconGeo.dispose();
      beaconMat.dispose();
      searchRayGeo.dispose();
      searchRayMat.dispose();
      renderer.dispose();
    };
  }, [nodes, nodeById, webEdgePairs]);

  const personalCount = useMemo(() => nodes.filter((n) => !n.isContrast).length, [nodes]);
  const contrastCount = nodes.length - personalCount;

  return (
    <div className="rounded-2xl border border-zinc-800/90 bg-[#090b10] text-zinc-100 overflow-hidden shadow-2xl">
      {/* Top Minimalist Obsidian Toolbar */}
      <div className="px-4 py-3 border-b border-white/10 bg-[#0c0f17]/95 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => handleModeChange('gravity')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition-all ${
              mode === 'gravity'
                ? 'bg-zinc-100 text-zinc-950 font-semibold shadow-sm'
                : 'bg-white/5 text-zinc-300 hover:bg-white/10 border border-white/10'
            }`}
          >
            <Compass className="w-3.5 h-3.5 text-amber-400" />
            <span>① 引力星轨 &amp; 光桥</span>
          </button>
          <button
            type="button"
            onClick={() => handleModeChange('terrain')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition-all ${
              mode === 'terrain'
                ? 'bg-zinc-100 text-zinc-950 font-semibold shadow-sm'
                : 'bg-white/5 text-zinc-300 hover:bg-white/10 border border-white/10'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-emerald-400" />
            <span>② 语义地形海拔</span>
          </button>
          <button
            type="button"
            onClick={() => handleModeChange('oklab')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition-all ${
              mode === 'oklab'
                ? 'bg-zinc-100 text-zinc-950 font-semibold shadow-sm'
                : 'bg-white/5 text-zinc-300 hover:bg-white/10 border border-white/10'
            }`}
          >
            <Palette className="w-3.5 h-3.5 text-sky-400" />
            <span>③ OKLab 色彩雕塑</span>
          </button>

          {mode === 'terrain' && (
            <div className="ml-1 pl-2 border-l border-white/10 flex items-center gap-1">
              <span className="text-[11px] text-zinc-400 mr-0.5">Y轴海拔:</span>
              {(
                [
                  { id: 'contrast', label: '破圈反差' },
                  { id: 'warmth', label: '冷暖色温' },
                  { id: 'tectonic', label: '构造硬核度' },
                ] as Array<{ id: TerrainElevationAxis; label: string }>
              ).map((ax) => (
                <button
                  key={ax.id}
                  type="button"
                  onClick={() => setTerrainAxis(ax.id)}
                  className={`px-2 py-1 rounded-md text-[11px] transition-colors ${
                    terrainAxis === ax.id
                      ? 'bg-emerald-400/20 text-emerald-200 border border-emerald-400/40 font-semibold'
                      : 'text-zinc-400 hover:text-zinc-200 bg-white/5 border border-white/5'
                  }`}
                >
                  {ax.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {mode !== 'oklab' && (
            <button
              type="button"
              onClick={() => setShowWebEdges((v) => !v)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                showWebEdges
                  ? 'bg-white/10 text-zinc-100 border-white/20'
                  : 'bg-white/5 text-zinc-400 border-white/10 hover:text-zinc-200'
              }`}
              title="显示或隐藏 Obsidian 语义关系细丝"
            >
              关系网
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowBridge((v) => !v)}
            className={`px-2.5 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 border transition-colors ${
              showBridge
                ? 'bg-amber-400/15 text-amber-200 border-amber-400/40'
                : 'bg-white/5 text-zinc-400 border-white/10 hover:text-zinc-200'
            }`}
          >
            <GitBranch className="w-3.5 h-3.5" />
            <span>A→B 光桥</span>
          </button>
          <button
            type="button"
            onClick={() => setAutoRotate((v) => !v)}
            className="px-2.5 py-1.5 rounded-lg text-xs bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 inline-flex items-center gap-1.5 transition-colors"
            title={autoRotate ? '暂停自动旋转' : '开启自动旋转'}
          >
            {autoRotate ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{autoRotate ? '自转' : '暂停'}</span>
          </button>
          <button
            type="button"
            onClick={handleResetView}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 transition-colors"
            title="复位视角"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main 3D Obsidian Dot-Matrix Graph Stage */}
      <div
        className="relative w-full h-[640px] select-none overflow-hidden"
        style={{
          background:
            'radial-gradient(ellipse at 50% 45%, #121520 0%, #0a0c12 62%, #07080d 100%)',
        }}
      >
        <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

        {/* Top-Left Telemetry Overlay */}
        <div className="pointer-events-none absolute top-3.5 left-3.5 max-w-[292px] rounded-xl bg-[#090c14]/75 backdrop-blur-md border border-white/10 px-3.5 py-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold tracking-wide text-zinc-100">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>
              {mode === 'gravity'
                ? '引力星轨 · Obsidian 语义星图'
                : mode === 'terrain'
                  ? '语义地形海拔 · 垂直构造点阵'
                  : 'OKLab 3D 色彩雕塑 · 物理色域柱'}
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">
            {mode === 'gravity'
              ? `内环实心点 ${personalCount} 个核心原点 · 外环细圈点 ${contrastCount} 个破圈卫星 · 悬停高亮邻域与实图。`
              : mode === 'terrain'
                ? 'X-Z 地面保留 256 维语义岛屿聚类，细线标出每张作品在所选维度的海拔。'
                : '圆周角 = 色相 Hue · 半径 = 饱和度 Chroma · 高度 = 明度 Lightness，色彩直接映射真实主色。'}
          </p>
          {semanticScores && Object.keys(semanticScores).length > 0 && (
            <div className="mt-2 pt-1.5 border-t border-white/10 text-[11px] text-sky-300 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 shrink-0" />
              <span>语义搜索信标已落地，点亮 Top-{Object.keys(semanticScores).length} 相似节点</span>
            </div>
          )}
        </div>

        {/* Top-Right 8-Domain Color Legend & Fly-To Pills */}
        <div className="absolute top-3.5 right-3.5 flex flex-wrap justify-end gap-1.5 max-w-[390px]">
          <button
            type="button"
            onClick={() => handleDomainFocus('all')}
            className={`px-2.5 py-1 rounded-full text-[11px] border transition-all ${
              focusDomain === 'all'
                ? 'bg-zinc-100 text-zinc-950 border-white font-semibold'
                : 'bg-[#090c14]/75 text-zinc-300 border-white/15 hover:border-white/40 backdrop-blur-md'
            }`}
          >
            全部 8 域 ({nodes.length})
          </button>
          {DOMAIN_LIST.map((dom) => {
            const cnt = domainCounts[dom.id] ?? 0;
            if (cnt === 0) return null;
            const isAct = focusDomain === dom.id;
            return (
              <button
                key={dom.id}
                type="button"
                onClick={() => handleDomainFocus(dom.id)}
                className={`px-2.5 py-1 rounded-full text-[11px] border inline-flex items-center gap-1.5 transition-all backdrop-blur-md ${
                  isAct
                    ? 'bg-zinc-100 text-zinc-950 border-white font-semibold'
                    : 'bg-[#090c14]/75 text-zinc-300 border-white/15 hover:border-white/40'
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: dom.color }}
                />
                <span>{dom.label}</span>
                <span className="opacity-65">{cnt}</span>
              </button>
            );
          })}
        </div>

        {/* Hover Glass Image Preview Card */}
        {hoveredState && !selectedAsset && (
          <div
            className="pointer-events-none absolute z-20 w-[236px] rounded-xl bg-[#0b0e17]/92 backdrop-blur-xl border border-white/15 p-2.5 shadow-2xl"
            style={{
              left: Math.min(Math.max(12, hoveredState.x + 18), (containerRef.current?.clientWidth ?? 900) - 252),
              top: Math.min(Math.max(12, hoveredState.y - 48), 430),
            }}
          >
            <div className="flex gap-2.5">
              <div className="w-16 h-20 rounded-lg overflow-hidden bg-zinc-900 shrink-0 border border-white/10">
                <img
                  src={hoveredState.asset.image_url}
                  alt={hoveredState.asset.title}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="min-w-0 flex-1 flex flex-col justify-between">
                <div>
                  <div className="text-xs font-semibold text-zinc-100 line-clamp-2 leading-snug">
                    {hoveredState.asset.title}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-zinc-200">
                      {hoveredState.asset.archetype_label}
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded ${
                        hoveredState.asset.source_origin === 'profile_expansion'
                          ? 'bg-amber-400/20 text-amber-200'
                          : 'bg-emerald-400/20 text-emerald-200'
                      }`}
                    >
                      {hoveredState.asset.source_origin === 'profile_expansion' ? '外环破圈' : '核心原点'}
                    </span>
                  </div>
                </div>
                <div className="text-[10px] text-zinc-400 truncate mt-1">
                  {hoveredState.asset.native_style_primary || hoveredState.asset.aesthetic_style_zh}
                </div>
              </div>
            </div>
            <div className="mt-2 flex h-1.5 rounded-full overflow-hidden gap-0.5">
              {(hoveredState.asset.granular_descriptors?.color_palette ?? []).slice(0, 5).map((hex, i) => (
                <span key={`${hex}-${i}`} className="flex-1 h-full" style={{ backgroundColor: hex }} />
              ))}
            </div>
            <div className="mt-1.5 text-[10px] text-zinc-400 flex items-center justify-between">
              <span>点击锁定节点</span>
              {typeof hoveredState.asset.core_distance === 'number' && (
                <span>轨道距 {Math.round(hoveredState.asset.core_distance * 100)}%</span>
              )}
            </div>
          </div>
        )}

        {/* Click-Locked Right-Side Glass Inspector HUD */}
        {selectedAsset && (
          <div className="absolute right-3.5 top-20 z-20 w-[268px] rounded-xl bg-[#0b0e17]/92 backdrop-blur-xl border border-white/15 p-3 shadow-2xl space-y-2.5">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-xs font-bold text-zinc-100 line-clamp-2 leading-snug">
                  {selectedAsset.title}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-zinc-200">
                    {selectedAsset.archetype_label}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-zinc-300">
                    {selectedAsset.native_style_primary || selectedAsset.aesthetic_style_zh}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedAssetId(null)}
                className="p-1 rounded-md hover:bg-white/10 text-zinc-400 hover:text-zinc-100"
                aria-label="关闭检查器"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="relative aspect-[4/3] w-full rounded-lg overflow-hidden bg-zinc-900 border border-white/10">
              <img
                src={selectedAsset.image_url}
                alt={selectedAsset.title}
                className="w-full h-full object-cover"
              />
            </div>

            <div className="flex h-2 rounded-md overflow-hidden gap-0.5">
              {(selectedAsset.granular_descriptors?.color_palette ?? []).slice(0, 5).map((hex, i) => (
                <span
                  key={`${hex}-${i}`}
                  className="flex-1 h-full"
                  style={{ backgroundColor: hex }}
                  title={hex}
                />
              ))}
            </div>

            {selectedAsset.aesthetic_critique?.headline_insight && (
              <p className="text-[11px] text-zinc-300 leading-relaxed line-clamp-2">
                {selectedAsset.aesthetic_critique.headline_insight}
              </p>
            )}

            <div className="grid grid-cols-2 gap-1.5 pt-0.5">
              <button
                type="button"
                onClick={() => onSelectAsset(selectedAsset)}
                className="px-2.5 py-1.5 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 text-[11px] font-semibold inline-flex items-center justify-center gap-1 transition-colors"
              >
                <Maximize2 className="w-3 h-3" />
                <span>深度赏析</span>
              </button>
              <button
                type="button"
                onClick={() => onToggleFusion(selectedAsset.asset_id)}
                className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium inline-flex items-center justify-center gap-1 border transition-colors ${
                  fusionIdSet.has(selectedAsset.asset_id)
                    ? 'bg-sky-500/20 text-sky-200 border-sky-400/50'
                    : 'bg-white/5 hover:bg-white/10 text-zinc-200 border-white/15'
                }`}
              >
                <Wand2 className="w-3 h-3" />
                <span>{fusionIdSet.has(selectedAsset.asset_id) ? '已入融合池' : '加入融合'}</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setCustomBridgeA(selectedAsset.asset_id);
                  if (!customBridgeB && activeBridgeEndpoints[1]) {
                    setCustomBridgeB(activeBridgeEndpoints[1]);
                  }
                  setShowBridge(true);
                }}
                className="px-2 py-1 rounded-lg bg-amber-400/10 hover:bg-amber-400/20 border border-amber-400/30 text-amber-200 text-[10px] font-medium transition-colors"
              >
                设为光桥起点 A
              </button>
              <button
                type="button"
                onClick={() => {
                  setCustomBridgeB(selectedAsset.asset_id);
                  if (!customBridgeA && activeBridgeEndpoints[0]) {
                    setCustomBridgeA(activeBridgeEndpoints[0]);
                  }
                  setShowBridge(true);
                }}
                className="px-2 py-1 rounded-lg bg-amber-400/10 hover:bg-amber-400/20 border border-amber-400/30 text-amber-200 text-[10px] font-medium transition-colors"
              >
                设为光桥终点 B
              </button>
            </div>
          </div>
        )}

        {/* Bottom A -> B Cross-Domain Inspiration Bridge Filmstrip */}
        {showBridge && bridgePath.length >= 2 && (
          <div className="absolute bottom-3.5 left-3.5 right-3.5 z-10 rounded-xl bg-[#090c14]/86 backdrop-blur-xl border border-amber-400/25 px-3 py-2 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <div className="shrink-0 pr-2 border-r border-white/10">
                <div className="text-[11px] font-semibold text-amber-300 flex items-center gap-1">
                  <GitBranch className="w-3.5 h-3.5" />
                  <span>A→B 跨界光桥</span>
                </div>
                <div className="text-[10px] text-zinc-400">{bridgePath.length} 步最短路径</div>
              </div>

              <div className="flex items-center gap-1.5">
                {bridgePath.map((step, idx) => (
                  <React.Fragment key={step.asset_id}>
                    <button
                      type="button"
                      onClick={() => setSelectedAssetId(step.asset_id)}
                      className={`flex items-center gap-1.5 pr-2 pl-1 py-1 rounded-lg border transition-all shrink-0 ${
                        selectedAssetId === step.asset_id
                          ? 'bg-amber-400/20 border-amber-300/60'
                          : 'bg-white/5 hover:bg-white/10 border-white/10'
                      }`}
                    >
                      <img
                        src={step.image_url}
                        alt={step.title}
                        className="w-7 h-7 rounded object-cover shrink-0 border border-white/10"
                      />
                      <div className="text-left max-w-[88px]">
                        <div className="text-[10px] font-medium text-zinc-100 truncate">
                          {idx === 0 ? 'A · ' : idx === bridgePath.length - 1 ? 'B · ' : `${idx + 1} · `}
                          {step.title}
                        </div>
                        <div className="text-[9px] text-zinc-400 truncate">{step.archetype_label}</div>
                      </div>
                    </button>
                    {idx < bridgePath.length - 1 && (
                      <span className="text-amber-400/70 text-xs shrink-0">→</span>
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={handleCycleBridge}
                className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/15 text-[11px] text-zinc-200 inline-flex items-center gap-1 transition-colors"
                title="随机切换一组跨界 A→B 路径"
              >
                <RefreshCw className="w-3 h-3" />
                <span>换一组</span>
              </button>
              <button
                type="button"
                onClick={handleFuseBridge}
                className="px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 text-[11px] font-semibold inline-flex items-center gap-1.5 transition-colors shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>光桥一键融合</span>
              </button>
            </div>
          </div>
        )}

        {!showBridge && (
          <div className="pointer-events-none absolute bottom-3.5 left-3.5 rounded-lg bg-[#090c14]/75 backdrop-blur-md border border-white/10 px-3 py-1.5 text-[11px] text-zinc-400 flex items-center gap-2">
            <Eye className="w-3.5 h-3.5 text-zinc-300" />
            <span>拖拽 360° 旋转 · 滚轮缩放 · 悬停高亮 Obsidian 语义邻域</span>
          </div>
        )}
      </div>
    </div>
  );
};
