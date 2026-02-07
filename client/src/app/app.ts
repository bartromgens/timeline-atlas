import { AsyncPipe } from '@angular/common';
import { Component, DestroyRef, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterOutlet } from '@angular/router';
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

  constructor(
    private eventsService: EventsService,
    private destroyRef: DestroyRef,
  ) {
    this.categories$ = this.eventsService.getCategories();
  }

  ngOnInit(): void {
    this.loadEvents(this.selectedCategoryIdFromValue());
  }

  onCategoryChange(): void {
    this.loadEvents(this.selectedCategoryIdFromValue());
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
          if (requestId === this.loadRequestId) this.events = events;
        },
        error: () => {
          if (requestId === this.loadRequestId) this.events = [];
        },
      });
  }
}
