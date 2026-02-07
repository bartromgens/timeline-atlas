import type { TimelineItem } from 'vis-timeline';
import type { EventApi } from '../models/event';
import { eventEndDate, eventStartDate } from '../models/event';

export function eventToTimelineItem(event: EventApi): TimelineItem | null {
  const start = eventStartDate(event);
  if (!start) return null;

  const end = eventEndDate(event);
  const hasRange = end != null && start.getTime() !== end.getTime();

  const content = event.title?.trim() || event.wikipedia_title?.trim() || `Event ${event.id}`;

  const item: TimelineItem = {
    id: event.id,
    content,
    start: start.toISOString(),
    title: event.description?.trim() || undefined,
  };

  if (hasRange) {
    item.end = end.toISOString();
    item.type = 'range';
  } else {
    item.type = 'point';
  }

  return item;
}

const MIN_SPAN_MS = 24 * 60 * 60 * 1000;
const MAX_SPAN_MS = 30 * 365.25 * 24 * 60 * 60 * 1000;
const MIN_VISIBLE_EVENTS = 8;

export function minImportanceForVisibleSpan(visibleSpanMs: number): number {
  if (visibleSpanMs <= MIN_SPAN_MS) return 0;
  if (visibleSpanMs >= MAX_SPAN_MS) return 1;
  const logMin = Math.log(MIN_SPAN_MS);
  const logMax = Math.log(MAX_SPAN_MS);
  const logSpan = Math.log(visibleSpanMs);
  return (logSpan - logMin) / (logMax - logMin);
}

export function eventsToTimelineItems(events: EventApi[], visibleSpanMs?: number): TimelineItem[] {
  const minImportance = visibleSpanMs != null ? minImportanceForVisibleSpan(visibleSpanMs) : 0;
  const aboveThreshold = events.filter((e) => (e.importance_score ?? 0) >= minImportance);
  const byImportance = [...aboveThreshold].sort(
    (a, b) => (b.importance_score ?? -Infinity) - (a.importance_score ?? -Infinity),
  );
  const toShow =
    byImportance.length >= MIN_VISIBLE_EVENTS
      ? byImportance
      : [...events]
          .sort((a, b) => (b.importance_score ?? -Infinity) - (a.importance_score ?? -Infinity))
          .slice(0, MIN_VISIBLE_EVENTS);
  return toShow.map(eventToTimelineItem).filter((item): item is TimelineItem => item != null);
}
