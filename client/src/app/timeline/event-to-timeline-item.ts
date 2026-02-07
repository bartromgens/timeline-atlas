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

const MIN_IMPORTANCE_FOR_TIMELINE = 0.2;

export function eventsToTimelineItems(events: EventApi[]): TimelineItem[] {
  const aboveThreshold = events.filter(
    (e) => (e.importance_score ?? 0) >= MIN_IMPORTANCE_FOR_TIMELINE,
  );
  const byImportance = [...aboveThreshold].sort(
    (a, b) => (b.importance_score ?? -Infinity) - (a.importance_score ?? -Infinity),
  );
  return byImportance.map(eventToTimelineItem).filter((item): item is TimelineItem => item != null);
}
