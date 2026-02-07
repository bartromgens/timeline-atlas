export interface EventTimeValue {
  value: string;
  resolution?: string;
}

export interface EventsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: EventApi[];
}

export interface EventApi {
  id: number;
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
  sitelink_count: number;
  pageviews_30d: number;
  backlink_count: number;
  sort_date: string;
  importance_score: number | null;
}

export function parseEventTime(time: EventTimeValue | null): Date | null {
  if (!time?.value) return null;
  const d = new Date(time.value);
  return isNaN(d.getTime()) ? null : d;
}

export function eventStartDate(event: EventApi): Date | null {
  return (
    parseEventTime(event.start_time) ??
    parseEventTime(event.point_in_time) ??
    parseEventTime(event.end_time)
  );
}

export function eventEndDate(event: EventApi): Date | null {
  return (
    parseEventTime(event.end_time) ??
    parseEventTime(event.point_in_time) ??
    parseEventTime(event.start_time)
  );
}
