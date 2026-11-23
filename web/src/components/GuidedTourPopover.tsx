'use client';

import React, { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, X } from 'lucide-react';
import type { MainTabId } from '@/components/ThesisOverview';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export interface GuidedTourStop {
  id: string;
  stopLabel: string;
  tab: MainTabId;
  title: string;
  aiBoundary: string;
  body: string;
  nextLabel: string;
}

export const GUIDED_TOUR_STOPS: GuidedTourStop[] = [
  {
    id: 'tour_aethervault',
    stopLabel: '01 / 04 · 3D 美学流形与 AST',
    tab: 'projectA',
    title: 'AetherVault：8 轴 3D 流形 × Zero-Drift AST',
    aiBoundary: 'VLM 仅负责冷启动离线打标；滑块拖拽触发 <20ms 纯前端加权欧氏重排并实时驱动 Three.js 探针。',
    body: '可切换「3D 美学流形」旋转观察 80 件跨门类标本与 Top-6 相似连线，或在首屏帘幕核查 AST 编译与多图直喂的防泄漏效果。',
    nextLabel: '下一站：双引擎方法论',
  },
  {
    id: 'tour_thesis',
    stopLabel: '02 / 04 · 产品边界与架构演进',
    tab: 'thesis',
    title: 'AI vs Non-AI 克制边界与双闭环协同',
    aiBoundary: '能用确定性数学、几何矩阵与规则引擎解决的问题，绝不交给大语言模型。',
    body: '承接 02-aurora 的 Decimal 精密算账与 03-super-agent 的人机确认门禁：上游锁死跨界风格正交，下游用物理排雷与精准算账接住视觉渲染。',
    nextLabel: '下一站：TectonicLoop 3D',
  },
  {
    id: 'tour_tectonic',
    stopLabel: '03 / 04 · 3D 立面投影与 VE 账本',
    tab: 'projectB',
    title: 'TectonicLoop：实景帘幕 × Three.js 单应性平面',
    aiBoundary: '透视投影偏差 0.000°（几何求解）与 8 项造价算账均由 Zero-LLM 确定性引擎执行。',
    body: '切换「3D 单应性投影」旋转查看挤出板缝与排雷针脚，对比三档造价落图，并导出甲方 VE 任务书与 8 幅构造大样。',
    nextLabel: '下一站：交互评测基准',
  },
  {
    id: 'tour_eval',
    stopLabel: '04 / 04 · Recharts 评测与成本账本',
    tab: 'techEval',
    title: 'EDD 交互评测：¥0.00596/图与 80/80 全通过',
    aiBoundary: '未知单价诚实报错 UNKNOWN_PRICE_MISSING，绝不臆造 0 值，全量指标以交互图表可溯源核验。',
    body: '查看 8 轴 Spearman ρ 雷达对比图、千张级冷启动成本曲线与 3 套商业案例的 PSNR ≥ 38 dB 保真度评测。',
    nextLabel: '完成 3 分钟导览',
  },
];

interface GuidedTourPopoverProps {
  isOpen: boolean;
  stepIndex: number;
  onSelectStep: (index: number) => void;
  onClose: () => void;
}

export const GuidedTourPopover: React.FC<GuidedTourPopoverProps> = ({
  isOpen,
  stepIndex,
  onSelectStep,
  onClose,
}) => {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const safeIndex = Math.max(0, Math.min(stepIndex, GUIDED_TOUR_STOPS.length - 1));
  const current = GUIDED_TOUR_STOPS[safeIndex];
  const isLast = safeIndex === GUIDED_TOUR_STOPS.length - 1;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.aside
          role="dialog"
          aria-label="3 分钟作品集导览"
          initial={{ opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 12, scale: 0.98 }}
          transition={{ duration: 0.18 }}
          className="fixed bottom-4 right-4 z-50 w-[min(400px,calc(100vw-2rem))] rounded-xl border border-border bg-card/95 backdrop-blur-md shadow-2xl overflow-hidden"
        >
          <div className="px-4 py-2.5 border-b border-border bg-secondary/60 flex items-center justify-between gap-3">
            <Badge variant="default" className="mono text-xs">
              {current.stopLabel}
            </Badge>
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭导览"
              className="inline-flex items-center justify-center w-6 h-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.75} />
            </button>
          </div>

          <div className="p-4 space-y-3">
            <h3 className="font-display text-sm font-bold text-foreground leading-snug">
              {current.title}
            </h3>
            <p className="text-xs leading-relaxed text-muted-foreground">{current.body}</p>
            <div className="px-3 py-2 rounded-lg bg-secondary/70 border border-border text-xs leading-relaxed text-foreground">
              <span className="mono font-semibold text-primary mr-1.5">AI BOUNDARY</span>
              {current.aiBoundary}
            </div>
          </div>

          <div className="px-4 py-3 border-t border-border flex items-center justify-between gap-2 bg-card">
            <div className="flex items-center gap-1.5" role="group" aria-label="导览步骤切换">
              {GUIDED_TOUR_STOPS.map((stop, idx) => {
                const active = idx === safeIndex;
                return (
                  <button
                    key={stop.id}
                    type="button"
                    onClick={() => onSelectStep(idx)}
                    aria-label={`跳至第 ${idx + 1} 站：${stop.title}`}
                    className={`h-2 rounded-full transition-all ${
                      active ? 'w-5 bg-primary' : 'w-2 bg-border hover:bg-muted-foreground'
                    }`}
                  />
                );
              })}
            </div>

            <Button
              type="button"
              size="sm"
              onClick={() => (isLast ? onClose() : onSelectStep(safeIndex + 1))}
            >
              <span>{current.nextLabel}</span>
              <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.75} />
            </Button>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
};
