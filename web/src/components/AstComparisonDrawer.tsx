import React, { useEffect, useState } from 'react';
import { ArrowDownToLine, X } from 'lucide-react';
import type {
  AstComparisonBundle,
  AstComparisonPair,
  CuratedShowcaseAsset,
} from '../types/aethervault';
import { BeforeAfterSlider } from './BeforeAfterSlider';

interface AstComparisonDrawerProps {
  isOpen: boolean;
  initialPairId?: string;
  onClose: () => void;
  comparisonBundle: AstComparisonBundle | null;
  assetsById: Record<string, CuratedShowcaseAsset>;
  currentSlots: { optics: string; material: string; lighting: string };
  currentCompiledPrompt: string;
  currentNegativePrompt: string;
  currentConflictsCount: number;
  onLoadSlotsIntoMixer: (pair: AstComparisonPair) => void;
}

function findClosestPairId(
  pairs: AstComparisonPair[],
  slots: { optics: string; material: string; lighting: string },
): string {
  if (pairs.length === 0) return '';
  let bestId = pairs[0].pair_id;
  let bestMatches = -1;
  for (const pair of pairs) {
    let matches = 0;
    if (pair.slots.optics === slots.optics) matches += 1;
    if (pair.slots.material === slots.material) matches += 1;
    if (pair.slots.lighting === slots.lighting) matches += 1;
    if (matches > bestMatches) {
      bestMatches = matches;
      bestId = pair.pair_id;
    }
  }
  return bestId;
}

export const AstComparisonDrawer: React.FC<AstComparisonDrawerProps> = ({
  isOpen,
  initialPairId,
  onClose,
  comparisonBundle,
  assetsById,
  currentSlots,
  currentCompiledPrompt,
  currentNegativePrompt,
  currentConflictsCount,
  onLoadSlotsIntoMixer,
}) => {
  const pairs = comparisonBundle?.pairs ?? [];
  const [selectedPairId, setSelectedPairId] = useState<string>('');

  useEffect(() => {
    if (isOpen && pairs.length > 0) {
      if (initialPairId && pairs.some((p) => p.pair_id === initialPairId)) {
        setSelectedPairId(initialPairId);
      } else {
        setSelectedPairId(findClosestPairId(pairs, currentSlots));
      }
    }
  }, [isOpen, initialPairId, pairs, currentSlots]);

  if (!isOpen) return null;

  const activePair = pairs.find((p) => p.pair_id === selectedPairId) ?? pairs[0] ?? null;
  const optAsset = activePair ? assetsById[activePair.slots.optics] : assetsById[currentSlots.optics];
  const matAsset = activePair ? assetsById[activePair.slots.material] : assetsById[currentSlots.material];
  const litAsset = activePair ? assetsById[activePair.slots.lighting] : assetsById[currentSlots.lighting];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ast-compare-drawer-title"
      onClick={onClose}
      className="fixed inset-0 z-50 bg-[#0E1015]/65 backdrop-blur-[2px] flex justify-end"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#FFFFFF] border-l border-[#0E1015] w-full max-w-3xl h-full flex flex-col overflow-hidden"
      >
        <div className="px-5 py-4 border-b border-[#E2E5EA] flex items-start justify-between gap-4 bg-[#FFFFFF]">
          <div>
            <h3
              id="ast-compare-drawer-title"
              className="font-display text-lg font-bold text-[#0E1015]"
            >
              多图直喂污染 vs 正交 AST 编译细节对照（{pairs.length} 组样本）
            </h3>
            <p className="text-xs text-[#525866] mt-0.5">
              对比三源图作用域隔离前后的结构化 Prompt 差异与冲突词拦截记录
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭 AST 对比抽屉"
            className="w-10 h-10 shrink-0 border border-[#E2E5EA] hover:border-[#0E1015] text-[#0E1015] flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4" strokeWidth={1.75} />
          </button>
        </div>

        <div className="p-5 overflow-y-auto space-y-6 text-xs">
          {/* Pair Index Selector */}
          {pairs.length > 0 && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-[#0E1015]">切换对照样本组合</span>
                {activePair && (
                  <button
                    type="button"
                    onClick={() => {
                      onLoadSlotsIntoMixer(activePair);
                      onClose();
                    }}
                    className="min-h-[36px] px-3.5 bg-[#153CE8] hover:bg-[#0E2BB5] text-[#FFFFFF] text-xs font-semibold inline-flex items-center gap-1.5 transition-colors"
                  >
                    <ArrowDownToLine className="w-3.5 h-3.5" />
                    <span>载入此组至底部托盘</span>
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {pairs.map((p) => {
                  const isSel = activePair?.pair_id === p.pair_id;
                  return (
                    <button
                      key={p.pair_id}
                      type="button"
                      aria-pressed={isSel}
                      onClick={() => setSelectedPairId(p.pair_id)}
                      className={`text-left p-2.5 border transition-colors ${
                        isSel
                          ? 'bg-[#EEF2FF] border-[#153CE8] text-[#0E1015]'
                          : 'bg-[#FFFFFF] border-[#E2E5EA] text-[#525866] hover:border-[#0E1015] hover:text-[#0E1015]'
                      }`}
                    >
                      <div className="flex items-center justify-between mono text-xs">
                        <span className={isSel ? 'text-[#153CE8] font-semibold' : 'text-[#525866]'}>
                          {p.pair_id.toUpperCase()}
                        </span>
                        <span className="tabular-nums">{p.conflicts_isolated_count} 隔离</span>
                      </div>
                      <div className="font-medium text-[#0E1015] truncate mt-1">{p.title_zh}</div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {activePair ? (
            <BeforeAfterSlider
              beforeSrc={activePair.naive_image_url}
              afterSrc={activePair.ast_image_url}
              beforeAlt={`${activePair.pair_id} 基线多图直喂结果`}
              afterAlt={`${activePair.pair_id} AetherVault 正交 AST 编译结果`}
            />
          ) : (
            <div className="p-8 border border-[#E2E5EA] bg-[#F4F5F7] text-center text-[#525866]">
              暂未加载对比实测样本数据集。
            </div>
          )}

          {/* 3 Isolated Source Slots */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label: '镜头透视来源', asset: optAsset, field: optAsset?.granular_descriptors.optics_camera },
              { label: '材质构筑来源', asset: matAsset, field: matAsset?.granular_descriptors.material_stack },
              { label: '大气光影来源', asset: litAsset, field: litAsset?.granular_descriptors.lighting_rig },
            ].map((s) => (
              <div key={s.label} className="border border-[#E2E5EA] bg-[#FFFFFF] p-3 space-y-2">
                <div className="text-xs font-semibold text-[#153CE8]">{s.label}</div>
                {s.asset && (
                  <div className="aspect-[4/3] bg-[#F4F5F7] overflow-hidden">
                    <img src={s.asset.image_url} alt={s.asset.title} className="w-full h-full object-cover" />
                  </div>
                )}
                <div className="font-semibold text-[#0E1015] truncate">
                  {s.asset?.title}
                </div>
                <p className="text-xs text-[#525866] leading-relaxed line-clamp-3">{s.field}</p>
              </div>
            ))}
          </div>

          {/* Decoupling Diagnosis */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 border border-[#E2E5EA] bg-[#F4F5F7] space-y-1.5">
              <div className="font-semibold text-[#C62828]">
                多图直喂失效归因
              </div>
              <p className="text-[#0E1015] leading-relaxed">
                {activePair?.naive_failure_summary ??
                  '直接将三张跨界参考图联合送入图像编辑模型，会导致原物体轮廓与冲突词条直接泄漏至目标建筑骨架。'}
              </p>
            </div>

            <div className="p-4 border border-[#E2E5EA] bg-[#F4F5F7] space-y-1.5">
              <div className="font-semibold text-[#0F766E]">
                AST 作用域隔离机制（拦截 {activePair?.conflicts_isolated_count ?? currentConflictsCount} 项冲突）
              </div>
              <p className="text-[#0E1015] leading-relaxed">
                {activePair?.ast_decoupling_summary ??
                  '通过四层正交结构严格切分光学镜头、局部构件材质与全局环境光，彻底屏蔽非预期主体迁移。'}
              </p>
            </div>
          </div>

          {/* Compiled Prompt & Guardrails */}
          <div className="border border-[#E2E5EA] p-4 space-y-2 bg-[#FFFFFF]">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[#0E1015]">编译后正交 AST 结构化指令</span>
              <span className="mono text-[#153CE8]">
                {activePair ? activePair.pair_id.toUpperCase() : 'LIVE MIXER'}
              </span>
            </div>
            <pre className="p-3 bg-[#F4F5F7] border border-[#E2E5EA] text-xs mono text-[#0E1015] whitespace-pre-wrap leading-relaxed">
              {activePair?.compiled_prompt ?? currentCompiledPrompt}
            </pre>
            <div className="text-xs mono text-[#C62828] bg-[#F4F5F7] border border-[#E2E5EA] p-2.5">
              --no {activePair ? activePair.negative_guardrails.join(', ') : currentNegativePrompt.replace(/^--no\s*/, '')}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
