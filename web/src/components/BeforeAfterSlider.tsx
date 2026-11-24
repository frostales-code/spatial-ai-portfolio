'use client';

import React, { useRef, useState } from 'react';
import { ArrowLeftRight } from 'lucide-react';

interface BeforeAfterSliderProps {
  beforeSrc: string;
  afterSrc: string;
  beforeAlt: string;
  afterAlt: string;
  beforeLabel?: string;
  afterLabel?: string;
  overlay?: React.ReactNode;
}

export const BeforeAfterSlider: React.FC<BeforeAfterSliderProps> = ({
  beforeSrc,
  afterSrc,
  beforeAlt,
  afterAlt,
  beforeLabel = '基线 · 多图直喂',
  afterLabel = 'AetherVault · AST 正交编译',
  overlay,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [position, setPosition] = useState(50);
  const [dragging, setDragging] = useState(false);

  const updateFromClientX = (clientX: number) => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const pct = ((clientX - rect.left) / Math.max(1, rect.width)) * 100;
    setPosition(Math.max(4, Math.min(96, Math.round(pct * 10) / 10)));
  };

  return (
    <div className="space-y-3">
      <div
        ref={containerRef}
        role="slider"
        tabIndex={0}
        aria-label="左右拖拽对比基线直喂与 AST 编译效果"
        aria-valuemin={4}
        aria-valuemax={96}
        aria-valuenow={Math.round(position)}
        data-testid="before-after-curtain"
        onPointerDown={(e) => {
          setDragging(true);
          e.currentTarget.setPointerCapture(e.pointerId);
          updateFromClientX(e.clientX);
        }}
        onPointerMove={(e) => {
          if (dragging) updateFromClientX(e.clientX);
        }}
        onPointerUp={(e) => {
          setDragging(false);
          if (e.currentTarget.hasPointerCapture(e.pointerId)) {
            e.currentTarget.releasePointerCapture(e.pointerId);
          }
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') setPosition((p) => Math.max(4, p - 4));
          if (e.key === 'ArrowRight') setPosition((p) => Math.min(96, p + 4));
          if (e.key === 'Home') setPosition(10);
          if (e.key === 'End') setPosition(90);
        }}
        className="relative w-full aspect-[4/3] rounded-xl overflow-hidden border border-border bg-secondary/60 shadow-sm select-none cursor-ew-resize touch-none"
      >
        {/* Right / Base Layer: AST Compiled */}
        <img
          src={afterSrc}
          alt={afterAlt}
          draggable={false}
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
        />

        {/* Left / Clipped Layer: Baseline Naive Multi-Image */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
        >
          <img
            src={beforeSrc}
            alt={beforeAlt}
            draggable={false}
            className="w-full h-full object-cover"
          />
        </div>

        {/* Optional SVG Seam & Interactive Diagnostic Pin Overlay */}
        {overlay && (
          <div className="absolute inset-0 pointer-events-none z-10">{overlay}</div>
        )}

        {/* Crisp Polarity Labels */}
        <span className="absolute top-3 left-3 z-20 rounded-md px-2 sm:px-2.5 py-1 max-w-[45%] truncate bg-black/80 backdrop-blur-sm text-white text-[11px] sm:text-xs font-medium pointer-events-none">
          {beforeLabel}
        </span>
        <span className="absolute top-3 right-3 z-20 rounded-md px-2 sm:px-2.5 py-1 max-w-[45%] truncate bg-primary text-primary-foreground text-[11px] sm:text-xs font-medium pointer-events-none">
          {afterLabel}
        </span>

        {/* Divider Line & Tactile Cobalt Handle */}
        <div
          className="absolute top-0 bottom-0 z-20 w-0.5 bg-card pointer-events-none"
          style={{ left: `${position}%` }}
        >
          <div className="absolute inset-y-0 -left-px w-0.5 bg-primary/80" />
          <div className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-primary text-primary-foreground border-2 border-white flex items-center justify-center shadow-md">
            <ArrowLeftRight className="w-4 h-4" strokeWidth={1.75} />
          </div>
        </div>
      </div>

      {/* Accessible Full-Width Scrub Control */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="font-medium text-foreground truncate">{beforeLabel}</span>
          <span className="font-semibold text-primary truncate">{afterLabel}</span>
        </div>
        <input
          type="range"
          min={4}
          max={96}
          step={1}
          value={Math.round(position)}
          aria-label="拖动滑块调整对比帘幕位置"
          onChange={(e) => setPosition(parseFloat(e.target.value))}
          className="w-full block"
        />
      </div>
    </div>
  );
};
