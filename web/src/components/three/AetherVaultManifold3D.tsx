'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useTheme } from 'next-themes';
import { Eye, Pause, Play, RotateCcw, Sparkles } from 'lucide-react';
import type { CuratedShowcaseAsset, SpectrumAxisMeta } from '@/types/aethervault';
import type { SpectrumAxisId } from '@/engine/salienceMetric';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export interface RankedManifoldItem {
  asset: CuratedShowcaseAsset;
  matchPct: number;
  distance: number;
}

interface AetherVaultManifold3DProps {
  rankedAssets: RankedManifoldItem[];
  axes: SpectrumAxisMeta[];
  queryScores: Record<SpectrumAxisId, number>;
  onSelectAsset: (asset: CuratedShowcaseAsset) => void;
  onAssignSlot?: (slot: 'optics' | 'material' | 'lighting', assetId: string) => void;
  minimalMode?: boolean;
}

const DOMAIN_COLORS: Record<string, number> = {
  architecture: 0x153ce8,
  industrial: 0x0f766e,
  editorial: 0x9333ea,
  craft: 0xd97706,
  graphic: 0xe11d48,
};

const DOMAIN_LABELS: Record<string, string> = {
  architecture: '建筑空间',
  industrial: '工业硬件',
  editorial: '视觉摄影',
  craft: '器物工艺',
  graphic: '平面构成',
};

const ARCHETYPE_COLORS: Record<string, number> = {
  interior: 0x2563eb,
  architecture: 0x153ce8,
  graphic_typography: 0xe11d48,
  craft: 0xd97706,
  industrial: 0x0f766e,
  landscape: 0x059669,
  illustration_character: 0x9333ea,
  fashion_photography: 0xdb2777,
};

const ARCHETYPE_LABELS: Record<string, string> = {
  interior: '室内设计',
  architecture: '建筑设计',
  graphic_typography: '平面与字体',
  craft: '器物工艺',
  industrial: '工业设计',
  landscape: '景观空间',
  illustration_character: '插画与角色',
  fashion_photography: '时尚摄影',
};

const SCALE = 2.35;

export const AetherVaultManifold3D: React.FC<AetherVaultManifold3DProps> = ({
  rankedAssets,
  axes,
  queryScores,
  onSelectAsset,
  onAssignSlot,
  minimalMode = false,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [xAxis, setXAxis] = useState<SpectrumAxisId>('tectonic_honesty');
  const [yAxis, setYAxis] = useState<SpectrumAxisId>('geometric_order');
  const [zAxis, setZAxis] = useState<SpectrumAxisId>('surface_entropy');
  const [autoRotate, setAutoRotate] = useState(true);
  const [webglFailed, setWebglFailed] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<RankedManifoldItem | null>(null);
  const [pinnedItem, setPinnedItem] = useState<RankedManifoldItem | null>(null);

  // Refs synced into animation loop without recreating WebGL context
  const queryTargetRef = useRef(new THREE.Vector3(0, 0, 0));
  const autoRotateRef = useRef(autoRotate);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const cardEntriesRef = useRef<
    Array<{
      group: THREE.Group;
      borderMat: THREE.MeshBasicMaterial;
      targetPos: THREE.Vector3;
      item: RankedManifoldItem;
    }>
  >([]);
  const tetherGeomRef = useRef<THREE.BufferGeometry | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const cubeLineMatRef = useRef<THREE.LineBasicMaterial | null>(null);
  const probeMatRef = useRef<THREE.MeshStandardMaterial | null>(null);
  const tetherMatRef = useRef<THREE.LineBasicMaterial | null>(null);

  const axisMetaMap = useMemo(() => {
    const map: Partial<Record<SpectrumAxisId, SpectrumAxisMeta>> = {};
    for (const a of axes) map[a.axis_id] = a;
    return map;
  }, [axes]);

  useEffect(() => {
    autoRotateRef.current = autoRotate;
    if (controlsRef.current) {
      controlsRef.current.autoRotate = autoRotate;
    }
  }, [autoRotate]);

  // Update target positions when queryScores, rankedAssets, or chosen axes change
  useEffect(() => {
    queryTargetRef.current.set(
      (queryScores[xAxis] ?? 0) * SCALE,
      (queryScores[yAxis] ?? 0) * SCALE,
      (queryScores[zAxis] ?? 0) * SCALE
    );

    const rankById = new Map<string, { item: RankedManifoldItem; rank: number }>();
    rankedAssets.forEach((item, idx) => {
      rankById.set(item.asset.asset_id, { item, rank: idx });
    });

    const getCategoryHex = (asset: CuratedShowcaseAsset): number => {
      if (minimalMode && asset.archetype) {
        return ARCHETYPE_COLORS[asset.archetype] ?? 0x64748b;
      }
      return DOMAIN_COLORS[asset.subject_isolation.domain] ?? 0x64748b;
    };

    for (const entry of cardEntriesRef.current) {
      const updated = rankById.get(entry.item.asset.asset_id);
      if (updated) {
        entry.group.visible = true;
        entry.item = updated.item;
        const scores = updated.item.asset.style_spectrums;
        entry.targetPos.set(
          (scores[xAxis]?.score ?? 0) * SCALE,
          (scores[yAxis]?.score ?? 0) * SCALE,
          (scores[zAxis]?.score ?? 0) * SCALE
        );
        const isTop6 = updated.rank < 6;
        const scaleVal = isTop6 ? 1.24 : 0.88;
        entry.group.scale.set(scaleVal, scaleVal, scaleVal);
        entry.borderMat.color.setHex(
          isTop6 ? (isDark ? 0x4b74ff : 0x153ce8) : getCategoryHex(updated.item.asset)
        );
      } else {
        entry.group.visible = false;
      }
    }
  }, [queryScores, rankedAssets, xAxis, yAxis, zAxis, isDark, minimalMode]);

  // Sync theme colors onto live Three.js scene
  useEffect(() => {
    if (sceneRef.current) {
      sceneRef.current.background = new THREE.Color(isDark ? 0x0b0f19 : 0xf4f6fa);
    }
    if (cubeLineMatRef.current) {
      cubeLineMatRef.current.color.setHex(isDark ? 0x2a354d : 0xcbd5e1);
    }
    if (probeMatRef.current) {
      probeMatRef.current.color.setHex(isDark ? 0x4b74ff : 0x153ce8);
      probeMatRef.current.emissive.setHex(isDark ? 0x2548c7 : 0x153ce8);
    }
    if (tetherMatRef.current) {
      tetherMatRef.current.color.setHex(isDark ? 0x6085ff : 0x153ce8);
    }
    if (gridRef.current) {
      const mats = Array.isArray(gridRef.current.material)
        ? gridRef.current.material
        : [gridRef.current.material];
      mats.forEach((m) => {
        if ('color' in m && m.color instanceof THREE.Color) {
          m.color.setHex(isDark ? 0x1f2a40 : 0xdce2ec);
        }
      });
    }
  }, [isDark]);

  // Initialize Three.js WebGL scene once when assets mount
  useEffect(() => {
    const container = containerRef.current;
    if (!container || rankedAssets.length === 0) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    } catch {
      setWebglFailed(true);
      return;
    }

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setAutoRotate(false);
      autoRotateRef.current = false;
    }

    const width = container.clientWidth || 640;
    const height = container.clientHeight || 420;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(isDark ? 0x0b0f19 : 0xf4f6fa);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
    camera.position.set(5.4, 3.6, 5.8);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = 2.8;
    controls.maxDistance = 12.5;
    controls.autoRotate = autoRotateRef.current;
    controls.autoRotateSpeed = 0.55;
    controlsRef.current = controls;

    // Studio lighting
    const ambient = new THREE.AmbientLight(0xffffff, 0.9);
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 8, 6);
    scene.add(ambient, dirLight);

    // Architectural bounding cube & floor reference grid
    const boxGeom = new THREE.BoxGeometry(SCALE * 2, SCALE * 2, SCALE * 2);
    const edgesGeom = new THREE.EdgesGeometry(boxGeom);
    const cubeLineMat = new THREE.LineBasicMaterial({
      color: isDark ? 0x2a354d : 0xcbd5e1,
      transparent: true,
      opacity: 0.75,
    });
    cubeLineMatRef.current = cubeLineMat;
    const cubeWireframe = new THREE.LineSegments(edgesGeom, cubeLineMat);
    scene.add(cubeWireframe);

    const grid = new THREE.GridHelper(
      SCALE * 2,
      8,
      isDark ? 0x29354f : 0xcbd5e1,
      isDark ? 0x1b2436 : 0xe2e8f0
    );
    grid.position.y = -SCALE;
    gridRef.current = grid;
    scene.add(grid);

    // Center orthogonal X / Y / Z axis guides
    const axisPositions = new Float32Array([
      -SCALE, 0, 0, SCALE, 0, 0,
      0, -SCALE, 0, 0, SCALE, 0,
      0, 0, -SCALE, 0, 0, SCALE,
    ]);
    const axisGeom = new THREE.BufferGeometry();
    axisGeom.setAttribute('position', new THREE.BufferAttribute(axisPositions, 3));
    const axisMat = new THREE.LineBasicMaterial({
      color: 0x64748b,
      transparent: true,
      opacity: 0.35,
    });
    scene.add(new THREE.LineSegments(axisGeom, axisMat));

    // Query Vector Probe (Cobalt Octahedron + Ring)
    const probeGroup = new THREE.Group();
    const probeGeom = new THREE.OctahedronGeometry(0.16, 0);
    const probeMat = new THREE.MeshStandardMaterial({
      color: isDark ? 0x4b74ff : 0x153ce8,
      emissive: isDark ? 0x2548c7 : 0x153ce8,
      emissiveIntensity: 0.55,
      roughness: 0.25,
      metalness: 0.3,
    });
    probeMatRef.current = probeMat;
    const probeMesh = new THREE.Mesh(probeGeom, probeMat);
    const ringGeom = new THREE.RingGeometry(0.24, 0.275, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: isDark ? 0x6085ff : 0x153ce8,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.75,
    });
    const probeRing = new THREE.Mesh(ringGeom, ringMat);
    probeGroup.add(probeMesh, probeRing);
    scene.add(probeGroup);

    // k-NN top-6 tether lines
    const tetherGeom = new THREE.BufferGeometry();
    tetherGeom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6 * 2 * 3), 3));
    const tetherMat = new THREE.LineBasicMaterial({
      color: isDark ? 0x6085ff : 0x153ce8,
      transparent: true,
      opacity: 0.65,
    });
    tetherGeomRef.current = tetherGeom;
    tetherMatRef.current = tetherMat;
    const tetherLines = new THREE.LineSegments(tetherGeom, tetherMat);
    scene.add(tetherLines);

    // Build specimen 3D nodes: top 80 as textured WebP plates + remaining specimens as crisp clickable domain nodes (60fps at 500+ scale)
    const MAX_TEXTURED_PLATES = 80;
    const texLoader = new THREE.TextureLoader();
    texLoader.setCrossOrigin('anonymous');
    const cardPlaneGeom = new THREE.PlaneGeometry(0.36, 0.27);
    const framePlaneGeom = new THREE.PlaneGeometry(0.4, 0.31);
    const nodeBoxGeom = new THREE.BoxGeometry(0.085, 0.085, 0.085);
    const createdTextures: THREE.Texture[] = [];
    const createdMaterials: THREE.Material[] = [];
    const pickMeshes: THREE.Mesh[] = [];
    const entries: typeof cardEntriesRef.current = [];

    rankedAssets.forEach((item, idx) => {
      const group = new THREE.Group();
      const scores = item.asset.style_spectrums;
      const pos = new THREE.Vector3(
        (scores[xAxis]?.score ?? 0) * SCALE,
        (scores[yAxis]?.score ?? 0) * SCALE,
        (scores[zAxis]?.score ?? 0) * SCALE
      );
      group.position.copy(pos);

      const domHex =
        minimalMode && item.asset.archetype
          ? ARCHETYPE_COLORS[item.asset.archetype] ?? 0x64748b
          : DOMAIN_COLORS[item.asset.subject_isolation.domain] ?? 0x64748b;
      const borderMat = new THREE.MeshBasicMaterial({
        color: idx < 6 ? (isDark ? 0x4b74ff : 0x153ce8) : domHex,
        side: THREE.DoubleSide,
      });
      createdMaterials.push(borderMat);

      if (idx < MAX_TEXTURED_PLATES) {
        const borderMesh = new THREE.Mesh(framePlaneGeom, borderMat);
        borderMesh.position.z = -0.004;

        const tex = texLoader.load(item.asset.image_url);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.minFilter = THREE.LinearFilter;
        createdTextures.push(tex);

        const imgMat = new THREE.MeshBasicMaterial({
          map: tex,
          side: THREE.DoubleSide,
        });
        createdMaterials.push(imgMat);
        const imgMesh = new THREE.Mesh(cardPlaneGeom, imgMat);
        imgMesh.userData = { assetId: item.asset.asset_id };
        pickMeshes.push(imgMesh);
        group.add(borderMesh, imgMesh);
      } else {
        const nodeMesh = new THREE.Mesh(nodeBoxGeom, borderMat);
        nodeMesh.userData = { assetId: item.asset.asset_id };
        pickMeshes.push(nodeMesh);
        group.add(nodeMesh);
      }

      const initialScale = idx < 6 ? 1.24 : 0.88;
      group.scale.set(initialScale, initialScale, initialScale);
      scene.add(group);

      entries.push({
        group,
        borderMat,
        targetPos: pos.clone(),
        item,
      });
    });

    cardEntriesRef.current = entries;

    // Raycasting for hover + click
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2(-99, -99);
    let pointerDownX = 0;
    let pointerDownY = 0;

    const updatePointer = (ev: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    };

    const handlePointerMove = (ev: PointerEvent) => {
      updatePointer(ev);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(pickMeshes, false);
      if (hits.length > 0) {
        const hitId = hits[0].object.userData.assetId as string;
        const found = cardEntriesRef.current.find((e) => e.item.asset.asset_id === hitId);
        if (found) {
          setHoveredItem(found.item);
          renderer.domElement.style.cursor = 'pointer';
          return;
        }
      }
      setHoveredItem(null);
      renderer.domElement.style.cursor = 'grab';
    };

    const handlePointerDown = (ev: PointerEvent) => {
      pointerDownX = ev.clientX;
      pointerDownY = ev.clientY;
    };

    const handlePointerUp = (ev: PointerEvent) => {
      const dist = Math.hypot(ev.clientX - pointerDownX, ev.clientY - pointerDownY);
      if (dist > 6) return;
      updatePointer(ev);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(pickMeshes, false);
      if (hits.length > 0) {
        const hitId = hits[0].object.userData.assetId as string;
        const found = cardEntriesRef.current.find((e) => e.item.asset.asset_id === hitId);
        if (found) {
          setPinnedItem(found.item);
        }
      }
    };

    renderer.domElement.addEventListener('pointermove', handlePointerMove);
    renderer.domElement.addEventListener('pointerdown', handlePointerDown);
    renderer.domElement.addEventListener('pointerup', handlePointerUp);

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
      if (!container) return;
      const w = container.clientWidth || 640;
      const h = container.clientHeight || 420;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    resizeObserver.observe(container);

    // Animation loop
    let rafId = 0;
    const clock = new THREE.Clock();
    const animate = () => {
      rafId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      probeGroup.position.lerp(queryTargetRef.current, 0.14);
      probeMesh.rotation.y = elapsed * 1.1;
      probeRing.lookAt(camera.position);

      // Smoothly interpolate specimen positions & billboard toward camera
      for (const entry of cardEntriesRef.current) {
        entry.group.position.lerp(entry.targetPos, 0.12);
        entry.group.quaternion.copy(camera.quaternion);
      }

      // Update k-NN tether vertices to Top-6 visible matches
      if (tetherGeomRef.current) {
        const posAttr = tetherGeomRef.current.getAttribute('position') as THREE.BufferAttribute;
        const top6 = [...cardEntriesRef.current]
          .filter((e) => e.group.visible)
          .sort((a, b) => a.item.distance - b.item.distance)
          .slice(0, 6);
        for (let i = 0; i < 6; i++) {
          const target = top6[i]?.group.position ?? probeGroup.position;
          posAttr.setXYZ(i * 2, probeGroup.position.x, probeGroup.position.y, probeGroup.position.z);
          posAttr.setXYZ(i * 2 + 1, target.x, target.y, target.z);
        }
        posAttr.needsUpdate = true;
      }

      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener('pointermove', handlePointerMove);
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
      renderer.domElement.removeEventListener('pointerup', handlePointerUp);
      controls.dispose();
      boxGeom.dispose();
      edgesGeom.dispose();
      cubeLineMat.dispose();
      axisGeom.dispose();
      axisMat.dispose();
      probeGeom.dispose();
      probeMat.dispose();
      ringGeom.dispose();
      ringMat.dispose();
      tetherGeom.dispose();
      tetherMat.dispose();
      cardPlaneGeom.dispose();
      framePlaneGeom.dispose();
      nodeBoxGeom.dispose();
      createdTextures.forEach((t) => t.dispose());
      createdMaterials.forEach((m) => m.dispose());
      renderer.dispose();
    };
    // Intentionally initialize WebGL scene once when asset count becomes ready
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rankedAssets.length > 0]);

  const handleResetCamera = () => {
    if (cameraRef.current && controlsRef.current) {
      cameraRef.current.position.set(5.4, 3.6, 5.8);
      controlsRef.current.target.set(0, 0, 0);
      controlsRef.current.update();
    }
  };

  const activePreview = pinnedItem ?? hoveredItem;

  if (webglFailed) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center space-y-2">
        <div className="text-sm font-semibold text-foreground">当前浏览器环境未启用 WebGL 3D 加速</div>
        <p className="text-xs text-muted-foreground">
          请切换至“标本画廊”视图浏览全部 {rankedAssets.length} 件跨界样张，8 轴向量重排与 AST 编译器不受影响。
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
      {/* Control Toolbar */}
      <div className="px-4 py-3 border-b border-border bg-secondary/40 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="default" className="mono">
            <Sparkles className="w-3 h-3" />
            {minimalMode ? 'Three.js 3D 审美星图' : 'Three.js 3D 美学光谱流形'}
          </Badge>
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {rankedAssets.length} 件标本投影 · {minimalMode ? '点击画片查看深度美学解析' : '钴蓝探针联动 Top-6 相似连线'}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {(
            [
              { label: 'X', value: xAxis, setter: setXAxis },
              { label: 'Y', value: yAxis, setter: setYAxis },
              { label: 'Z', value: zAxis, setter: setZAxis },
            ] as const
          ).map(({ label, value, setter }) => (
            <label key={label} className="inline-flex items-center gap-1.5">
              <span className="mono font-semibold text-primary">{label}</span>
              <select
                value={value}
                onChange={(e) => setter(e.target.value as SpectrumAxisId)}
                aria-label={`选择 ${label} 轴维度`}
                className="h-7 rounded-md border border-border bg-card px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {axes.map((a) => (
                  <option key={a.axis_id} value={a.axis_id}>
                    {a.label_zh}
                  </option>
                ))}
              </select>
            </label>
          ))}

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setAutoRotate((v) => !v)}
            className="h-7 px-2.5"
          >
            {autoRotate ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span className="hidden sm:inline">{autoRotate ? '暂停旋转' : '自动旋转'}</span>
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleResetCamera}
            className="h-7 px-2.5"
          >
            <RotateCcw className="w-3 h-3" />
            <span className="hidden sm:inline">重置视角</span>
          </Button>
        </div>
      </div>

      {/* 3D WebGL Viewport */}
      <div className="relative h-[420px] sm:h-[480px] w-full">
        <div
          ref={containerRef}
          className="h-full w-full"
          aria-label={`${rankedAssets.length} 件跨界标本 Three.js 三维正交美学流形画布`}
        />

        {/* Bottom-left Axis Legend */}
        <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-1.5">
          <div className="rounded-md border border-border/80 bg-card/85 backdrop-blur-md px-2.5 py-1 text-xs text-foreground shadow-sm mono">
            X: {axisMetaMap[xAxis]?.label_zh ?? xAxis} · Y: {axisMetaMap[yAxis]?.label_zh ?? yAxis} · Z:{' '}
            {axisMetaMap[zAxis]?.label_zh ?? zAxis}
          </div>
        </div>

        {/* Bottom-right Category Legend */}
        {(() => {
          const useArchetypeLegend =
            minimalMode && rankedAssets.some((item) => Boolean(item.asset.archetype));
          return (
            <div className="pointer-events-none hidden md:flex absolute bottom-3 right-3 items-center gap-2.5 rounded-md border border-border/80 bg-card/85 backdrop-blur-md px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
              {Object.entries(useArchetypeLegend ? ARCHETYPE_LABELS : DOMAIN_LABELS).map(
                ([key, zh]) => (
                  <span key={key} className="inline-flex items-center gap-1">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{
                        backgroundColor: `#${(
                          (useArchetypeLegend ? ARCHETYPE_COLORS[key] : DOMAIN_COLORS[key]) ??
                          0x64748b
                        )
                          .toString(16)
                          .padStart(6, '0')}`,
                      }}
                    />
                    <span>{zh}</span>
                  </span>
                )
              )}
            </div>
          );
        })()}

        {/* Interactive Specimen HUD Card (Hover or Click-Pinned) */}
        {activePreview && (
          <div className="absolute top-3 right-3 w-[min(280px,calc(100%-1.5rem))] rounded-lg border border-border bg-card/95 backdrop-blur-md p-3 shadow-lg space-y-2.5">
            <div className="flex items-start gap-2.5">
              <img
                src={activePreview.asset.image_url}
                alt={activePreview.asset.title}
                className="w-16 h-12 object-cover rounded-md border border-border shrink-0"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-1">
                  <span className="mono text-xs font-semibold text-primary">
                    {minimalMode
                      ? activePreview.asset.archetype_label ??
                        ARCHETYPE_LABELS[activePreview.asset.archetype ?? 'architecture']
                      : `${activePreview.matchPct}% 匹配`}
                  </span>
                  <span className="text-xs text-muted-foreground truncate">
                    {minimalMode
                      ? activePreview.asset.sub_style ?? ''
                      : DOMAIN_LABELS[activePreview.asset.subject_isolation.domain] ??
                        activePreview.asset.subject_isolation.domain}
                  </span>
                </div>
                <div className="text-xs font-semibold text-foreground line-clamp-2 mt-0.5">
                  {activePreview.asset.title}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-border">
              <Button
                type="button"
                variant="default"
                size="sm"
                className="h-7 px-2 text-xs flex-1"
                onClick={() => onSelectAsset(activePreview.asset)}
              >
                <Eye className="w-3 h-3" />
                <span>{minimalMode ? '查看深度美学解析' : '详情'}</span>
              </Button>
              {!minimalMode && onAssignSlot && (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => onAssignSlot('optics', activePreview.asset.asset_id)}
                  >
                    镜
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => onAssignSlot('material', activePreview.asset.asset_id)}
                  >
                    材
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => onAssignSlot('lighting', activePreview.asset.asset_id)}
                  >
                    光
                  </Button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
