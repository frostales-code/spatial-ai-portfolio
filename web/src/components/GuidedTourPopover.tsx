import React, { useEffect } from 'react';
import { ArrowRight, X } from 'lucide-react';
import type { MainTabId } from './ThesisOverview';

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
    stopLabel: '01 / 04 · 跨域光谱检索与 AST',
    tab: 'projectA',
    title: 'AetherVault：8 轴连续重排 × Zero-Drift AST',
    aiBoundary: 'VLM 仅负责冷启动离线打标；滑块拖拽触发 <20ms 纯前端加权欧氏重排。',
    body: '拖拽任意滑块即可在 80 件跨建筑、工业、平面、器物与摄影样张中实时重排；点开“对比模式”可核查 AST 编译与直接多图直喂的实体泄漏差异。',
    nextLabel: '下一站：查看双引擎方法论',
  },
  {
    id: 'tour_thesis',
    stopLabel: '02 / 04 · 产品边界与成本总览',
    tab: 'thesis',
    title: 'AI vs Non-AI 克制边界与双闭环协同',
    aiBoundary: '能用确定性数学、几何矩阵与规则引擎解决的问题，绝不交给大语言模型。',
    body: '从 02-aurora 的 Decimal 算账与 03-super-agent 的人类确认门禁演进而来：上游锁死跨界风格正交，下游用规则排雷与精准算账接住视觉渲染。',
    nextLabel: '下一站：进入 TectonicLoop',
  },
  {
    id: 'tour_tectonic',
    stopLabel: '03 / 04 · 立面改造与 VE 账本',
    tab: 'projectB',
    title: 'TectonicLoop：实景帘幕对比 × H/H⁻¹ 单应性落图',
    aiBoundary: '透视投影偏差 0.000°（几何求解）与 8 项造价算账均由 Zero-LLM 确定性引擎执行。',
    body: '拖动商业立面 Before/After 帘幕，切换高定/均衡/降本造价三档，或展开 8 个构造大样图与 VE 参数滑块验证单方造价与工期联动。',
    nextLabel: '下一站：核验评测基准',
  },
  {
    id: 'tour_eval',
    stopLabel: '04 / 04 · 量化评测与冷启动账本',
    tab: 'techEval',
    title: 'EDD 评测体系：¥0.00596/图与 80/80 契约校验',
    aiBoundary: '未知单价诚实报错 UNKNOWN_PRICE_MISSING，绝不臆造 0 值，全量跑分可复现。',
    body: '查看冷启动单图成本对比（在线 ¥0.00596/图、Batch 等效 ¥0.00298/图）、Prompt Cache 49.25% 命中率与非掩码区 PSNR ≥ 38 dB 保真指标。',
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

  if (!isOpen) return null;

  const safeIndex = Math.max(0, Math.min(stepIndex, GUIDED_TOUR_STOPS.length - 1));
  const current = GUIDED_TOUR_STOPS[safeIndex];
  const isLast = safeIndex === GUIDED_TOUR_STOPS.length - 1;

  return (
    <aside
      role="dialog"
      aria-label="3 分钟作品集导览"
      className="fixed bottom-4 right-4 z-50 w-[min(392px,calc(100vw-2rem))] bg-[#FFFFFF] border border-[#0E1015] shadow-[0_12px_32px_rgba(14,16,21,0.12)]"
    >
      <div className="px-4 py-2.5 border-b border-[#E2E5EA] bg-[#F4F5F7] flex items-center justify-between gap-3">
        <span className="font-mono text-xs font-medium uppercase tracking-[0.06em] text-[#153CE8]">
          {current.stopLabel}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭导览"
          className="inline-flex items-center justify-center w-6 h-6 text-[#525866] hover:text-[#0E1015] hover:bg-[#E2E5EA]/60 transition-colors"
        >
          <X className="w-3.5 h-3.5" strokeWidth={1.75} />
        </button>
      </div>

      <div className="p-4 space-y-3">
        <h3 className="font-display text-sm font-bold text-[#0E1015] leading-snug">
          {current.title}
        </h3>
        <p className="text-xs leading-relaxed text-[#525866]">{current.body}</p>
        <div className="px-3 py-2 bg-[#F4F5F7] border border-[#E2E5EA] text-xs leading-relaxed text-[#0E1015]">
          <span className="font-mono text-xs font-medium text-[#153CE8] mr-1.5">BOUNDARY</span>
          {current.aiBoundary}
        </div>
      </div>

      <div className="px-4 py-3 border-t border-[#E2E5EA] flex items-center justify-between gap-2 bg-[#FFFFFF]">
        <div className="flex items-center gap-1.5" role="group" aria-label="导览步骤切换">
          {GUIDED_TOUR_STOPS.map((stop, idx) => {
            const active = idx === safeIndex;
            return (
              <button
                key={stop.id}
                type="button"
                onClick={() => onSelectStep(idx)}
                aria-label={`跳至第 ${idx + 1} 站：${stop.title}`}
                className={`h-2 transition-all ${
                  active ? 'w-5 bg-[#153CE8]' : 'w-2 bg-[#E2E5EA] hover:bg-[#525866]'
                }`}
              />
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => (isLast ? onClose() : onSelectStep(safeIndex + 1))}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#153CE8] hover:bg-[#0E2BB5] text-white text-xs font-semibold transition-colors"
        >
          <span>{current.nextLabel}</span>
          <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.75} />
        </button>
      </div>
    </aside>
  );
};
