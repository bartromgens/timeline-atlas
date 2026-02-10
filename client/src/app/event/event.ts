export interface EventTimeValue {
  value: string;
  resolution?: string;
}

export interface CategoryApi {
  id: number;
  name: string;
  wikidata_id: string;
}

export interface EventsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: EventApi[];
}

export interface EventApi {
  id: number;
  category_id: number | null;
  title: string;
  description: string;
  point_in_time: EventTimeValue | null;
  start_time: EventTimeValue | null;
  end_time: EventTimeValue | null;
  location_name: string;
  location_qid: string;
  location_lat: number | null;
  location_lon: number | null;
  wikidata_id: string;
  wikidata_url: string;
  wikipedia_url: string;
  wikipedia_title: string;
  wikipedia_extract: string;
  sitelink_count: number;
  pageviews_30d: number;
  backlink_count: number;
  sort_date: string;
  importance_score: number | null;
}

/**
 * Parse ISO date string including BCE (negative year). JS Date often fails on
 * BCE strings; we parse components and use Date.UTC(year, monthIndex, day).
 */
function parseEventTimeValue(value: string): Date | null {
  const d = new Date(value);
  if (!isNaN(d.getTime())) return d;
  const m = value.match(/^(-?\d{4})(?:-(\d{2})(?:-(\d{2}))?)?/);
  if (!m) return null;
  const year = parseInt(m[1], 10);
  const month = m[2] ? parseInt(m[2], 10) - 1 : 0;
  const day = m[3] ? parseInt(m[3], 10) : 1;
  const ms = Date.UTC(year, month, day, 0, 0, 0, 0);
  return isFinite(ms) ? new Date(ms) : null;
}

export function parseEventTime(time: EventTimeValue | null): Date | null {
  if (!time?.value) return null;
  return parseEventTimeValue(time.value);
}

function hasStartAndEnd(event: EventApi): boolean {
  return !!(event.start_time?.value && event.end_time?.value);
}

export function endOfDay(date: Date): Date {
  const d = new Date(date);
  d.setUTCHours(23, 59, 59, 999);
  return d;
}

export function eventStartDate(event: EventApi): Date | null {
  if (hasStartAndEnd(event)) {
    return parseEventTime(event.start_time);
  }
  return (
    parseEventTime(event.start_time) ??
    parseEventTime(event.point_in_time) ??
    parseEventTime(event.end_time)
  );
}

export function eventEndDate(event: EventApi): Date | null {
  if (hasStartAndEnd(event)) {
    return parseEventTime(event.end_time);
  }
  return (
    parseEventTime(event.end_time) ??
    parseEventTime(event.point_in_time) ??
    parseEventTime(event.start_time)
  );
}
