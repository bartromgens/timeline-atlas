import { AsyncPipe } from '@angular/common';
import { ChangeDetectorRef, Component, DestroyRef, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterOutlet } from '@angular/router';
import { Observable } from 'rxjs';
import { MapComponent } from './map/map.component';
import type { CategoryApi, EventApi } from './models/event';
import { EventsService } from './services/events.service';
import { TimelineComponent } from './timeline/timeline.component';

@Component({
  selector: 'app-root',
  imports: [AsyncPipe, FormsModule, RouterOutlet, TimelineComponent, MapComponent],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  readonly projectName = 'Timeline Atlas';
  categories$: Observable<CategoryApi[]>;
  /** Bound to the select; '' = All, otherwise category id as string */
  selectedCategoryValue = '';
  events: EventApi[] = [];
  hoveredEventId: number | null = null;

  constructor(
    private eventsService: EventsService,
    private destroyRef: DestroyRef,
    private cdr: ChangeDetectorRef,
    private route: ActivatedRoute,
    private router: Router,
  ) {
    this.categories$ = this.eventsService.getCategories();
  }

  ngOnInit(): void {
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
