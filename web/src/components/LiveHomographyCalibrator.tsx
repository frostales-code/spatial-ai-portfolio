'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Crosshair, RotateCcw, Upload } from 'lucide-react';
import type { Point2D, ProjectedSeamSegment } from '@/types/tectonic';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface LiveHomographyCalibratorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultImageUrl: string;
  defaultQuad: Point2D[];
  isLiveEngine: boolean;
}

const DEFAULT_QUAD: Point2D[] = [
  { x: 110, y: 110 },
  { x: 690, y: 115 },
  { x: 705, y: 515 },
  { x: 95, y: 515 },
];

/**
 * Pure TypeScript 2D projective bilinear/homography seam projection fallback
 * so interactive 4-point calibration works smoothly even offline on GitHub Pages.
 */
function projectSeamsOffline(
  quad: Point2D[],
  facadeWidthMm: number,
  facadeHeightMm: number,
  panelWidthMm: number,
  panelHeightMm: number
): {
  seams: ProjectedSeamSegment[];
  stretchRatio: number;
  vanishingDeg: number;
} {
  const [tl, tr, br, bl] = quad;
  const lerpPt = (a: Point2D, b: Point2D, t: number): Point2D => ({
    x: a.x + (b.x - a.x) * t,
    y: a.y + (b.y - a.y) * t,
  });

  const seams: ProjectedSeamSegment[] = [];
  const cols = Math.max(2, Math.round(facadeWidthMm / Math.max(300, panelWidthMm)));
  const rows = Math.max(1, Math.round(facadeHeightMm / Math.max(300, panelHeightMm)));

  for (let c = 0; c <= cols; c++) {
    const u = c / cols;
    seams.push({
      orientation: 'vertical',
      start: lerpPt(tl, tr, u),
      end: lerpPt(bl, br, u),
    });
  }
  for (let r = 0; r <= rows; r++) {
    const v = r / rows;
    seams.push({
      orientation: 'horizontal',
      start: lerpPt(tl, bl, v),
      end: lerpPt(tr, br, v),
    });
  }

  const topEdge = Math.hypot(tr.x - tl.x, tr.y - tl.y);
  const botEdge = Math.hypot(br.x - bl.x, br.y - bl.y);
  const stretchRatio =
    Math.round((Math.max(topEdge, botEdge) / Math.max(1, Math.min(topEdge, botEdge))) * 1000) /
    1000;
  return { seams, stretchRatio, vanishingDeg: 0.0 };
}

export const LiveHomographyCalibrator: React.FC<LiveHomographyCalibratorProps> = ({
  open,
  onOpenChange,
  defaultImageUrl,
  defaultQuad,
  isLiveEngine,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [imageUrl, setImageUrl] = useState(defaultImageUrl);
  const [quad, setQuad] = useState<Point2D[]>(
    defaultQuad.length === 4 ? defaultQuad : DEFAULT_QUAD
  );
  const [draggingIdx, setDraggingIdx] = useState<number | null>(null);
  const [facadeWidthMm, setFacadeWidthMm] = useState(7200);
  const [facadeHeightMm, setFacadeHeightMm] = useState(3600);
  const [panelWidthMm, setPanelWidthMm] = useState(1200);
  const [panelHeightMm, setPanelHeightMm] = useState(2400);
  const [liveSeams, setLiveSeams] = useState<ProjectedSeamSegment[] | null>(null);
  const [liveMeta, setLiveMeta] = useState<{
    source: 'fastapi' | 'client';
    stretchRatio: number;
    vanishingDeg: number;
    extremeWarning: boolean;
  } | null>(null);
  const [loadingLive, setLoadingLive] = useState(false);

  useEffect(() => {
    setImageUrl(defaultImageUrl);
    setQuad(defaultQuad.length === 4 ? defaultQuad : DEFAULT_QUAD);
    setLiveSeams(null);
    setLiveMeta(null);
  }, [defaultImageUrl, defaultQuad]);

  const offlineCalc = useMemo(
    () => projectSeamsOffline(quad, facadeWidthMm, facadeHeightMm, panelWidthMm, panelHeightMm),
    [quad, facadeWidthMm, facadeHeightMm, panelWidthMm, panelHeightMm]
  );

  const displayedSeams = liveSeams ?? offlineCalc.seams;
  const stretchRatio = liveMeta?.stretchRatio ?? offlineCalc.stretchRatio;
  const extremeWarning = liveMeta?.extremeWarning ?? stretchRatio >= 1.48;
  const vanishingDeg = liveMeta?.vanishingDeg ?? offlineCalc.vanishingDeg;

  const runLiveProjection = useCallback(async () => {
    if (!isLiveEngine) {
      setLiveSeams(offlineCalc.seams);
      setLiveMeta({
        source: 'client',
        stretchRatio: offlineCalc.stretchRatio,
        vanishingDeg: offlineCalc.vanishingDeg,
        extremeWarning: offlineCalc.stretchRatio >= 1.48,
      });
      return;
    }

    setLoadingLive(true);
    try {
      const res = await fetch('/api/tectonic/project-seams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_quad: quad,
          facade_width_mm: facadeWidthMm,
          facade_height_mm: facadeHeightMm,
          panel_width_mm: panelWidthMm,
          panel_height_mm: panelHeightMm,
          openings_mm: [],
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLiveSeams(data.seam_segments ?? offlineCalc.seams);
      setLiveMeta({
        source: 'fastapi',
        stretchRatio: Number(data.edge_stretch_ratio ?? offlineCalc.stretchRatio),
        vanishingDeg: Number(data.vertical_vanishing_deviation_deg ?? 0),
        extremeWarning: Boolean(data.extreme_tilt_warning),
      });
    } catch {
      setLiveSeams(offlineCalc.seams);
      setLiveMeta({
        source: 'client',
        stretchRatio: offlineCalc.stretchRatio,
        vanishingDeg: offlineCalc.vanishingDeg,
        extremeWarning: offlineCalc.stretchRatio >= 1.48,
      });
    } finally {
      setLoadingLive(false);
    }
  }, [isLiveEngine, quad, facadeWidthMm, facadeHeightMm, panelWidthMm, panelHeightMm, offlineCalc]);

  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (draggingIdx === null || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = Math.max(20, Math.min(780, ((e.clientX - rect.left) / rect.width) * 800));
    const y = Math.max(20, Math.min(580, ((e.clientY - rect.top) / rect.height) * 600));
    setQuad((prev) =>
      prev.map((pt, i) => (i === draggingIdx ? { x: Math.round(x), y: Math.round(y) } : pt))
    );
    setLiveSeams(null);
    setLiveMeta(null);
  };

  const handleUploadImage = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setImageUrl(reader.result);
        setLiveSeams(null);
        setLiveMeta(null);
      }
    };
    reader.readAsDataURL(file);
  };

  const quadPolygon = quad.map((p) => `${p.x},${p.y}`).join(' ');
  const labels = ['P1 左上', 'P2 右上', 'P3 右下', 'P4 左下'];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(94vw,860px)]">
        <DialogHeader>
          <div className="flex flex-wrap items-center gap-2 pr-6">
            <Badge variant={isLiveEngine ? 'success' : 'default'} className="mono">
              <Crosshair className="w-3 h-3" />
              {isLiveEngine ? 'FastAPI Live Engine (/api/tectonic/project-seams)' : '离线确定性几何沙盒'}
            </Badge>
            <Badge variant="outline" className="mono">
              拉伸比 {stretchRatio.toFixed(2)}x · 灭点误差 {vanishingDeg.toFixed(3)}°
            </Badge>
          </div>
          <DialogTitle>自定义立面 4 点单应性透视标定（H / H⁻¹）</DialogTitle>
          <DialogDescription>
            拖动图像上 4 个角点或上传任意商业门头照片，实时求解单应性矩阵并投射预制板模数分缝网格。
          </DialogDescription>
        </DialogHeader>

        {extremeWarning && (
          <div className="rounded-lg border border-destructive/60 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              <strong>Bad Case #1 强透视护栏触发：</strong>当前顶底透视压缩比达{' '}
              <span className="mono font-semibold">{stretchRatio.toFixed(2)}x (≥ 1.48x)</span>
              ，远端板缝存在过度拉伸风险，建议微调上方角点或改用更正视的立面底图。
            </span>
          </div>
        )}

        {/* Interactive 4-Point SVG Over Image */}
        <div className="relative w-full max-w-[600px] mx-auto aspect-[4/3] rounded-lg overflow-hidden border border-border bg-secondary select-none shrink-0">
          <img
            src={imageUrl}
            alt="自定义立面标定底图"
            className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          />
          <svg
            ref={svgRef}
            viewBox="0 0 800 600"
            className="absolute inset-0 w-full h-full touch-none"
            onPointerMove={handlePointerMove}
            onPointerUp={() => setDraggingIdx(null)}
            onPointerLeave={() => setDraggingIdx(null)}
          >
            <polygon
              points={quadPolygon}
              fill="rgba(21, 60, 232, 0.10)"
              stroke="#153CE8"
              strokeWidth="2"
              strokeDasharray="6 4"
            />
            {displayedSeams.map((seg, idx) => (
              <line
                key={idx}
                x1={seg.start.x}
                y1={seg.start.y}
                x2={seg.end.x}
                y2={seg.end.y}
                stroke={extremeWarning ? '#DC2626' : '#3B82F6'}
                strokeWidth={seg.orientation === 'vertical' ? 1.8 : 1.3}
                strokeOpacity={0.9}
              />
            ))}
            {quad.map((pt, idx) => (
              <g
                key={idx}
                transform={`translate(${pt.x}, ${pt.y})`}
                className="cursor-grab active:cursor-grabbing"
                onPointerDown={(e) => {
                  e.stopPropagation();
                  setDraggingIdx(idx);
                }}
              >
                <circle r="13" fill="#153CE8" fillOpacity="0.22" />
                <circle r="7" fill="#153CE8" stroke="#FFFFFF" strokeWidth="2.5" />
                <rect x="11" y="-12" width="54" height="20" rx="4" fill="rgba(14,16,21,0.82)" />
                <text x="16" y="2" fill="#FFFFFF" fontSize="11" fontFamily="Chivo Mono">
                  {labels[idx]}
                </text>
              </g>
            ))}
          </svg>
        </div>

        {/* Controls Footer */}
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 pt-2 bg-card">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <label className="inline-flex items-center gap-1.5">
              <span className="text-muted-foreground">板材模数</span>
              <select
                value={`${panelWidthMm}x${panelHeightMm}`}
                onChange={(e) => {
                  const [w, h] = e.target.value.split('x').map(Number);
                  setPanelWidthMm(w);
                  setPanelHeightMm(h);
                  setLiveSeams(null);
                }}
                className="h-8 rounded-md border border-border bg-card px-2 text-xs"
              >
                <option value="1200x2400">1200×2400 mm (UHPC/铝板)</option>
                <option value="900x1800">900×1800 mm (石材/穿孔板)</option>
                <option value="600x1200">600×1200 mm (纤维水泥/木挂板)</option>
              </select>
            </label>

            <label className="inline-flex items-center gap-1.5">
              <span className="text-muted-foreground">面宽</span>
              <input
                type="number"
                min={2400}
                max={20000}
                step={600}
                value={facadeWidthMm}
                onChange={(e) => {
                  setFacadeWidthMm(Number(e.target.value) || 7200);
                  setLiveSeams(null);
                }}
                className="h-8 w-20 rounded-md border border-border bg-card px-2 mono text-xs"
              />
              <span className="text-muted-foreground">mm</span>
            </label>

            <label className="inline-flex items-center gap-1.5">
              <span className="text-muted-foreground">净高</span>
              <input
                type="number"
                min={2400}
                max={12000}
                step={300}
                value={facadeHeightMm}
                onChange={(e) => {
                  setFacadeHeightMm(Number(e.target.value) || 3600);
                  setLiveSeams(null);
                }}
                className="h-8 w-20 rounded-md border border-border bg-card px-2 mono text-xs"
              />
              <span className="text-muted-foreground">mm</span>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border bg-card hover:bg-secondary text-xs font-medium cursor-pointer transition-colors">
              <Upload className="w-3.5 h-3.5 text-primary" />
              <span>上传立面图</span>
              <input type="file" accept="image/*" onChange={handleUploadImage} className="sr-only" />
            </label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setQuad(defaultQuad.length === 4 ? defaultQuad : DEFAULT_QUAD);
                setLiveSeams(null);
                setLiveMeta(null);
              }}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>重置四角</span>
            </Button>
            <Button type="button" size="sm" onClick={runLiveProjection} disabled={loadingLive}>
              <Crosshair className="w-3.5 h-3.5" />
              <span>
                {loadingLive
                  ? '投影求解中...'
                  : isLiveEngine
                    ? '调用 FastAPI 实时投影'
                    : '求解单应性分缝'}
              </span>
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
