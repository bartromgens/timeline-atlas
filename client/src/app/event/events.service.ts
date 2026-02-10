import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { EMPTY, Observable } from 'rxjs';
import { expand, map, reduce } from 'rxjs/operators';
import {
  CategoryApi,
  EventApi,
  EventTypeApi,
  EventsListResponse,
} from './event';

function parseCategoriesResponse(body: CategoryApi[] | { results?: CategoryApi[] }): CategoryApi[] {
  if (Array.isArray(body)) return body;
  if (body?.results && Array.isArray(body.results)) return body.results;
  return [];
}

function parseEventTypesResponse(
  body: EventTypeApi[] | { results?: EventTypeApi[] },
): EventTypeApi[] {
  if (Array.isArray(body)) return body;
  if (body?.results && Array.isArray(body.results)) return body.results;
  return [];
}

@Injectable({ providedIn: 'root' })
export class EventsService {
  private readonly apiUrl = '/api/events/';
  private readonly categoriesUrl = '/api/categories/';
  private readonly eventTypesUrl = '/api/event-types/';

  constructor(private http: HttpClient) {}

  getCategories(): Observable<CategoryApi[]> {
    return this.http
      .get<CategoryApi[] | { results: CategoryApi[] }>(this.categoriesUrl)
      .pipe(map(parseCategoriesResponse));
  }

  getEventTypes(): Observable<EventTypeApi[]> {
    return this.http
      .get<EventTypeApi[] | { results: EventTypeApi[] }>(this.eventTypesUrl)
      .pipe(map(parseEventTypesResponse));
  }

  getEvents(
    categoryId: number | null | 'uncategorized' = null,
    eventTypeId: number | null = null,
  ): Observable<EventApi[]> {
    let params = new HttpParams();
    if (categoryId === 'uncategorized') {
      params = params.set('category', 'uncategorized');
    } else if (categoryId != null) {
      params = params.set('category', String(categoryId));
    }
    if (eventTypeId != null) {
      params = params.set('event_type', String(eventTypeId));
    }
    return this.http.get<EventsListResponse>(this.apiUrl, { params }).pipe(
      expand((res) => {
        const nextUrl = res.next ? this.nextUrlSameOrigin(res.next) : null;
        return nextUrl ? this.http.get<EventsListResponse>(nextUrl) : EMPTY;
      }),
      reduce((acc: EventApi[], res) => acc.concat(res.results), []),
    );
  }

  private nextUrlSameOrigin(next: string): string {
    try {
      const u = new URL(next, window.location.origin);
      return u.pathname + u.search;
    } catch {
      return next.startsWith('/') ? next : `/${next}`;
    }
  }
}
