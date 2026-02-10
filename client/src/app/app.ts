import { AsyncPipe } from '@angular/common';
import { ChangeDetectorRef, Component, DestroyRef, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatToolbarModule } from '@angular/material/toolbar';
import { filter } from 'rxjs/operators';
import { Observable } from 'rxjs';
import { EventDetailsComponent } from './event-details/event-details.component';
import { MapComponent, type MapBounds } from './map/map.component';
import { AuthService } from './auth/auth.service';
import type { CategoryApi, EventApi, EventTypeApi } from './event/event';
import { EventsService } from './event/events.service';
import { DEFAULT_FILTER_BY_VISIBLE_MAP_AREA } from './timeline/event-to-timeline-item';
import { TimelineComponent } from './timeline/timeline.component';

@Component({
  selector: 'app-root',
  imports: [
    AsyncPipe,
    FormsModule,
    RouterLink,
    RouterOutlet,
    TimelineComponent,
    MapComponent,
    EventDetailsComponent,
    MatToolbarModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatSelectModule,
  ],
  templateUrl: './app.html',
})
export class App implements OnInit {
  readonly projectName = 'Timeline Atlas';
  categories$: Observable<CategoryApi[]>;
  eventTypes$: Observable<EventTypeApi[]>;
  /** Bound to the select; '' = All, 'uncategorized' = no category, else category id */
  selectedCategoryValue = '';
  /** Bound to the event type select; '' = All, else event type id */
  selectedEventTypeValue = '';
  events: EventApi[] = [];
  mapBounds: MapBounds | null = null;
  hoveredEventId: number | null = null;
  selectedEventId: number | null = null;
  filterByVisibleMapArea = DEFAULT_FILTER_BY_VISIBLE_MAP_AREA;
  isAnalyticsPage = false;
  isLoggedIn$: Observable<boolean>;

  constructor(
    private eventsService: EventsService,
    private authService: AuthService,
    private destroyRef: DestroyRef,
    private cdr: ChangeDetectorRef,
    private route: ActivatedRoute,
    private router: Router,
  ) {
    this.isLoggedIn$ = this.authService.isLoggedIn$;
    this.categories$ = this.eventsService.getCategories();
    this.eventTypes$ = this.eventsService.getEventTypes();
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((e) => {
        this.isAnalyticsPage = e.urlAfterRedirects.includes('/analytics');
        this.cdr.detectChanges();
      });
  }

  ngOnInit(): void {
    this.authService.checkAuth();
    this.isAnalyticsPage = this.router.url.includes('/analytics');
    const categoryParam = this.route.snapshot.queryParamMap.get('category');
    if (categoryParam != null && categoryParam !== '') {
      this.selectedCategoryValue = categoryParam;
    }
    const eventTypeParam = this.route.snapshot.queryParamMap.get('event_type');
    if (eventTypeParam != null && eventTypeParam !== '') {
      this.selectedEventTypeValue = eventTypeParam;
    }
    this.loadEvents(this.selectedCategoryFilter(), this.selectedEventTypeFilter());
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const categoryParam = params.get('category');
      const eventTypeParam = params.get('event_type');
      let categoryChanged = false;
      let eventTypeChanged = false;
      if (categoryParam != null && categoryParam !== '') {
        if (categoryParam !== this.selectedCategoryValue) {
          this.selectedCategoryValue = categoryParam;
          categoryChanged = true;
        }
      } else if (this.selectedCategoryValue !== '') {
        this.selectedCategoryValue = '';
        categoryChanged = true;
      }
      if (eventTypeParam != null && eventTypeParam !== '') {
        if (eventTypeParam !== this.selectedEventTypeValue) {
          this.selectedEventTypeValue = eventTypeParam;
          eventTypeChanged = true;
        }
      } else if (this.selectedEventTypeValue !== '') {
        this.selectedEventTypeValue = '';
        eventTypeChanged = true;
      }
      if (categoryChanged || eventTypeChanged) {
        this.loadEvents(this.selectedCategoryFilter(), this.selectedEventTypeFilter());
        this.cdr.detectChanges();
      }
    });
  }

  onBoundsChange(bounds: MapBounds): void {
    setTimeout(() => {
      this.mapBounds = bounds;
      this.cdr.detectChanges();
    }, 0);
  }

  onTimelineItemHover(eventId: number | null): void {
    this.hoveredEventId = eventId;
  }

  onMapMarkerSelect(eventId: number): void {
    this.selectedEventId = this.selectedEventId === eventId ? null : eventId;
  }

  onTimelineItemSelect(eventId: number): void {
    this.selectedEventId = this.selectedEventId === eventId ? null : eventId;
  }

  get selectedEvent(): EventApi | null {
    if (this.selectedEventId == null) return null;
    return this.events.find((e) => e.id === this.selectedEventId) ?? null;
  }

  onCategoryChange(): void {
    this.loadEvents(this.selectedCategoryFilter(), this.selectedEventTypeFilter());
    this.updateQueryParams();
  }

  onEventTypeChange(): void {
    this.loadEvents(this.selectedCategoryFilter(), this.selectedEventTypeFilter());
    this.updateQueryParams();
  }

  private updateQueryParams(): void {
    const categoryParam =
      this.selectedCategoryValue === '' ? null : this.selectedCategoryValue;
    const eventTypeParam =
      this.selectedEventTypeValue === '' ? null : this.selectedEventTypeValue;
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { category: categoryParam, event_type: eventTypeParam },
      queryParamsHandling: '',
      replaceUrl: true,
    });
  }

  /** Parse current select value for API: null = All, 'uncategorized', or category id. */
  private selectedCategoryFilter(): number | null | 'uncategorized' {
    const v = this.selectedCategoryValue;
    if (v === '' || v == null) return null;
    if (v === 'uncategorized') return 'uncategorized';
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }

  /** Parse current event type select value for API: null = All, else event type id. */
  private selectedEventTypeFilter(): number | null {
    const v = this.selectedEventTypeValue;
    if (v === '' || v == null) return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }

  private loadRequestId = 0;

  private loadEvents(
    categoryFilter: number | null | 'uncategorized',
    eventTypeFilter: number | null = null,
  ): void {
    const requestId = ++this.loadRequestId;
    this.eventsService
      .getEvents(categoryFilter, eventTypeFilter)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (events) => {
          if (requestId === this.loadRequestId) {
            this.events = events;
            this.selectedEventId = null;
            this.cdr.detectChanges();
          }
        },
        error: () => {
          if (requestId === this.loadRequestId) {
            this.events = [];
            this.cdr.detectChanges();
          }
        },
      });
  }
}
