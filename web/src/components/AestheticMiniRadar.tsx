'use client';

import React, { useMemo } from 'react';
import { ALL_AXIS_IDS, type SpectrumAxisId } from '@/engine/salienceMetric';

const AXIS_SHORT_ZH: Record<SpectrumAxisId, string> = {
  tectonic_honesty: '构造诚实',
  surface_entropy: '肌理时间',
  spatial_density: '空间留白',
  geometric_order: '几何秩序',
  lighting_drama: '光影反差',
  chromatic_tension: '色彩张力',
  thermal_mood: '情绪色温',
  reality_abstraction: '抽象程度',
};

interface AestheticMiniRadarProps {
  primaryScores: Partial<Record<SpectrumAxisId, number>>;
  baselineScores?: Partial<Record<SpectrumAxisId, number>>;
  primaryLabel?: string;
  baselineLabel?: string;
  sizeClass?: string;
}

export const AestheticMiniRadar: React.FC<AestheticMiniRadarProps> = ({
  primaryScores,
  baselineScores,
  primaryLabel = '本图光谱',
  baselineLabel = '个人审美均值',
  sizeClass = 'w-full max-w-[240px]',
}) => {
  const geom = useMemo(() => {
    const cx = 135;
    const cy = 104;
    const maxR = 64;
    const n = ALL_AXIS_IDS.length;

    const toPolygon = (scores: Partial<Record<SpectrumAxisId, number>>) =>
      ALL_AXIS_IDS.map((axisId, i) => {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        const val = scores[axisId] ?? 0;
        const norm = (val + 1) / 2;
        const rVal = maxR * (0.18 + 0.82 * norm);
        const px = cx + rVal * Math.cos(angle);
        const py = cy + rVal * Math.sin(angle);
        return { px, py };
      });

    const axes = ALL_AXIS_IDS.map((axisId, i) => {
      const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
      return {
        axisId,
        label: AXIS_SHORT_ZH[axisId],
        xEnd: cx + maxR * Math.cos(angle),
        yEnd: cy + maxR * Math.sin(angle),
        lx: cx + (maxR + 25) * Math.cos(angle),
        ly: cy + (maxR + 17) * Math.sin(angle),
      };
    });

    const primaryPts = toPolygon(primaryScores);
    const baselinePts = baselineScores ? toPolygon(baselineScores) : null;

    return {
      cx,
      cy,
      maxR,
      axes,
      primaryPts,
      primaryPoly: primaryPts.map((p) => `${p.px.toFixed(1)},${p.py.toFixed(1)}`).join(' '),
      baselinePoly: baselinePts
        ? baselinePts.map((p) => `${p.px.toFixed(1)},${p.py.toFixed(1)}`).join(' ')
        : null,
    };
  }, [primaryScores, baselineScores]);

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 270 208" className={`${sizeClass} h-auto select-none`} role="img" aria-label="8 轴审美光谱微缩雷达图">
        {[0.3, 0.65, 1.0].map((rFactor) => (
          <circle
            key={rFactor}
            cx={geom.cx}
            cy={geom.cy}
            r={geom.maxR * rFactor}
            fill="none"
            stroke="hsl(var(--border))"
            strokeWidth="1"
            strokeDasharray={rFactor === 0.65 ? '3 3' : undefined}
          />
        ))}
        {geom.axes.map((ax) => (
          <line
            key={ax.axisId}
            x1={geom.cx}
            y1={geom.cy}
            x2={ax.xEnd}
            y2={ax.yEnd}
            stroke="hsl(var(--border))"
            strokeWidth="0.9"
          />
        ))}
        {geom.baselinePoly && (
          <polygon
            points={geom.baselinePoly}
            fill="hsl(var(--muted-foreground) / 0.1)"
            stroke="hsl(var(--muted-foreground))"
            strokeWidth="1.25"
            strokeDasharray="3 3"
          />
        )}
        <polygon
          points={geom.primaryPoly}
          fill="hsl(var(--primary) / 0.18)"
          stroke="hsl(var(--primary))"
          strokeWidth="1.75"
        />
        {geom.primaryPts.map((pt, idx) => (
          <circle key={idx} cx={pt.px} cy={pt.py} r="2.6" fill="hsl(var(--primary))" />
        ))}
        {geom.axes.map((ax) => (
          <text
            key={ax.axisId}
            x={ax.lx}
            y={ax.ly}
            fill="hsl(var(--foreground))"
            fontSize="10.2"
            fontWeight="600"
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {ax.label}
          </text>
        ))}
      </svg>

      {baselineScores && (
        <div className="mt-1 flex items-center justify-center gap-4 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 h-0.5 bg-primary" />
            <span>{primaryLabel}</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 border-t border-dashed border-muted-foreground" />
            <span>{baselineLabel}</span>
          </span>
        </div>
      )}
    </div>
  );
};
