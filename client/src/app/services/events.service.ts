import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { EventApi, EventsListResponse } from '../models/event';

@Injectable({ providedIn: 'root' })
export class EventsService {
  private readonly apiUrl = '/api/events/';

  constructor(private http: HttpClient) {}

  getEvents(): Observable<EventApi[]> {
    return this.http
      .get<EventsListResponse>(this.apiUrl)
      .pipe(map((res) => res.results));
  }
}
