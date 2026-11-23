'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useTheme } from 'next-themes';
import { Box, Eye, Layers, RotateCcw } from 'lucide-react';
import type { TectonicCase, TectonicTierState } from '@/types/tectonic';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface TectonicPlane3DProps {
  activeCase: TectonicCase;
  activeTier: TectonicTierState;
  showSeams: boolean;
  showPins: boolean;
}

type CameraPreset = 'perspective' | 'orthographic' | 'street';

const CAMERA_PRESETS: Record<CameraPreset, { pos: [number, number, number]; label: string }> = {
  perspective: { pos: [2.2, 0.65, 4.15], label: '3/4 建筑透视' },
  orthographic: { pos: [0, 0, 4.65], label: '正交立面校验 (0.000°)' },
  street: { pos: [-1.75, -0.45, 4.35], label: '低视点街景' },
};

export const TectonicPlane3D: React.FC<TectonicPlane3DProps> = ({
  activeCase,
  activeTier,
  showSeams,
  showPins,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [preset, setPreset] = useState<CameraPreset>('perspective');
  const [wireframeMode, setWireframeMode] = useState(false);
  const [webglFailed, setWebglFailed] = useState(false);

  const targetCamPosRef = useRef(new THREE.Vector3(...CAMERA_PRESETS.perspective.pos));
  const lerpingCamRef = useRef(false);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const facadeMatRef = useRef<THREE.MeshStandardMaterial | null>(null);
  const seamGroupRef = useRef<THREE.Group | null>(null);
  const pinGroupRef = useRef<THREE.Group | null>(null);

  const selectPreset = (next: CameraPreset) => {
    setPreset(next);
    targetCamPosRef.current.set(...CAMERA_PRESETS[next].pos);
    lerpingCamRef.current = true;
  };

  useEffect(() => {
    if (sceneRef.current) {
      sceneRef.current.background = new THREE.Color(isDark ? 0x0b0f19 : 0xf4f6fa);
    }
  }, [isDark]);

  useEffect(() => {
    if (facadeMatRef.current) {
      facadeMatRef.current.wireframe = wireframeMode;
    }
  }, [wireframeMode]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    } catch {
      setWebglFailed(true);
      return;
    }

    const width = container.clientWidth || 680;
    const height = container.clientHeight || 420;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(isDark ? 0x0b0f19 : 0xf4f6fa);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    camera.position.set(...CAMERA_PRESETS.perspective.pos);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = 2.4;
    controls.maxDistance = 9.5;
    controls.addEventListener('start', () => {
      lerpingCamRef.current = false;
    });
    controlsRef.current = controls;

    // Studio directional + hemisphere lights
    const hemi = new THREE.HemisphereLight(0xffffff, isDark ? 0x1e293b : 0xcbd5e1, 1.0);
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.05);
    keyLight.position.set(4, 6, 5);
    scene.add(hemi, keyLight);

    // Subtle ground reference grid
    const grid = new THREE.GridHelper(
      9,
      18,
      isDark ? 0x26324a : 0xcbd5e1,
      isDark ? 0x161f31 : 0xe2e8f0
    );
    grid.position.y = -1.55;
    scene.add(grid);

    // 3D Architectural Facade Slab (4:3 matches 800x600 WebP aspect)
    const slabW = 4.0;
    const slabH = 3.0;
    const slabD = 0.16;

    const texLoader = new THREE.TextureLoader();
    texLoader.setCrossOrigin('anonymous');
    const facadeTex = texLoader.load(activeTier.image_url);
    facadeTex.colorSpace = THREE.SRGBColorSpace;

    const sideMat = new THREE.MeshStandardMaterial({
      color: isDark ? 0x1e293b : 0xdbe2ec,
      roughness: 0.7,
    });
    const frontMat = new THREE.MeshStandardMaterial({
      map: facadeTex,
      roughness: 0.55,
      metalness: 0.05,
      wireframe: wireframeMode,
    });
    facadeMatRef.current = frontMat;

    const slabGeom = new THREE.BoxGeometry(slabW, slabH, slabD);
    const slabMesh = new THREE.Mesh(slabGeom, [
      sideMat,
      sideMat,
      sideMat,
      sideMat,
      frontMat,
      sideMat,
    ]);
    scene.add(slabMesh);

    // 3D Extruded Homography Panel Seam Ribs
    const seamGroup = new THREE.Group();
    seamGroup.visible = showSeams;
    const seamMat = new THREE.MeshBasicMaterial({
      color: isDark ? 0x6085ff : 0x153ce8,
      transparent: true,
      opacity: 0.85,
    });
    const seamGeoms: THREE.BufferGeometry[] = [];
    const segments = activeTier.homography_projection?.seam_segments ?? [];
    for (const seg of segments) {
      const x1 = (seg.start.x / 800 - 0.5) * slabW;
      const y1 = (0.5 - seg.start.y / 600) * slabH;
      const x2 = (seg.end.x / 800 - 0.5) * slabW;
      const y2 = (0.5 - seg.end.y / 600) * slabH;
      const len = Math.hypot(x2 - x1, y2 - y1);
      if (len < 0.005) continue;

      const ribGeom = new THREE.BoxGeometry(len, 0.012, 0.025);
      seamGeoms.push(ribGeom);
      const rib = new THREE.Mesh(ribGeom, seamMat);
      rib.position.set((x1 + x2) / 2, (y1 + y2) / 2, slabD / 2 + 0.014);
      rib.rotation.z = Math.atan2(y2 - y1, x2 - x1);
      seamGroup.add(rib);
    }
    seamGroupRef.current = seamGroup;
    scene.add(seamGroup);

    // 3D Floating Constructability Diagnostic Pins
    const pinGroup = new THREE.Group();
    pinGroup.visible = showPins;
    const pinGeom = new THREE.SphereGeometry(0.065, 16, 16);
    const pinMats: THREE.Material[] = [];
    const pins = activeCase.geometry?.diagnostic_pins_pct ?? [];
    for (const pin of pins) {
      const zoneAlerts = activeTier.alerts.filter((a) => a.zone_id === pin.zone_id);
      const hasBlocking = zoneAlerts.some((a) => a.severity === 'BLOCKING');
      const hasWarning = zoneAlerts.some((a) => a.severity === 'WARNING');
      const colorHex = hasBlocking ? 0xdc2626 : hasWarning ? 0xd97706 : 0x0f766e;

      const pMat = new THREE.MeshStandardMaterial({
        color: colorHex,
        emissive: colorHex,
        emissiveIntensity: 0.4,
      });
      pinMats.push(pMat);
      const mesh = new THREE.Mesh(pinGeom, pMat);
      const px = (pin.x_pct / 100 - 0.5) * slabW;
      const py = (0.5 - pin.y_pct / 100) * slabH;
      mesh.position.set(px, py, slabD / 2 + 0.085);
      pinGroup.add(mesh);
    }
    pinGroupRef.current = pinGroup;
    scene.add(pinGroup);

    const resizeObserver = new ResizeObserver(() => {
      if (!container) return;
      const w = container.clientWidth || 680;
      const h = container.clientHeight || 420;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    resizeObserver.observe(container);

    let rafId = 0;
    const animate = () => {
      rafId = requestAnimationFrame(animate);
      if (lerpingCamRef.current) {
        camera.position.lerp(targetCamPosRef.current, 0.1);
        controls.target.lerp(new THREE.Vector3(0, 0, 0), 0.1);
        if (camera.position.distanceTo(targetCamPosRef.current) < 0.02) {
          lerpingCamRef.current = false;
        }
      }
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      controls.dispose();
      slabGeom.dispose();
      facadeTex.dispose();
      sideMat.dispose();
      frontMat.dispose();
      seamMat.dispose();
      seamGeoms.forEach((g) => g.dispose());
      pinGeom.dispose();
      pinMats.forEach((m) => m.dispose());
      renderer.dispose();
    };
  }, [activeCase, activeTier, isDark, showSeams, showPins, wireframeMode]);

  useEffect(() => {
    if (seamGroupRef.current) seamGroupRef.current.visible = showSeams;
  }, [showSeams]);

  useEffect(() => {
    if (pinGroupRef.current) pinGroupRef.current.visible = showPins;
  }, [showPins]);

  if (webglFailed) {
    return (
      <div className="rounded-lg border border-border bg-secondary/40 p-8 text-center text-xs text-muted-foreground">
        当前浏览器未启用 WebGL，可切换至“实景帘幕对比”或“正交构造 CAD”视图查看完整立面。
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="px-3.5 py-2.5 border-b border-border bg-secondary/40 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge variant="default" className="mono">
            <Box className="w-3 h-3" />
            Three.js 3D 单应性投影平面
          </Badge>
          <span className="mono text-xs text-muted-foreground hidden sm:inline">
            灭点误差 {activeTier.homography_projection.vertical_vanishing_deviation_deg.toFixed(3)}° ·{' '}
            {activeTier.homography_projection.seam_segments.length} 条挤出拼缝
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {(Object.keys(CAMERA_PRESETS) as CameraPreset[]).map((key) => (
            <Button
              key={key}
              type="button"
              size="sm"
              variant={preset === key ? 'default' : 'outline'}
              className="h-7 px-2.5 text-xs"
              onClick={() => selectPreset(key)}
            >
              <Eye className="w-3 h-3" />
              <span>{CAMERA_PRESETS[key].label}</span>
            </Button>
          ))}
          <Button
            type="button"
            size="sm"
            variant={wireframeMode ? 'secondary' : 'outline'}
            className="h-7 px-2.5 text-xs"
            onClick={() => setWireframeMode((v) => !v)}
          >
            <Layers className="w-3 h-3" />
            <span>网格线框</span>
          </Button>
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-7 w-7"
            onClick={() => selectPreset('perspective')}
            aria-label="重置 3D 立面视角"
          >
            <RotateCcw className="w-3 h-3" />
          </Button>
        </div>
      </div>

      <div className="relative h-[380px] sm:h-[460px] w-full">
        <div
          ref={containerRef}
          className="h-full w-full"
          aria-label="TectonicLoop 3D 商业立面单应性投影画布"
        />
        <div className="pointer-events-none absolute bottom-3 left-3 rounded-md border border-border/80 bg-card/85 backdrop-blur-md px-2.5 py-1 text-xs text-muted-foreground shadow-sm">
          拖拽旋转建筑立面 · 滚轮缩放检视预制板模数缝与排雷针脚（红=阻断 / 琥珀=警告 / 青=通过）
        </div>
      </div>
    </div>
  );
};
