'use client';

import React from 'react';
import { ArrowLeft, RotateCcw, X } from 'lucide-react';
import type { SpectrumAxisId } from '../engine/salienceMetric';
import type { CuratedShowcaseAsset } from '../types/aethervault';

export interface CalibrationChoiceOption {
  id: 'A' | 'B';
  assetId: string;
  headline: string;
  rationale: string;
  targetDelta: Partial<Record<SpectrumAxisId, number>>;
  boostWeights: Partial<Record<SpectrumAxisId, number>>;
}

export interface CalibrationRoundSpec {
  roundIndex: 1 | 2;
  promptQuestion: string;
  axisHint: string;
  optionA: CalibrationChoiceOption;
  optionB: CalibrationChoiceOption;
}

export const CALIBRATION_ROUNDS: readonly CalibrationRoundSpec[] = [
  {
    roundIndex: 1,
    promptQuestion: '材质时间熵与构造表现度：你更偏向哪种物理表皮张力？',
    axisHint: '收敛维度：构造诚实度 × 肌理时间熵',
    optionA: {
      id: 'A',
      assetId: 'arch_01',
      headline: '风化粗粝矿物质感 · 明缝耐候构筑',
      rationale: '保留耐候钢与模板混凝土的自然岁月肌理，强化 12mm 结构明缝秩序',
      targetDelta: { surface_entropy: 0.45, tectonic_honesty: 0.65, geometric_order: 0.75 },
      boostWeights: { surface_entropy: 1.8, tectonic_honesty: 1.5 },
    },
    optionB: {
      id: 'B',
      assetId: 'ind_02',
      headline: '零瑕疵精密加工 · 机械节点外露',
      rationale: '将表皮收敛至 CNC 阳极氧化金属公差，凸显精密紧固件与仪器级克制',
      targetDelta: { surface_entropy: -0.5, tectonic_honesty: 0.9, geometric_order: 0.9 },
      boostWeights: { surface_entropy: 1.8, tectonic_honesty: 1.7 },
    },
  },
  {
    roundIndex: 2,
    promptQuestion: '光影反差与情绪色温：目标空间应呈现怎样的光环境？',
    axisHint: '收敛维度：光影反差 × 情绪色温 × 留白密度',
    optionA: {
      id: 'A',
      assetId: 'edit_01',
      headline: '极地阴天漫射 · 冷峻克制大留白',
      rationale: '消解硬阴影与高饱和噪点，采用冷灰银盐曲线与 75%+ 呼吸负空间',
      targetDelta: { lighting_drama: -0.7, thermal_mood: -0.6, spatial_density: -0.8, chromatic_tension: -0.75 },
      boostWeights: { lighting_drama: 1.8, thermal_mood: 1.6, spatial_density: 1.5 },
    },
    optionB: {
      id: 'B',
      assetId: 'arch_12',
      headline: '暖金光影切割 · 亲密温润包裹感',
      rationale: '引入 2700K 暖色温与定向光影明暗层次，强化触觉亲和力与氛围张力',
      targetDelta: { lighting_drama: 0.45, thermal_mood: 0.85, chromatic_tension: 0.15 },
      boostWeights: { lighting_drama: 1.7, thermal_mood: 1.9 },
    },
  },
];

interface VisualCalibrationPanelProps {
  isOpen: boolean;
  currentRound: 1 | 2 | 'done';
  chosenLabels: string[];
  assetsById: Record<string, CuratedShowcaseAsset>;
  onSelectOption: (round: CalibrationRoundSpec, option: CalibrationChoiceOption) => void;
  onBackRound: () => void;
  onReset: () => void;
  onClose: () => void;
}

export const VisualCalibrationPanel: React.FC<VisualCalibrationPanelProps> = ({
  isOpen,
  currentRound,
  chosenLabels,
  assetsById,
  onSelectOption,
  onBackRound,
  onReset,
  onClose,
}) => {
  if (!isOpen) return null;

  const activeSpec =
    currentRound === 'done'
      ? null
      : CALIBRATION_ROUNDS.find((r) => r.roundIndex === currentRound) ?? CALIBRATION_ROUNDS[0];

  const titleText =
    currentRound === 'done'
      ? '两轮视觉二分校准已完成'
      : `两轮视觉二分校准 · 第 ${currentRound} / 2 轮`;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="calibration-dialog-title"
      onClick={onClose}
      className="fixed inset-0 z-50 bg-foreground/65 backdrop-blur-[2px] flex items-center justify-center p-3 sm:p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card border border-foreground/70 w-full max-w-4xl max-h-[90vh] overflow-y-auto p-5 sm:p-7 space-y-6"
      >
        <div className="flex flex-wrap items-start justify-between gap-4 pb-4 border-b border-border">
          <div className="space-y-1">
            <h2
              id="calibration-dialog-title"
              className="font-display text-lg sm:text-xl font-bold text-foreground"
            >
              {titleText}
            </h2>
            <p className="text-xs text-muted-foreground">
              {activeSpec
                ? `${activeSpec.promptQuestion}（${activeSpec.axisHint}）`
                : '8 轴意图向量与注意力权重已自动更新至图库排序'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {currentRound !== 1 && (
              <button
                type="button"
                onClick={onBackRound}
                className="min-h-[36px] px-3 text-xs font-medium border border-border hover:border-foreground/70 text-foreground inline-flex items-center gap-1.5 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>返回上一轮</span>
              </button>
            )}
            <button
              type="button"
              onClick={onReset}
              className="min-h-[36px] px-3 text-xs font-medium border border-border hover:border-foreground/70 text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>重置</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭视觉二分校准"
              className="w-10 h-10 border border-border hover:border-foreground/70 text-foreground flex items-center justify-center transition-colors"
            >
              <X className="w-4 h-4" strokeWidth={1.75} />
            </button>
          </div>
        </div>

        {activeSpec ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {[activeSpec.optionA, activeSpec.optionB].map((opt) => {
              const asset = assetsById[opt.assetId];
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onSelectOption(activeSpec, opt)}
                  className="group text-left border border-border hover:border-primary bg-card transition-colors flex flex-col"
                >
                  <div className="aspect-[4/3] w-full bg-secondary/60 overflow-hidden">
                    {asset ? (
                      <img
                        src={asset.image_url}
                        alt={opt.headline}
                        className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
                      />
                    ) : null}
                  </div>
                  <div className="p-4 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-primary">
                        选择方向 {opt.id}
                      </span>
                      <span className="text-muted-foreground">
                        {asset?.subject_isolation.domain_label ?? opt.assetId}
                      </span>
                    </div>
                    <div className="text-sm font-bold text-foreground">{opt.headline}</div>
                    <p className="text-xs text-muted-foreground leading-relaxed">{opt.rationale}</p>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="bg-secondary/60 border border-border p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-foreground">
                已锁定偏好的光谱路径：
              </div>
              <p className="text-xs text-muted-foreground">
                {chosenLabels.join(' → ')}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="min-h-[40px] px-5 bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold transition-colors shrink-0"
            >
              查看重排图库结果
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
