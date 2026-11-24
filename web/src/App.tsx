'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Compass, Layers, RotateCw, X } from 'lucide-react';
import { AetherVaultWorkspace } from '@/components/AetherVaultWorkspace';
import { GUIDED_TOUR_STOPS, GuidedTourPopover } from '@/components/GuidedTourPopover';
import { PersonalAestheticAtlas } from '@/components/PersonalAestheticAtlas';
import { TechEvalOverview } from '@/components/TechEvalOverview';
import { TectonicLoopPreview } from '@/components/TectonicLoopPreview';
import { ThemeToggle } from '@/components/ThemeToggle';
import { ThesisOverview, type MainTabId } from '@/components/ThesisOverview';
import { Button } from '@/components/ui/button';
import type { AetherVaultShowcaseBundle, AstComparisonBundle } from '@/types/aethervault';
import type { EddBenchmarkBundle } from '@/types/eval';
import type { TectonicShowcaseBundle } from '@/types/tectonic';
import { trackShowcaseEvent } from '@/utils/analytics';
import { resolvePublicUrl } from '@/utils/assetUrl';

const TAB_TITLES: Record<MainTabId, string> = {
  projectA: 'AetherVault — 正交美学光谱编译器 | Spatial AI Studio',
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
  const [surfaceMode, setSurfaceMode] = useState<'atlas' | 'studio'>('studio');
  const [activeTab, setActiveTab] = useState<MainTabId>('projectA');
  const [bundle, setBundle] = useState<AetherVaultShowcaseBundle | null>(null);
  const [comparisonBundle, setComparisonBundle] = useState<AstComparisonBundle | null>(null);
  const [tectonicBundle, setTectonicBundle] = useState<TectonicShowcaseBundle | null>(null);
  const [eddBenchmark, setEddBenchmark] = useState<EddBenchmarkBundle | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLiveEngine, setIsLiveEngine] = useState(false);
  const [probingEngine, setProbingEngine] = useState(false);
  const [liveNotice, setLiveNotice] = useState<string | null>(null);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourStep, setTourStep] = useState(0);

  const hasPersonalAtlas = Boolean(bundle?.rag_schema && bundle?.aesthetic_profile);

  const loadShowcaseData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const isLocalHost =
        typeof window !== 'undefined' &&
        (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost');

      const fetchPrimaryBundle = async (): Promise<Response> => {
        if (isLocalHost) {
          const personalRes = await fetch(
            resolvePublicUrl('/data/aethervault_personal_500.json')
          ).catch(() => null);
          if (personalRes && personalRes.ok) {
            return personalRes;
          }
        }
        return fetch(resolvePublicUrl('/data/aethervault_showcase_v1.json'));
      };

      const [showcaseRes, compareRes, tectonicRes, eddRes] = await Promise.all([
        fetchPrimaryBundle(),
        fetch(resolvePublicUrl('/data/ast_comparisons_v1.json')).catch(() => null),
        fetch(resolvePublicUrl('/data/tectonic_showcase_v1.json')).catch(() => null),
        fetch(resolvePublicUrl('/data/edd_benchmark_v1.json')).catch(() => null),
      ]);
      if (!showcaseRes.ok) {
        throw new Error(`数据包读取失败 (HTTP ${showcaseRes.status})`);
      }
      const data: AetherVaultShowcaseBundle = await showcaseRes.json();
      const cmpData: AstComparisonBundle | null =
        compareRes && compareRes.ok ? await compareRes.json() : null;
      const tecData: TectonicShowcaseBundle | null =
        tectonicRes && tectonicRes.ok ? await tectonicRes.json() : null;
      const eddData: EddBenchmarkBundle | null =
        eddRes && eddRes.ok ? await eddRes.json() : null;
      setBundle(normalizeBundleUrls(data));
      setComparisonBundle(normalizeComparisonUrls(cmpData));
      setTectonicBundle(normalizeTectonicUrls(tecData));
      setEddBenchmark(eddData);
      if (data.rag_schema && data.aesthetic_profile) {
        setSurfaceMode('atlas');
      } else {
        setSurfaceMode('studio');
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadShowcaseData();
  }, [loadShowcaseData]);

  useEffect(() => {
    document.title =
      surfaceMode === 'atlas' && hasPersonalAtlas
        ? `AetherVault · 个人审美图谱 — ${bundle?.total_assets ?? 500} 样本视觉分析与分类`
        : TAB_TITLES[activeTab];
  }, [surfaceMode, hasPersonalAtlas, bundle?.total_assets, activeTab]);

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

    const offlineMessage =
      '未检测到本地 FastAPI Live Engine (127.0.0.1:8780)。公网展示已保持在零延迟 Instant Showcase 模式，所有 3D 流形、AST 对比与 Zero-LLM 造价算账均可在浏览器离线运行。';
    const isLocalHost =
      typeof window !== 'undefined' &&
      (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost');
    if (!isLocalHost) {
      setIsLiveEngine(false);
      setLiveNotice(offlineMessage);
      trackShowcaseEvent('mode_switch', { mode: 'live_engine', connected: false, host: 'cdn' });
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
      setLiveNotice(offlineMessage);
      trackShowcaseEvent('mode_switch', { mode: 'live_engine', connected: false });
    } catch {
      setIsLiveEngine(false);
      setLiveNotice(offlineMessage);
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

  if (surfaceMode === 'atlas' && hasPersonalAtlas) {
    return (
      <div className="min-h-screen bg-background text-foreground transition-colors duration-200">
        <header className="sticky top-0 z-40 border-b border-border/80 bg-background/85 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-3">
            <div className="inline-flex items-center gap-2 font-display text-[13px] sm:text-[15px] font-extrabold tracking-[-0.02em] text-foreground whitespace-nowrap">
              <span className="h-2.5 w-2.5 rounded-sm bg-primary shrink-0" aria-hidden="true" />
              <span>AETHERVAULT · 个人审美图谱</span>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <ThemeToggle />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setSurfaceMode('studio')}
                className="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground"
              >
                <Layers className="w-3.5 h-3.5 shrink-0" strokeWidth={1.75} />
                <span className="hidden sm:inline">切换至双引擎作品集</span>
                <span className="sm:hidden">作品集</span>
              </Button>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 pt-6 pb-16">
          {loadError && (
            <div
              role="alert"
              className="mb-8 p-5 rounded-xl border border-destructive/60 bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm"
            >
              <div className="space-y-1">
                <div className="text-sm font-semibold text-destructive">数据包加载异常</div>
                <p className="text-xs text-muted-foreground">{loadError}</p>
              </div>
              <Button type="button" onClick={loadShowcaseData} className="shrink-0">
                <RotateCw className="w-3.5 h-3.5" strokeWidth={1.75} />
                <span>重新加载</span>
              </Button>
            </div>
          )}

          {bundle ? (
            <PersonalAestheticAtlas bundle={bundle} />
          ) : (
            <div className="py-20 text-center text-sm text-muted-foreground rounded-xl border border-border bg-card">
              {loading ? '正在加载 500 件个人审美档案、门类分类与深度美学分析...' : '暂无可用展示数据'}
            </div>
          )}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-200">
      {/* Modern Glassmorphic Architectural Studio Masthead */}
      <header className="sticky top-0 z-40 border-b border-border/80 bg-background/85 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="h-14 flex items-center justify-between gap-2 sm:gap-4">
            <button
              type="button"
              onClick={() => handleNavigate('projectA')}
              className="inline-flex items-center gap-2 font-display text-[13px] sm:text-[15px] font-extrabold tracking-[-0.02em] text-foreground whitespace-nowrap hover:text-primary transition-colors shrink-0"
            >
              <span className="h-2.5 w-2.5 rounded-sm bg-primary shrink-0" aria-hidden="true" />
              <span className="sm:hidden">AETHERVAULT</span>
              <span className="hidden sm:inline">AETHERVAULT / TECTONICLOOP</span>
            </button>

            {/* Desktop Tablist with Framer Motion Shared Indicator */}
            <nav
              role="tablist"
              aria-label="主导航"
              className="hidden md:flex items-center h-14 gap-6"
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
                    className={`relative h-full inline-flex items-center text-[13px] font-medium whitespace-nowrap transition-colors ${
                      active
                        ? 'text-foreground font-semibold'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <span>{item.label}</span>
                    {active && (
                      <motion.span
                        layoutId="desktop-nav-underline"
                        transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                        className="absolute bottom-0 left-0 right-0 h-[2px] rounded-full bg-primary"
                      />
                    )}
                  </button>
                );
              })}
            </nav>

            {/* Right Controls: Back to Atlas (local only) + Guided Tour + Theme Toggle + Dual-Mode Switcher */}
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              {hasPersonalAtlas && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setTourOpen(false);
                    setSurfaceMode('atlas');
                  }}
                  aria-label="返回个人审美图谱"
                  className="h-8 px-2 sm:px-2.5 text-xs shrink-0"
                >
                  <ArrowLeft className="w-3.5 h-3.5 shrink-0" strokeWidth={1.75} />
                  <span className="hidden lg:inline">返回个人审美图谱</span>
                  <span className="lg:hidden">图谱</span>
                </Button>
              )}
              <Button
                type="button"
                variant={tourOpen ? 'default' : 'outline'}
                size="sm"
                onClick={handleOpenTour}
                aria-expanded={tourOpen}
                aria-label="打开 3 分钟作品集导览"
                className="h-8 w-8 px-0 sm:w-auto sm:px-2.5 text-xs shrink-0"
              >
                <Compass className="w-3.5 h-3.5 shrink-0" strokeWidth={1.75} />
                <span className="hidden sm:inline">3 分钟导览</span>
              </Button>

              <ThemeToggle />

              <div
                role="group"
                aria-label="运行模式切换"
                className="inline-flex items-center rounded-md border border-border bg-secondary/60 p-0.5 shrink-0"
              >
                <button
                  type="button"
                  aria-pressed={!isLiveEngine}
                  onClick={() => handleSwitchEngineMode('instant')}
                  className={`inline-flex items-center gap-1 sm:gap-1.5 rounded-[5px] px-1.5 sm:px-2.5 py-1 text-xs whitespace-nowrap transition-all ${
                    !isLiveEngine
                      ? 'bg-card text-foreground font-semibold shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      !isLiveEngine ? 'bg-primary' : 'bg-muted-foreground/40'
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
                  className={`inline-flex items-center gap-1 sm:gap-1.5 rounded-[5px] px-1.5 sm:px-2.5 py-1 text-xs whitespace-nowrap transition-all disabled:opacity-60 ${
                    isLiveEngine
                      ? 'bg-card text-teal-ok font-semibold shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      isLiveEngine ? 'bg-teal-ok' : 'bg-muted-foreground/40'
                    }`}
                    aria-hidden="true"
                  />
                  <span className="sm:hidden">{probingEngine ? '...' : 'Live'}</span>
                  <span className="hidden sm:inline">
                    {probingEngine ? '探测中...' : 'Live Engine'}
                  </span>
                </button>
              </div>
            </div>
          </div>

          {/* Mobile Single-Row Scrollable Tab Rail */}
          <nav
            role="tablist"
            aria-label="移动端主导航"
            className="md:hidden flex items-center gap-5 h-10 border-t border-border/80 overflow-x-auto no-scrollbar"
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
                      ? 'border-primary text-foreground font-semibold'
                      : 'border-transparent text-muted-foreground'
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
            className="mb-6 px-4 py-3 rounded-lg border border-border bg-secondary/70 flex items-start justify-between gap-4 text-xs text-foreground shadow-sm"
          >
            <p className="leading-relaxed">{liveNotice}</p>
            <button
              type="button"
              onClick={() => setLiveNotice(null)}
              aria-label="关闭模式提示"
              className="text-muted-foreground hover:text-foreground shrink-0 p-0.5 rounded-sm"
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.75} />
            </button>
          </div>
        )}

        {loadError && (
          <div
            role="alert"
            className="mb-8 p-5 rounded-xl border border-destructive/60 bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm"
          >
            <div className="space-y-1">
              <div className="text-sm font-semibold text-destructive">数据包加载异常</div>
              <p className="text-xs text-muted-foreground">{loadError}</p>
            </div>
            <Button type="button" onClick={loadShowcaseData} className="shrink-0">
              <RotateCw className="w-3.5 h-3.5" strokeWidth={1.75} />
              <span>重新加载</span>
            </Button>
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
            <div className="py-20 text-center text-sm text-muted-foreground rounded-xl border border-border bg-card">
              {loading ? '正在加载跨界美学样本、3D 正交光影流形与黄金锚点...' : '暂无可用展示数据'}
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
            eddBenchmark={eddBenchmark}
            isActive={activeTab === 'techEval'}
          />
        </section>
      </main>

      <GuidedTourPopover
        isOpen={tourOpen}
        stepIndex={tourStep}
        hasBottomDock={activeTab === 'projectA'}
        totalAssets={bundle?.total_assets ?? 500}
        onSelectStep={handleSelectTourStep}
        onClose={handleCloseTour}
      />
    </div>
  );
};

export default App;
