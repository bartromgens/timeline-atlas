import type { TimelineItem } from 'vis-timeline';
import { colorForCategory } from '../models/category-colors';
import type { EventApi } from '../event/event';
import { endOfDay, eventEndDate, eventStartDate } from '../event/event';

const UNCATEGORIZED_GROUP_ID = 'uncategorized';

const MIN_RANGE_MS = 1000;

export interface EventToTimelineItemOptions {
  hideLabel?: boolean;
}

export function eventToTimelineItem(
  event: EventApi,
  options?: EventToTimelineItemOptions,
): TimelineItem | null {
  const start = eventStartDate(event);
  if (!start) return null;

  let end = eventEndDate(event);
  const noEndDate = !event.end_time?.value;
  if (noEndDate && (end == null || end.getTime() === start.getTime())) {
    end = endOfDay(start);
  }
  const startMs = start.getTime();
  const endMs = end != null ? end.getTime() : startMs;
  const hasRange = end != null && endMs > startMs && endMs - startMs >= MIN_RANGE_MS;

  const label = event.title?.trim() || event.wikipedia_title?.trim() || `Event ${event.id}`;
  const description = event.description?.trim();
  const groupId = event.category_id != null ? String(event.category_id) : UNCATEGORIZED_GROUP_ID;
  const color = colorForCategory(event.category_id);
  const content = options?.hideLabel ? '' : label;

  const item: TimelineItem = {
    id: event.id,
    content,
    start: start.toISOString(),
    title: description ?? '',
    group: groupId,
    style: `border-left: 4px solid ${color}; background-color: ${color}22;`,
  };

  if (hasRange && end != null) {
    item.end = end.toISOString();
    item.type = 'range';
  } else {
    item.type = 'point';
  }

  return item;
}

export const MIN_SPAN_MS = 24 * 60 * 60 * 1000;
const MAX_SPAN_MS = 100 * 365.25 * 24 * 60 * 60 * 1000;
const FOCUSED_SPAN_MS = 10 * 365.25 * 24 * 60 * 60 * 1000;

export const DEFAULT_MIN_VISIBLE_EVENTS = 30;
export const DEFAULT_MAX_OVERLAPPING_EVENTS = 12;
export const DEFAULT_SHORT_EVENT_FRACTION = 0.05;

/** Hide events whose duration exceeds this multiple of the visible range. */
export const DEFAULT_MAX_EVENT_SPAN_VISIBLE_RATIO = 3;

export interface TimelineDisplayOptions {
  minVisibleEvents: number;
  maxOverlappingEvents: number;
  shortEventFraction: number;
  maxEventSpanVisibleRatio: number;
}

export interface VisibleWindow {
  startMs: number;
  endMs: number;
}

function eventOverlapsWindow(event: EventApi, startMs: number, endMs: number): boolean {
  const start = eventStartDate(event);
  if (!start) return false;
  const end = eventEndDate(event) ?? start;
  const eventStartMs = start.getTime();
  const eventEndMs = end.getTime();
  return eventStartMs <= endMs && eventEndMs >= startMs;
}

export function minImportanceForVisibleSpan(visibleSpanMs: number): number {
  if (visibleSpanMs <= FOCUSED_SPAN_MS) return 0;
  if (visibleSpanMs >= MAX_SPAN_MS) return 0.8;
  const logFocused = Math.log(FOCUSED_SPAN_MS);
  const logMax = Math.log(MAX_SPAN_MS);
  const logSpan = Math.log(visibleSpanMs);
  return (0.8 * (logSpan - logFocused)) / (logMax - logFocused);
}

function maxEventsForVisibleSpan(
  visibleSpanMs: number,
  minVisibleEvents: number = DEFAULT_MIN_VISIBLE_EVENTS,
): number {
  const yearsVisible = visibleSpanMs / (365.25 * 24 * 60 * 60 * 1000);

  if (yearsVisible < 1) {
    return Math.min(225, Math.ceil(120 / yearsVisible));
  } else if (yearsVisible < 5) {
    return Math.ceil(120 / yearsVisible);
  } else if (yearsVisible < 20) {
    return Math.ceil(75 / yearsVisible);
  } else {
    return minVisibleEvents;
  }
}

interface TimeRange {
  start: number;
  end: number;
  event: EventApi;
}

function timeRangeForEvent(event: EventApi): TimeRange | null {
  const start = eventStartDate(event);
  if (!start) return null;
  const rawEnd = eventEndDate(event) ?? start;
  const startMs = start.getTime();
  const endMs = Math.max(startMs, rawEnd.getTime());
  return { start: startMs, end: endMs, event };
}

function selectEventsUpToMaxConcurrent(events: EventApi[], maxConcurrent: number): EventApi[] {
  const byImportance = [...events].sort(
    (a, b) => (b.importance_score ?? -Infinity) - (a.importance_score ?? -Infinity),
  );
  const selected: TimeRange[] = [];

  for (const candidate of byImportance) {
    const candidateRange = timeRangeForEvent(candidate);
    if (!candidateRange) continue;

    const allRanges = [...selected, candidateRange];
    const criticalPoints = [...new Set(allRanges.flatMap((r) => [r.start, r.end]))].sort(
      (a, b) => a - b,
    );

    let maxConcurrentWithCandidate = 0;
    for (const point of criticalPoints) {
      let concurrent = 0;
      for (const range of allRanges) {
        if (point >= range.start && point <= range.end) concurrent++;
      }
      maxConcurrentWithCandidate = Math.max(maxConcurrentWithCandidate, concurrent);
    }

    if (maxConcurrentWithCandidate <= maxConcurrent) {
      selected.push(candidateRange);
    }
  }

  return selected.map((r) => r.event);
}

export function eventsToTimelineItems(
  events: EventApi[],
  visibleSpanMs?: number,
  visibleWindow?: VisibleWindow,
  options?: Partial<TimelineDisplayOptions>,
): TimelineItem[] {
  const minVisibleEvents = options?.minVisibleEvents ?? DEFAULT_MIN_VISIBLE_EVENTS;
  const maxOverlapping = options?.maxOverlappingEvents ?? DEFAULT_MAX_OVERLAPPING_EVENTS;
  const shortEventFraction = options?.shortEventFraction ?? DEFAULT_SHORT_EVENT_FRACTION;
  const maxEventSpanVisibleRatio =
    options?.maxEventSpanVisibleRatio ?? DEFAULT_MAX_EVENT_SPAN_VISIBLE_RATIO;

  const minImportance = visibleSpanMs != null ? minImportanceForVisibleSpan(visibleSpanMs) : 0;
  const maxEvents =
    visibleSpanMs != null
      ? maxEventsForVisibleSpan(visibleSpanMs, minVisibleEvents)
      : events.length;

  const overlapping = visibleWindow
    ? events.filter((e) => eventOverlapsWindow(e, visibleWindow.startMs, visibleWindow.endMs))
    : events;

  const maxEventSpanMs =
    visibleSpanMs != null && visibleSpanMs > 0
      ? maxEventSpanVisibleRatio * visibleSpanMs
      : Infinity;
  const pool =
    maxEventSpanMs < Infinity
      ? overlapping.filter((e) => {
          const range = timeRangeForEvent(e);
          if (!range) return true;
          return range.end - range.start <= maxEventSpanMs;
        })
      : overlapping;

  const minToShow = visibleWindow ? Math.min(minVisibleEvents, pool.length) : 0;

  if (visibleSpanMs) {
    const years = visibleSpanMs / (365.25 * 24 * 60 * 60 * 1000);
    console.log(
      `Zoom: ${years.toFixed(1)}y → max ${maxEvents} events, ${maxOverlapping} concurrent`,
    );
  }

  const aboveThreshold = pool.filter((e) => (e.importance_score ?? 0) >= minImportance);
  const byImportance = [...aboveThreshold].sort(
    (a, b) => (b.importance_score ?? -Infinity) - (a.importance_score ?? -Infinity),
  );

  const takeCount = Math.max(minToShow, Math.min(maxEvents, byImportance.length));
  const topEvents = byImportance.slice(0, takeCount);
  const toShow =
    topEvents.length >= minToShow || minToShow === 0
      ? topEvents
      : [...pool]
          .sort((a, b) => (b.importance_score ?? -Infinity) - (a.importance_score ?? -Infinity))
          .slice(0, Math.max(minToShow, topEvents.length));

  const result = selectEventsUpToMaxConcurrent(toShow, maxOverlapping);
  const hideLabelByEventId = computeHideLabelByEventId(result, visibleWindow, shortEventFraction);
  return result
    .map((event) =>
      eventToTimelineItem(event, {
        hideLabel: hideLabelByEventId.get(event.id) ?? false,
      }),
    )
    .filter((item): item is TimelineItem => item != null);
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function computeHideLabelByEventId(
  events: EventApi[],
  visibleWindow: VisibleWindow | undefined,
  shortEventFraction: number = DEFAULT_SHORT_EVENT_FRACTION,
): Map<number, boolean> {
  const out = new Map<number, boolean>();
  if (!visibleWindow || events.length === 0) return out;
  const visibleSpanMs = visibleWindow.endMs - visibleWindow.startMs;
  if (visibleSpanMs <= 0) return out;

  const importanceScores = events.map((e) => e.importance_score ?? 0);
  const medianImportance = median(importanceScores);

  for (const event of events) {
    const start = eventStartDate(event);
    if (!start) continue;
    let end = eventEndDate(event) ?? start;
    const noEndDate = !event.end_time?.value;
    if (noEndDate && end.getTime() === start.getTime()) {
      end = endOfDay(start);
    }
    const eventSpanMs = Math.max(0, end.getTime() - start.getTime());
    const short = eventSpanMs / visibleSpanMs < shortEventFraction;
    const lowImportance = (event.importance_score ?? 0) < medianImportance;
    out.set(event.id, short && lowImportance);
  }
  return out;
}
