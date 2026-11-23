import React, { useCallback, useEffect, useState } from 'react';
import { Compass, RotateCw, X } from 'lucide-react';
import { AetherVaultWorkspace } from './components/AetherVaultWorkspace';
import { GUIDED_TOUR_STOPS, GuidedTourPopover } from './components/GuidedTourPopover';
import { TechEvalOverview } from './components/TechEvalOverview';
import { TectonicLoopPreview } from './components/TectonicLoopPreview';
import { ThesisOverview, type MainTabId } from './components/ThesisOverview';
import type { AetherVaultShowcaseBundle, AstComparisonBundle } from './types/aethervault';
import type { TectonicShowcaseBundle } from './types/tectonic';
import { trackShowcaseEvent } from './utils/analytics';
import { resolvePublicUrl } from './utils/assetUrl';

const TAB_TITLES: Record<MainTabId, string> = {
  projectA: 'AetherVault — 正交美学光谱编译器 | Spatial AI Monograph',
  thesis: '双引擎方法论 — AetherVault & TectonicLoop',
  projectB: 'TectonicLoop — 物理建构与造价双向闭环',
  techEval: '评测基准 — 量化指标与冷启动成本账本',
};

function normalizeBundleUrls(
  bundleData: AetherVaultShowcaseBundle
): AetherVaultShowcaseBundle {
  return {
    ...bundleData,
    assets: bundleData.assets.map((asset) => ({
      ...asset,
      image_url: resolvePublicUrl(asset.image_url),
    })),
  };
}

function normalizeComparisonUrls(
  cmpData: AstComparisonBundle | null
): AstComparisonBundle | null {
  if (!cmpData) return null;
  return {
    ...cmpData,
    pairs: cmpData.pairs.map((pair) => ({
      ...pair,
      naive_image_url: resolvePublicUrl(pair.naive_image_url),
      ast_image_url: resolvePublicUrl(pair.ast_image_url),
    })),
  };
}

function normalizeTectonicUrls(
  tecData: TectonicShowcaseBundle | null
): TectonicShowcaseBundle | null {
  if (!tecData) return null;
  return {
    ...tecData,
    cases: tecData.cases.map((c) => ({
      ...c,
      tiers: c.tiers.map((tier) => ({
        ...tier,
        image_url: resolvePublicUrl(tier.image_url),
      })),
    })),
  };
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<MainTabId>('projectA');
  const [bundle, setBundle] = useState<AetherVaultShowcaseBundle | null>(null);
  const [comparisonBundle, setComparisonBundle] = useState<AstComparisonBundle | null>(null);
  const [tectonicBundle, setTectonicBundle] = useState<TectonicShowcaseBundle | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLiveEngine, setIsLiveEngine] = useState(false);
  const [probingEngine, setProbingEngine] = useState(false);
  const [liveNotice, setLiveNotice] = useState<string | null>(null);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourStep, setTourStep] = useState(0);

  const loadShowcaseData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [showcaseRes, compareRes, tectonicRes] = await Promise.all([
        fetch(resolvePublicUrl('/data/aethervault_showcase_v1.json')),
        fetch(resolvePublicUrl('/data/ast_comparisons_v1.json')).catch(() => null),
        fetch(resolvePublicUrl('/data/tectonic_showcase_v1.json')).catch(() => null),
      ]);
      if (!showcaseRes.ok) {
        throw new Error(`数据包读取失败 (HTTP ${showcaseRes.status})`);
      }
      const data: AetherVaultShowcaseBundle = await showcaseRes.json();
      const cmpData: AstComparisonBundle | null =
        compareRes && compareRes.ok ? await compareRes.json() : null;
      const tecData: TectonicShowcaseBundle | null =
        tectonicRes && tectonicRes.ok ? await tectonicRes.json() : null;
      setBundle(normalizeBundleUrls(data));
      setComparisonBundle(normalizeComparisonUrls(cmpData));
      setTectonicBundle(normalizeTectonicUrls(tecData));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadShowcaseData();
    let cancelled = false;
    async function probeLiveEngine() {
      try {
        const res = await fetch('/api/health', { signal: AbortSignal.timeout(1200) });
        if (res.ok) {
          const data = await res.json();
          if (!cancelled && data?.status === 'ok') setIsLiveEngine(true);
        }
      } catch {
        // Default Instant Showcase Mode when local FastAPI is not running
      }
    }
    probeLiveEngine();
    return () => {
      cancelled = true;
    };
  }, [loadShowcaseData]);

  useEffect(() => {
    document.title = TAB_TITLES[activeTab];
  }, [activeTab]);

  const navItems: Array<{ id: MainTabId; label: string }> = [
    { id: 'projectA', label: 'AetherVault' },
    { id: 'thesis', label: '双引擎方法论' },
    { id: 'projectB', label: 'TectonicLoop' },
    { id: 'techEval', label: '评测基准' },
  ];

  const handleNavigate = (tab: MainTabId) => {
    setActiveTab(tab);
    trackShowcaseEvent('tab_view', { tab });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSwitchEngineMode = async (target: 'instant' | 'live') => {
    if (target === 'instant') {
      setIsLiveEngine(false);
      setLiveNotice(null);
      trackShowcaseEvent('mode_switch', { mode: 'instant_showcase' });
      return;
    }

    setProbingEngine(true);
    setLiveNotice(null);
    try {
      const res = await fetch('/api/health', { signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        const payload = await res.json();
        if (payload?.status === 'ok') {
          setIsLiveEngine(true);
          trackShowcaseEvent('mode_switch', { mode: 'live_engine', connected: true });
          return;
        }
      }
      setIsLiveEngine(false);
      setLiveNotice(
        '未检测到本地 FastAPI Live Engine (127.0.0.1:8780)。公网展示已保持在零延迟 Instant Showcase 模式，所有交互、AST 对比与 Zero-LLM 造价算账均可在浏览器离线运行。'
      );
      trackShowcaseEvent('mode_switch', { mode: 'live_engine', connected: false });
    } catch {
      setIsLiveEngine(false);
      setLiveNotice(
        '未检测到本地 FastAPI Live Engine (127.0.0.1:8780)。公网展示已保持在零延迟 Instant Showcase 模式，所有交互、AST 对比与 Zero-LLM 造价算账均可在浏览器离线运行。'
      );
      trackShowcaseEvent('mode_switch', { mode: 'live_engine', connected: false });
    } finally {
      setProbingEngine(false);
    }
  };

  const handleSelectTourStep = (nextIndex: number) => {
    const safeIndex = Math.max(0, Math.min(nextIndex, GUIDED_TOUR_STOPS.length - 1));
    const stop = GUIDED_TOUR_STOPS[safeIndex];
    setTourStep(safeIndex);
    setActiveTab(stop.tab);
    trackShowcaseEvent('tour_step', { step: safeIndex + 1, stop_id: stop.id });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleOpenTour = () => {
    setTourOpen(true);
    handleSelectTourStep(0);
  };

  const handleCloseTour = () => {
    setTourOpen(false);
    trackShowcaseEvent('tour_complete', { last_step: tourStep + 1 });
  };

  return (
    <div className="min-h-screen bg-[#FFFFFF] text-[#0E1015]">
      {/* Compact Monograph Masthead */}
      <header className="sticky top-0 z-40 border-b border-[#E2E5EA] bg-[#FFFFFF]/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="h-12 md:h-14 flex items-center justify-between gap-2 sm:gap-4">
            <button
              type="button"
              onClick={() => handleNavigate('projectA')}
              className="font-display text-[13px] sm:text-[15px] font-extrabold tracking-[-0.02em] text-[#0E1015] whitespace-nowrap hover:text-[#153CE8] transition-colors shrink-0"
            >
              <span className="sm:hidden">AETHERVAULT</span>
              <span className="hidden sm:inline">AETHERVAULT / TECTONICLOOP</span>
            </button>

            {/* Desktop Tablist */}
            <nav
              role="tablist"
              aria-label="主导航"
              className="hidden md:flex items-center h-14 gap-7"
            >
              {navItems.map((item) => {
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => handleNavigate(item.id)}
                    className={`h-full inline-flex items-center text-[13px] font-medium border-b-2 whitespace-nowrap transition-colors ${
                      active
                        ? 'border-[#153CE8] text-[#0E1015] font-semibold'
                        : 'border-transparent text-[#525866] hover:text-[#0E1015]'
                    }`}
                  >
                    {item.label}
                  </button>
                );
              })}
            </nav>

            {/* Interactive Tour + Dual-Mode Switcher */}
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleOpenTour}
                aria-expanded={tourOpen}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 border text-xs font-medium whitespace-nowrap transition-colors ${
                  tourOpen
                    ? 'border-[#153CE8] bg-[#153CE8] text-white'
                    : 'border-[#E2E5EA] bg-[#FFFFFF] text-[#0E1015] hover:border-[#153CE8] hover:text-[#153CE8]'
                }`}
              >
                <Compass className="w-3.5 h-3.5 shrink-0" strokeWidth={1.75} />
                <span>3 分钟导览</span>
              </button>

              <div
                role="group"
                aria-label="运行模式切换"
                className="inline-flex items-center border border-[#E2E5EA] bg-[#FFFFFF]"
              >
                <button
                  type="button"
                  aria-pressed={!isLiveEngine}
                  onClick={() => handleSwitchEngineMode('instant')}
                  className={`inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs whitespace-nowrap transition-colors ${
                    !isLiveEngine
                      ? 'bg-[#F4F5F7] text-[#0E1015] font-semibold'
                      : 'text-[#525866] hover:text-[#0E1015]'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      !isLiveEngine ? 'bg-[#153CE8]' : 'bg-[#E2E5EA]'
                    }`}
                    aria-hidden="true"
                  />
                  <span className="sm:hidden">Showcase</span>
                  <span className="hidden sm:inline">Instant Showcase</span>
                </button>
                <button
                  type="button"
                  aria-pressed={isLiveEngine}
                  disabled={probingEngine}
                  onClick={() => handleSwitchEngineMode('live')}
                  className={`inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-xs border-l border-[#E2E5EA] whitespace-nowrap transition-colors disabled:opacity-60 ${
                    isLiveEngine
                      ? 'bg-[#F4F5F7] text-[#0F766E] font-semibold'
                      : 'text-[#525866] hover:text-[#0E1015]'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      isLiveEngine ? 'bg-[#0F766E]' : 'bg-[#E2E5EA]'
                    }`}
                    aria-hidden="true"
                  />
                  <span className="sm:hidden">{probingEngine ? '探测...' : 'Live'}</span>
                  <span className="hidden sm:inline">
                    {probingEngine ? '探测中...' : 'Live Engine'}
                  </span>
                </button>
              </div>
            </div>
          </div>

          {/* Mobile Single-Row Scrollable Tab Rail (<=40px) */}
          <nav
            role="tablist"
            aria-label="移动端主导航"
            className="md:hidden flex items-center gap-5 h-10 border-t border-[#E2E5EA] overflow-x-auto no-scrollbar"
          >
            {navItems.map((item) => {
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => handleNavigate(item.id)}
                  className={`h-full inline-flex items-center text-[13px] border-b-2 whitespace-nowrap shrink-0 transition-colors ${
                    active
                      ? 'border-[#153CE8] text-[#0E1015] font-semibold'
                      : 'border-transparent text-[#525866]'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 pt-6 pb-24">
        {liveNotice && (
          <div
            role="status"
            className="mb-6 px-4 py-3 border border-[#E2E5EA] bg-[#F4F5F7] flex items-start justify-between gap-4 text-xs text-[#0E1015]"
          >
            <p className="leading-relaxed">{liveNotice}</p>
            <button
              type="button"
              onClick={() => setLiveNotice(null)}
              aria-label="关闭模式提示"
              className="text-[#525866] hover:text-[#0E1015] shrink-0 p-0.5"
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.75} />
            </button>
          </div>
        )}

        {loadError && (
          <div
            role="alert"
            className="mb-8 p-5 border border-[#C62828] bg-[#FFFFFF] flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div className="space-y-1">
              <div className="text-sm font-semibold text-[#C62828]">数据包加载异常</div>
              <p className="text-xs text-[#525866]">{loadError}</p>
            </div>
            <button
              type="button"
              onClick={loadShowcaseData}
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#153CE8] hover:bg-[#0E2BB5] text-white text-xs font-semibold transition-colors shrink-0"
            >
              <RotateCw className="w-3.5 h-3.5" strokeWidth={1.75} />
              <span>重新加载</span>
            </button>
          </div>
        )}

        {/* Preserve mounted workspaces via CSS hidden so tab switching never wipes sliders or slots */}
        <section
          aria-hidden={activeTab !== 'projectA'}
          className={activeTab === 'projectA' ? 'block' : 'hidden'}
        >
          {bundle ? (
            <AetherVaultWorkspace
              bundle={bundle}
              comparisonBundle={comparisonBundle}
              isLiveEngine={isLiveEngine}
            />
          ) : (
            <div className="py-20 text-center text-sm text-[#525866] border border-[#E2E5EA] bg-[#F4F5F7]">
              {loading ? '正在加载 80 件跨界高审美样本与 8 轴五点黄金锚点数据...' : '暂无可用展示数据'}
            </div>
          )}
        </section>

        <section
          aria-hidden={activeTab !== 'thesis'}
          className={activeTab === 'thesis' ? 'block' : 'hidden'}
        >
          <ThesisOverview
            onNavigate={handleNavigate}
            totalCuratedAssets={bundle?.total_assets ?? 80}
            effectiveCostCnyPerImg={
              bundle?.vlm_scoring_report?.cost_metrics.observed_online_cny_per_img ??
              bundle?.cost_ledger.effective_cost_cny_per_img ??
              0.0059
            }
            previewAssets={
              bundle
                ? (['architecture', 'industrial', 'editorial', 'craft'] as const)
                    .map((dom) => bundle.assets.find((a) => a.subject_isolation.domain === dom))
                    .filter((a): a is NonNullable<typeof a> => Boolean(a))
                : []
            }
          />
        </section>

        <section
          aria-hidden={activeTab !== 'projectB'}
          className={activeTab === 'projectB' ? 'block' : 'hidden'}
        >
          <TectonicLoopPreview
            tectonicBundle={tectonicBundle}
            isLiveEngine={isLiveEngine}
          />
        </section>

        <section
          aria-hidden={activeTab !== 'techEval'}
          className={activeTab === 'techEval' ? 'block' : 'hidden'}
        >
          <TechEvalOverview
            costLedger={bundle?.cost_ledger ?? null}
            vlmReport={bundle?.vlm_scoring_report ?? null}
            tectonicBundle={tectonicBundle}
          />
        </section>
      </main>

      <GuidedTourPopover
        isOpen={tourOpen}
        stepIndex={tourStep}
        onSelectStep={handleSelectTourStep}
        onClose={handleCloseTour}
      />
    </div>
  );
};

export default App;
