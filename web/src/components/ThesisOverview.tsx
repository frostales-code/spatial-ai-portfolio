import React from 'react';
import { ArrowLeftRight, ArrowRight } from 'lucide-react';
import type { CuratedShowcaseAsset } from '../types/aethervault';

export type MainTabId = 'thesis' | 'projectA' | 'projectB' | 'techEval';

interface ThesisOverviewProps {
  onNavigate: (tab: MainTabId) => void;
  totalCuratedAssets: number;
  effectiveCostCnyPerImg: number;
  previewAssets?: CuratedShowcaseAsset[];
}

export const ThesisOverview: React.FC<ThesisOverviewProps> = ({
  onNavigate,
  totalCuratedAssets,
  effectiveCostCnyPerImg,
  previewAssets = [],
}) => {
  return (
    <div className="space-y-12">
      {/* Opening Thesis Band */}
      <section className="pb-10 border-b border-[#E2E5EA] flex flex-col lg:flex-row lg:items-end justify-between gap-8">
        <div className="max-w-3xl space-y-4">
          <h1 className="font-display text-3xl sm:text-4xl lg:text-[42px] font-extrabold leading-[1.12] tracking-[-0.03em] text-[#0E1015]">
            从「隐性审美唤醒」到「物理建构落地」的空间 AI 双引擎架构
          </h1>
          <p className="text-[15px] text-[#525866] leading-relaxed max-w-[66ch]">
            现阶段空间生成工具普遍停留在孤立的“单步抽卡出图”——前端接不住设计师高度非标、跨门类的微妙品味，后端接不住施工模数分缝、规范排雷与预算动态重算。本系统将概率生成模型约束在确定性工程底座之内：上游入库{' '}
            <span className="mono font-semibold text-[#0E1015] tabular-nums">{totalCuratedAssets}</span> 件跨 5 门类锚定标本，实测在线结构化标定成本{' '}
            <span className="mono font-semibold text-[#153CE8] tabular-nums">¥{effectiveCostCnyPerImg.toFixed(4)}/张</span>；下游由单应性投影与零幻觉 Decimal 账本闭环。
          </p>
        </div>

        <div className="flex flex-wrap lg:flex-col gap-3 shrink-0">
          <button
            type="button"
            onClick={() => onNavigate('projectA')}
            className="min-h-[44px] px-5 bg-[#153CE8] hover:bg-[#0E2BB5] text-[#FFFFFF] text-xs font-semibold inline-flex items-center justify-between gap-6 transition-colors"
          >
            <span>进入 AetherVault 工作台</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => onNavigate('projectB')}
            className="min-h-[44px] px-5 border border-[#0E1015] bg-[#FFFFFF] hover:bg-[#F4F5F7] text-[#0E1015] text-xs font-semibold inline-flex items-center justify-between gap-6 transition-colors"
          >
            <span>查看 TectonicLoop 立面沙盒</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </section>

      {/* Curated Photographic Rhythm Strip */}
      {previewAssets.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="font-display text-lg font-bold text-[#0E1015]">跨门类同构视觉采样实例</h2>
            <button
              type="button"
              onClick={() => onNavigate('projectA')}
              className="text-xs font-semibold text-[#153CE8] hover:underline"
            >
              检视全部 {totalCuratedAssets} 件标本
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
            {previewAssets.map((asset) => (
              <div key={asset.asset_id} className="space-y-2">
                <div className="aspect-[4/3] bg-[#F4F5F7] overflow-hidden">
                  <img
                    src={asset.image_url}
                    alt={asset.title}
                    loading="lazy"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="font-semibold text-[#0E1015] truncate">{asset.title}</span>
                  <span className="text-[#525866] shrink-0">{asset.subject_isolation.domain_label}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Dual-Engine Architecture + Full-Width Bidirectional Bridge */}
      <section className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 border border-[#E2E5EA] divide-y lg:divide-y-0 lg:divide-x divide-[#E2E5EA]">
          {/* Engine A */}
          <div className="p-6 sm:p-8 flex flex-col justify-between space-y-6 bg-[#FFFFFF]">
            <div className="space-y-5">
              <div className="border-t-2 border-[#153CE8] pt-3 flex items-baseline justify-between">
                <span className="mono text-xs font-semibold text-[#153CE8]">0 → 1 概念探索与审美对齐</span>
                <span className="text-xs text-[#525866]">AetherVault</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-bold text-[#0E1015]">
                  AetherVault · 美学光谱知识库与风格编译器
                </h2>
                <p className="text-sm text-[#525866] mt-1">
                  解决“收藏数千张参考图却搜不出氛围感，多图混搭生图彼此串色污染”的前端痛点。
                </p>
              </div>
              <div className="space-y-4 border-t border-[#E2E5EA] pt-4 text-xs">
                <div>
                  <div className="font-semibold text-[#0E1015]">1. 8 维连续双极光谱与 5 点黄金锚点标尺</div>
                  <p className="text-[#525866] leading-relaxed mt-1">
                    剥离物体类别，按构造诚实度、肌理时间熵、光影反差与留白密度等 8 条正交轴 [-1.0, +1.0] 建立可计算指纹，以 40 组视觉黄金标尺抑制 VLM 打分漂移。
                  </p>
                </div>
                <div>
                  <div className="font-semibold text-[#0E1015]">2. 个人先验唤醒、跨界召回与两轮视觉校准</div>
                  <p className="text-[#525866] leading-relaxed mt-1">
                    联动个人高审美色板先验数据库，锁死光谱指纹从精密工业、高定摄影与东方器物中跨域召回同构灵感，两次点击快速收敛模糊需求。
                  </p>
                </div>
                <div>
                  <div className="font-semibold text-[#0E1015]">3. 作用域隔离的正交 AST 特征编译</div>
                  <p className="text-[#525866] leading-relaxed mt-1">
                    拆解并分别继承“图 A 镜头透视 + 图 B 局部材质 + 图 C 全局光影”，自动清理无关主体并注入定向负向护栏。
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-[#E2E5EA] flex items-center justify-between text-xs">
              <span className="text-[#525866]">核心约束：&lt; 20ms 前端纯向量重排</span>
              <button
                type="button"
                onClick={() => onNavigate('projectA')}
                className="font-semibold text-[#153CE8] hover:underline"
              >
                打开编译器工作台
              </button>
            </div>
          </div>

          {/* Engine B */}
          <div className="p-6 sm:p-8 flex flex-col justify-between space-y-6 bg-[#FFFFFF]">
            <div className="space-y-5">
              <div className="border-t-2 border-[#0E1015] pt-3 flex items-baseline justify-between">
                <span className="mono text-xs font-semibold text-[#0E1015]">1 → N 深化落地与动态控本</span>
                <span className="text-xs text-[#525866]">TectonicLoop</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-bold text-[#0E1015]">
                  TectonicLoop · 物理建构与造价双向引擎
                </h2>
                <p className="text-sm text-[#525866] mt-1">
                  终结脱离工程常识的“效果图诈骗”，打通概念视觉、标准节点模数与造价预算的双向反馈。
                </p>
              </div>
              <div className="space-y-4 border-t border-[#E2E5EA] pt-4 text-xs">
                <div>
                  <div className="font-semibold text-[#0E1015]">1. 物理建构幻觉自动排雷</div>
                  <p className="text-[#525866] leading-relaxed mt-1">
                    自动检出超限整体幕墙玻璃、临街无法占道养护的现浇混凝土、缺乏金属泛水与防潮勒脚的墙身细部。
                  </p>
                </div>
                <div>
                  <div className="font-semibold text-[#0E1015]">2. 同效异构工艺包与零幻觉 Decimal 算账</div>
                  <p className="text-[#525866] leading-relaxed mt-1">
                    严格锁定大模型仅做语义路由，所有净面积折算、损耗系数与工程量清单全部走 Decimal 规则计算；缺失单价强制输出 UNKNOWN_PRICE_MISSING。
                  </p>
                </div>
                <div>
                  <div className="font-semibold text-[#0E1015]">3. 预算约束反向透视模数投影</div>
                  <p className="text-[#525866] leading-relaxed mt-1">
                    预算或工期收紧切换干挂体系时，依单应性矩阵 H/H⁻¹ 精准映射 600/1200mm 拼缝网格与压顶收口。
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-[#E2E5EA] flex items-center justify-between text-xs">
              <span className="text-[#525866]">核心约束：Zero-LLM 确定性造价表</span>
              <button
                type="button"
                onClick={() => onNavigate('projectB')}
                className="font-semibold text-[#153CE8] hover:underline"
              >
                打开立面排雷沙盒
              </button>
            </div>
          </div>
        </div>

        {/* Full-Width Horizontal Bidirectional Data Bar */}
        <div className="border border-[#E2E5EA] bg-[#F4F5F7] px-5 py-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          <div className="font-semibold text-[#0E1015]">
            上游输出：高审美正交 AST 概念方案 + 物理尺度锚点
          </div>
          <div className="flex items-center gap-2 text-[#153CE8] font-semibold shrink-0">
            <ArrowLeftRight className="w-4 h-4" />
            <span>双向数据闭环</span>
          </div>
          <div className="font-semibold text-[#0E1015]">
            下游回流：经预算/工艺验证的真实节点沉淀入库
          </div>
        </div>
      </section>

      {/* 4 Core AI Product Architecture Pillars (Top-ruled Swiss Grid, zero side-tabs) */}
      <section className="space-y-5">
        <h2 className="font-display text-lg font-bold text-[#0E1015]">
          AI 产品工程与系统边界实践
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-xs">
          {[
            {
              title: '领域本体工程 (Ontology)',
              desc: '将模糊的“视觉氛围”与“建筑构造规范”分别抽象为正交连续光谱矩阵与构造节点状态图，替代脆弱文本切片。',
            },
            {
              title: '复合系统分工 (Compound AI)',
              desc: '清晰划分概率模型与确定性代码：VLM 负责语义归类，几何单应性计算分缝投影，Decimal 规则引擎负责精确算账。',
            },
            {
              title: 'GUI + LUI 融合交互',
              desc: '用 8 轴连续滑块、5 点视觉标尺与 2 轮二分比较取代设计师排斥的多轮纯文本对话试错。',
            },
            {
              title: '评测驱动研发 (EDD)',
              desc: '为每条核心链路配置可复用量化基准：斯皮尔曼排序一致性、透视灭点角度误差、Token 成本红线与账单精度。',
            },
          ].map((pillar) => (
            <div key={pillar.title} className="border-t-2 border-[#0E1015] pt-3.5 space-y-1.5">
              <div className="text-sm font-bold text-[#0E1015]">{pillar.title}</div>
              <p className="text-[#525866] leading-relaxed">{pillar.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
