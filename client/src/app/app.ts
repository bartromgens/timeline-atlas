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
import { MapComponent } from './map/map.component';
import { AuthService } from './auth/auth.service';
import type { CategoryApi, EventApi } from './event/event';
import { EventsService } from './event/events.service';
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
  /** Bound to the select; '' = All, otherwise category id as string */
  selectedCategoryValue = '';
  events: EventApi[] = [];
  hoveredEventId: number | null = null;
  selectedEventId: number | null = null;
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
    this.loadEvents(this.selectedCategoryIdFromValue());
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const categoryParam = params.get('category');
      if (categoryParam != null && categoryParam !== '') {
        if (categoryParam !== this.selectedCategoryValue) {
          this.selectedCategoryValue = categoryParam;
          this.loadEvents(this.selectedCategoryIdFromValue());
          this.cdr.detectChanges();
        }
      } else if (this.selectedCategoryValue !== '') {
        this.selectedCategoryValue = '';
        this.loadEvents(null);
        this.cdr.detectChanges();
      }
    });
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
    const id = this.selectedCategoryIdFromValue();
    this.loadEvents(id);
    const categoryParam = this.selectedCategoryValue === '' ? null : this.selectedCategoryValue;
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { category: categoryParam },
      queryParamsHandling: '',
      replaceUrl: true,
    });
  }

  /** Parse current select value to category id for API (null = All). */
  private selectedCategoryIdFromValue(): number | null {
    const v = this.selectedCategoryValue;
    return v === '' ? null : Number(v);
  }

  private loadRequestId = 0;

  private loadEvents(categoryId: number | null): void {
    const requestId = ++this.loadRequestId;
    this.eventsService
      .getEvents(categoryId)
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
