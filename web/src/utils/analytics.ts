export type ShowcaseEventType =
  | 'mode_switch'
  | 'tab_view'
  | 'tour_step'
  | 'tour_complete'
  | 'rerank_slider'
  | 'ast_compare_switch'
  | 'tectonic_case_switch'
  | 'tectonic_tier_switch'
  | 'tectonic_ve_open';

export interface ShowcaseAnalyticsEvent {
  type: ShowcaseEventType;
  detail?: Record<string, string | number | boolean>;
  timestampMs: number;
}

export interface SessionAnalyticsSummary {
  totalEvents: number;
  countsByType: Partial<Record<ShowcaseEventType, number>>;
  recentEvents: ShowcaseAnalyticsEvent[];
}

const STORAGE_KEY = 'spatial_ai_portfolio_session_events_v1';
const MAX_EVENTS = 120;
const memoryBuffer: ShowcaseAnalyticsEvent[] = [];

function readStoredEvents(): ShowcaseAnalyticsEvent[] {
  if (typeof window === 'undefined') return memoryBuffer;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return memoryBuffer;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : memoryBuffer;
  } catch {
    return memoryBuffer;
  }
}

function writeStoredEvents(events: ShowcaseAnalyticsEvent[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(events));
  } catch {
    // Ignore storage quota or private-mode restrictions; memory buffer remains valid.
  }
}

/**
 * Record an anonymous, strictly local session interaction event (no PII, no external beacon).
 */
export function trackShowcaseEvent(
  type: ShowcaseEventType,
  detail?: Record<string, string | number | boolean>
): void {
  const entry: ShowcaseAnalyticsEvent = {
    type,
    detail,
    timestampMs: Date.now(),
  };

  memoryBuffer.push(entry);
  if (memoryBuffer.length > MAX_EVENTS) {
    memoryBuffer.splice(0, memoryBuffer.length - MAX_EVENTS);
  }

  const existing = readStoredEvents();
  const next = existing === memoryBuffer ? [...memoryBuffer] : [...existing, entry].slice(-MAX_EVENTS);
  writeStoredEvents(next);
}

export function getSessionAnalyticsSummary(): SessionAnalyticsSummary {
  const events = readStoredEvents();
  const countsByType: Partial<Record<ShowcaseEventType, number>> = {};
  for (const evt of events) {
    countsByType[evt.type] = (countsByType[evt.type] ?? 0) + 1;
  }
  return {
    totalEvents: events.length,
    countsByType,
    recentEvents: events.slice(-12),
  };
}
