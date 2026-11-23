import React, { useState } from 'react';
import { Check, Copy, X } from 'lucide-react';
import { ALL_AXIS_IDS, type SpectrumAxisId } from '../engine/salienceMetric';
import type { CuratedShowcaseAsset, SpectrumAxisMeta } from '../types/aethervault';

export type AstSlotKey = 'optics' | 'material' | 'lighting';

interface SpecimenLightboxProps {
  asset: CuratedShowcaseAsset | null;
  matchScore?: number;
  axesMetaById: Record<string, SpectrumAxisMeta>;
  selectedSlots: { optics: string; material: string; lighting: string };
  onAssignSlot: (slot: AstSlotKey, assetId: string) => void;
  onCopyHex: (hex: string) => Promise<void> | void;
  onClose: () => void;
}

const AXIS_SHORT_LABELS: Record<SpectrumAxisId, string> = {
  tectonic_honesty: '构造诚实',
  surface_entropy: '肌理时间',
  spatial_density: '空间留白',
  geometric_order: '几何秩序',
  lighting_drama: '光影反差',
  chromatic_tension: '色彩张力',
  thermal_mood: '情绪色温',
  reality_abstraction: '抽象程度',
};

export const SpecimenLightbox: React.FC<SpecimenLightboxProps> = ({
  asset,
  matchScore,
  axesMetaById,
  selectedSlots,
  onAssignSlot,
  onCopyHex,
  onClose,
}) => {
  const [copiedHex, setCopiedHex] = useState<string | null>(null);

  if (!asset) return null;

  const handleHexClick = async (hex: string) => {
    await onCopyHex(hex);
    setCopiedHex(hex);
    setTimeout(() => setCopiedHex(null), 1400);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="lightbox-asset-title"
      onClick={onClose}
      className="fixed inset-0 z-50 bg-[#0E1015]/70 backdrop-blur-[2px] flex items-center justify-center p-3 sm:p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#FFFFFF] border border-[#0E1015] w-full max-w-5xl max-h-[92vh] overflow-y-auto grid grid-cols-1 lg:grid-cols-12"
      >
        {/* Left: Full Unobstructed Plate */}
        <div className="lg:col-span-7 bg-[#F4F5F7] border-b lg:border-b-0 lg:border-r border-[#E2E5EA] flex flex-col justify-between p-4 sm:p-6">
          <div className="aspect-[4/3] w-full bg-[#FFFFFF] border border-[#E2E5EA] overflow-hidden">
            <img
              src={asset.image_url}
              alt={asset.title}
              className="w-full h-full object-cover"
            />
          </div>
          <div className="pt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-[#525866]">
            <span>
              编号 <span className="mono font-medium text-[#0E1015]">{asset.asset_id}</span>
              {' · '}
              {asset.subject_isolation.domain_label}
              {asset.subject_isolation.is_personal_prior ? ' · 个人审美先验' : ''}
            </span>
            <span className="mono">
              授权溯源：{asset.license}
            </span>
          </div>
        </div>

        {/* Right: Monograph Telemetry, Palette & Slot Assignment */}
        <div className="lg:col-span-5 p-5 sm:p-6 flex flex-col justify-between gap-6">
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-3 pb-4 border-b border-[#E2E5EA]">
              <div>
                <h2
                  id="lightbox-asset-title"
                  className="font-display text-lg font-bold text-[#0E1015] leading-snug"
                >
                  {asset.title}
                </h2>
                {asset.title_en && (
                  <p className="text-xs text-[#525866] mt-0.5">{asset.title_en}</p>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="关闭大图检视"
                className="w-10 h-10 shrink-0 border border-[#E2E5EA] hover:border-[#0E1015] flex items-center justify-center text-[#0E1015] transition-colors"
              >
                <X className="w-4 h-4" strokeWidth={1.75} />
              </button>
            </div>

            {typeof matchScore === 'number' && (
              <div className="flex items-center justify-between text-xs pb-3 border-b border-[#E2E5EA]">
                <span className="text-[#525866]">当前 8 轴光谱加权匹配度</span>
                <span className="mono text-sm font-semibold text-[#153CE8] tabular-nums">
                  {matchScore}%
                </span>
              </div>
            )}

            {/* OKLab Palette Swatches */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[#0E1015]">OKLab 提取主色板</span>
                <span className="text-[#525866]">点击色卡复制色值</span>
              </div>
              <div className="grid grid-cols-5 gap-2">
                {asset.granular_descriptors.color_palette.slice(0, 5).map((hex) => {
                  const isCopied = copiedHex === hex;
                  return (
                    <button
                      key={hex}
                      type="button"
                      onClick={() => handleHexClick(hex)}
                      aria-label={`复制色值 ${hex}`}
                      className="text-left border border-[#E2E5EA] hover:border-[#0E1015] transition-colors"
                    >
                      <div className="h-9 w-full" style={{ backgroundColor: hex }} />
                      <div className="px-1.5 py-1 text-xs mono text-[#0E1015] flex items-center justify-between">
                        <span className="truncate">{isCopied ? '已复制' : hex}</span>
                        {isCopied ? (
                          <Check className="w-3 h-3 text-[#0F766E] shrink-0" />
                        ) : (
                          <Copy className="w-3 h-3 text-[#525866] shrink-0" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Granular Layer Descriptors */}
            <div className="space-y-2.5 text-xs border-t border-[#E2E5EA] pt-4">
              <div>
                <span className="font-semibold text-[#0E1015]">光学镜头层：</span>
                <span className="text-[#525866]">{asset.granular_descriptors.optics_camera}</span>
              </div>
              <div>
                <span className="font-semibold text-[#0E1015]">材质构筑层：</span>
                <span className="text-[#525866]">{asset.granular_descriptors.material_stack}</span>
              </div>
              <div>
                <span className="font-semibold text-[#0E1015]">大气光影层：</span>
                <span className="text-[#525866]">{asset.granular_descriptors.lighting_rig}</span>
              </div>
            </div>

            {/* 8-Axis Spectrum Readings & Salience */}
            <div className="space-y-2 border-t border-[#E2E5EA] pt-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[#0E1015]">8 轴正交光谱读数</span>
                <span className="text-[#525866]" title="Salience 决定该轴在距离计算中参与权重的高低，避免局部特写产生噪声">
                  含显著度门控 (s)
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                {ALL_AXIS_IDS.map((axisId) => {
                  const reading = asset.style_spectrums[axisId];
                  const label = axesMetaById[axisId]?.label_zh ?? AXIS_SHORT_LABELS[axisId];
                  const pct = Math.round(((reading.score + 1) / 2) * 100);
                  return (
                    <div key={axisId} className="space-y-1">
                      <div className="flex items-center justify-between text-[#0E1015]">
                        <span>{label}</span>
                        <span className="mono tabular-nums text-[#525866]">
                          {reading.score > 0 ? `+${reading.score.toFixed(1)}` : reading.score.toFixed(1)} · s={reading.salience.toFixed(1)}
                        </span>
                      </div>
                      <div className="h-1 bg-[#E2E5EA] w-full">
                        <div className="h-full bg-[#153CE8]" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Slot Assignment Footer */}
          <div className="border-t border-[#E2E5EA] pt-4 space-y-2">
            <div className="text-xs font-semibold text-[#0E1015]">装配至 AST 正交混音槽位</div>
            <div className="grid grid-cols-3 gap-2">
              {(
                [
                  { slot: 'optics' as const, label: '设为镜头参考', active: selectedSlots.optics === asset.asset_id },
                  { slot: 'material' as const, label: '设为材质参考', active: selectedSlots.material === asset.asset_id },
                  { slot: 'lighting' as const, label: '设为光影参考', active: selectedSlots.lighting === asset.asset_id },
                ] as const
              ).map((item) => (
                <button
                  key={item.slot}
                  type="button"
                  aria-pressed={item.active}
                  onClick={() => onAssignSlot(item.slot, asset.asset_id)}
                  className={`min-h-[40px] px-2 text-xs font-medium border transition-colors ${
                    item.active
                      ? 'bg-[#153CE8] border-[#153CE8] text-[#FFFFFF]'
                      : 'bg-[#FFFFFF] border-[#E2E5EA] text-[#0E1015] hover:border-[#0E1015]'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
