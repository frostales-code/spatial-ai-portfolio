import React from 'react';
import { X } from 'lucide-react';
import type { SpectrumAxisId } from '../engine/salienceMetric';
import type { AxisCalibrationRubric, CuratedShowcaseAsset } from '../types/aethervault';

interface GoldenAnchorDrawerProps {
  rubric: AxisCalibrationRubric | null;
  currentValue: number;
  assetsById: Record<string, CuratedShowcaseAsset>;
  onApplyAnchorLevel: (axisId: SpectrumAxisId, level: number) => void;
  onClose: () => void;
}

export const GoldenAnchorDrawer: React.FC<GoldenAnchorDrawerProps> = ({
  rubric,
  currentValue,
  assetsById,
  onApplyAnchorLevel,
  onClose,
}) => {
  if (!rubric) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="golden-anchor-title"
      onClick={onClose}
      className="fixed inset-0 z-50 bg-[#0E1015]/65 backdrop-blur-[2px] flex items-center justify-center p-3 sm:p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#FFFFFF] border border-[#0E1015] max-w-6xl w-full max-h-[90vh] flex flex-col overflow-hidden"
      >
        <div className="px-5 py-4 border-b border-[#E2E5EA] flex items-start justify-between gap-4 bg-[#FFFFFF]">
          <div className="space-y-1">
            <h3 id="golden-anchor-title" className="font-display text-lg font-bold text-[#0E1015]">
              {rubric.label_zh} · 5 点黄金锚点标尺（{rubric.neg_label} ↔ {rubric.pos_label}）
            </h3>
            <p className="text-xs text-[#525866]">
              <span className="font-semibold text-[#0F766E]">显著度门控规则：</span>
              {rubric.salience_gating_rule}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭黄金锚点标尺"
            className="w-10 h-10 shrink-0 border border-[#E2E5EA] hover:border-[#0E1015] text-[#0E1015] flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4" strokeWidth={1.75} />
          </button>
        </div>

        <div className="p-5 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {rubric.anchors.map((pt) => {
            const refAsset = assetsById[pt.reference_asset_id];
            const isNearCurrent = Math.abs(currentValue - pt.level) < 0.25;
            const formattedLevel = pt.level > 0 ? `+${pt.level.toFixed(1)}` : pt.level.toFixed(1);
            return (
              <div
                key={pt.level}
                className={`border flex flex-col justify-between bg-[#FFFFFF] ${
                  isNearCurrent ? 'border-[#153CE8]' : 'border-[#E2E5EA]'
                }`}
              >
                <div>
                  <div className="aspect-[4/3] bg-[#F4F5F7] overflow-hidden">
                    {refAsset ? (
                      <img
                        src={refAsset.image_url}
                        alt={pt.anchor_title_zh}
                        className="w-full h-full object-cover"
                      />
                    ) : null}
                  </div>
                  <div className="p-3.5 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span
                        className={`mono font-semibold tabular-nums ${
                          isNearCurrent ? 'text-[#153CE8]' : 'text-[#0E1015]'
                        }`}
                      >
                        档位 {formattedLevel}
                      </span>
                      <span className="mono text-[#525866]">{pt.reference_asset_id}</span>
                    </div>
                    <div className="text-sm font-semibold text-[#0E1015]">{pt.anchor_title_zh}</div>
                    <p className="text-xs text-[#525866] leading-relaxed">
                      {pt.physical_visual_criteria}
                    </p>
                    <p className="text-xs text-[#525866] border-t border-[#E2E5EA] pt-2 leading-relaxed">
                      跨界示例：{pt.cross_domain_examples}
                    </p>
                  </div>
                </div>
                <div className="p-3 border-t border-[#E2E5EA] bg-[#F4F5F7]">
                  <button
                    type="button"
                    onClick={() => {
                      onApplyAnchorLevel(rubric.axis_id, pt.level);
                      onClose();
                    }}
                    className={`w-full min-h-[36px] text-xs font-semibold border transition-colors ${
                      isNearCurrent
                        ? 'bg-[#153CE8] border-[#153CE8] text-[#FFFFFF]'
                        : 'bg-[#FFFFFF] border-[#E2E5EA] text-[#0E1015] hover:border-[#153CE8] hover:text-[#153CE8]'
                    }`}
                  >
                    对齐至此档位 ({formattedLevel})
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
