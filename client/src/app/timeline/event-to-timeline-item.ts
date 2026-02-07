import type { TimelineItem } from 'vis-timeline';
import { colorForCategory } from '../models/category-colors';
import type { EventApi } from '../models/event';
import { endOfDay, eventEndDate, eventStartDate } from '../models/event';

const UNCATEGORIZED_GROUP_ID = 'uncategorized';

const MIN_RANGE_MS = 1000;

export function eventToTimelineItem(event: EventApi): TimelineItem | null {
  const start = eventStartDate(event);
  if (!start) return null;

  let end = eventEndDate(event);
  const noEndDate = !event.end_time?.value;
  if (noEndDate && (end == null || end.getTime() === start.getTime())) {
    end = endOfDay(start);
  }
  const startMs = start.getTime();
  const endMs = end != null ? end.getTime() : startMs;
  const hasRange =
    end != null && endMs > startMs && endMs - startMs >= MIN_RANGE_MS;

  const label = event.title?.trim() || event.wikipedia_title?.trim() || `Event ${event.id}`;
  const description = event.description?.trim();
  const groupId =
    event.category_id != null ? String(event.category_id) : UNCATEGORIZED_GROUP_ID;
  const color = colorForCategory(event.category_id);

  const item: TimelineItem = {
    id: event.id,
    content: label,
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
const MIN_VISIBLE_EVENTS = 20;
const MAX_OVERLAPPING_EVENTS = 12;

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
  return 0.8 * (logSpan - logFocused) / (logMax - logFocused);
}

function maxEventsForVisibleSpan(visibleSpanMs: number): number {
  const yearsVisible = visibleSpanMs / (365.25 * 24 * 60 * 60 * 1000);
  
  if (yearsVisible < 1) {
    return Math.min(150, Math.ceil(80 / yearsVisible));
  } else if (yearsVisible < 5) {
    return Math.ceil(80 / yearsVisible);
  } else if (yearsVisible < 20) {
    return Math.ceil(50 / yearsVisible);
  } else {
    return MIN_VISIBLE_EVENTS;
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

function selectEventsUpToMaxConcurrent(
  events: EventApi[],
  maxConcurrent: number,
): EventApi[] {
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
): TimelineItem[] {
  const minImportance = visibleSpanMs != null ? minImportanceForVisibleSpan(visibleSpanMs) : 0;
  const maxEvents = visibleSpanMs != null ? maxEventsForVisibleSpan(visibleSpanMs) : events.length;
  const maxOverlapping = MAX_OVERLAPPING_EVENTS;

  const pool = visibleWindow
    ? events.filter((e) =>
        eventOverlapsWindow(e, visibleWindow.startMs, visibleWindow.endMs),
      )
    : events;

  const minToShow = visibleWindow
    ? Math.min(MIN_VISIBLE_EVENTS, pool.length)
    : 0;

  if (visibleSpanMs) {
    const years = visibleSpanMs / (365.25 * 24 * 60 * 60 * 1000);
    console.log(`Zoom: ${years.toFixed(1)}y → max ${maxEvents} events, ${MAX_OVERLAPPING_EVENTS} concurrent`);
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
  return result.map(eventToTimelineItem).filter((item): item is TimelineItem => item != null);
}
