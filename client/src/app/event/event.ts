export interface EventTimeValue {
  value: string;
  resolution?: string;
}

export interface CategoryApi {
  id: number;
  name: string;
  wikidata_id: string;
}

export interface EventTypeApi {
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
  event_type_id: number | null;
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

/** Unicode minus (U+2212) used by Wikidata for BCE. */
const UNICODE_MINUS = '\u2212';

/**
 * Parse ISO date string including BCE (negative year). JS Date often fails on
 * BCE strings; we parse components. Date.UTC(year, ...) treats 0–99 as 1900+year,
 * so we build the date via setUTCFullYear for correct BCE and 1–99 AD.
 * Year regex uses \d{1,4} so short BCE years (e.g. "-60") are parsed as -60, not 1960.
 */
function parseEventTimeValue(value: string): Date | null {
  const normalized = value.replace(UNICODE_MINUS, '-');
  const m = normalized.match(/^(-?\d{1,4})(?:-(\d{2})(?:-(\d{2}))?)?/);
  if (m) {
    const year = parseInt(m[1], 10);
    const month = m[2] ? parseInt(m[2], 10) - 1 : 0;
    const day = m[3] ? parseInt(m[3], 10) : 1;
    const base = new Date(0);
    base.setUTCFullYear(year, month, day);
    base.setUTCHours(0, 0, 0, 0);
    if (isFinite(base.getTime())) return base;
  }
  const d = new Date(normalized);
  return !isNaN(d.getTime()) ? d : null;
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
