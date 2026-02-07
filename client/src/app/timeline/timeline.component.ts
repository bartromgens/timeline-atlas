import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { Timeline } from 'vis-timeline';
import type { DataGroup } from 'vis-timeline';
import { colorForCategory } from '../models/category-colors';
import type { CategoryApi, EventApi } from '../models/event';
import { eventEndDate, eventStartDate } from '../models/event';
import {
  eventsToTimelineItems,
  MIN_SPAN_MS,
  type VisibleWindow,
} from './event-to-timeline-item';

const UNCATEGORIZED_GROUP_ID = 'uncategorized';

@Component({
  selector: 'app-timeline',
  standalone: true,
  imports: [],
  templateUrl: './timeline.component.html',
  styleUrl: './timeline.component.css',
})
export class TimelineComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('timelineContainer') timelineContainer!: ElementRef<HTMLElement>;
  @Input() events: EventApi[] = [];
  @Input() categories: CategoryApi[] = [];

  private timeline: Timeline | null = null;
  private rangeChangedHandler = (): void => this.updateItemsForWindow();

  ngAfterViewInit(): void {
    const container = this.timelineContainer?.nativeElement;
    if (!container) return;

    this.timeline = new Timeline(container, [], [], {
      editable: false,
      zoomKey: 'ctrlKey',
      groupHeightMode: 'fitItems',
      stack: true,
      stackSubgroups: false,
      margin: {
        item: {
          horizontal: 0,
          vertical: 5,
        },
      },
    });
    this.timeline.on('rangechanged', this.rangeChangedHandler);
    this.applyEvents();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['events'] || changes['categories']) {
      this.applyEvents();
    }
  }

  private buildGroups(): DataGroup[] {
    const presentIds = new Set(
      this.events.map((e) => e.category_id).filter((id): id is number => id != null),
    );
    const hasUncategorized = this.events.some((e) => e.category_id == null);
    const byId = new Map(this.categories.map((c) => [c.id, c]));
    const fromCategories = this.categories.filter((c) => presentIds.has(c.id)).map((c) => c.id);
    const missingIds = [...presentIds].filter((id) => !byId.has(id));
    const ordered: (number | null)[] = [
      ...fromCategories,
      ...missingIds.sort((a, b) => a - b),
      ...(hasUncategorized ? [null] : []),
    ];
    return ordered.map((categoryId) => {
      const id = categoryId != null ? String(categoryId) : UNCATEGORIZED_GROUP_ID;
      const cat = categoryId != null ? byId.get(categoryId) : null;
      const name =
        categoryId == null
          ? 'Uncategorized'
          : (cat?.name ?? cat?.wikidata_id ?? `Category ${categoryId}`);
      const color = colorForCategory(categoryId);
      return {
        id,
        content: name,
        style: `border-left: 4px solid ${color};`,
      };
    });
  }

  private applyEvents(): void {
    if (!this.timeline) return;
    if (this.events.length === 0) {
      this.timeline.setGroups([]);
      this.timeline.setItems([]);
      return;
    }
    this.timeline.setGroups(this.buildGroups());
    const range = this.eventDateRange();
    if (range) {
      this.timeline.setWindow(range.start, range.end, { animation: false });
      const spanMs = Math.max(range.end.getTime() - range.start.getTime(), MIN_SPAN_MS);
      const visibleWindow: VisibleWindow = {
        startMs: range.start.getTime(),
        endMs: range.end.getTime(),
      };
      this.timeline.setItems(eventsToTimelineItems(this.events, spanMs, visibleWindow));
    } else {
      this.timeline.setItems([]);
    }
  }

  private eventDateRange(): { start: Date; end: Date } | null {
    let minMs = Infinity;
    let maxMs = -Infinity;
    for (const e of this.events) {
      const start = eventStartDate(e);
      if (!start) continue;
      const end = eventEndDate(e) ?? start;
      const startMs = start.getTime();
      const endMs = end.getTime();
      minMs = Math.min(minMs, startMs);
      maxMs = Math.max(maxMs, endMs);
    }
    if (minMs === Infinity) return null;
    if (minMs === maxMs) {
      const half = MIN_SPAN_MS / 2;
      return {
        start: new Date(minMs - half),
        end: new Date(minMs + half),
      };
    }
    return { start: new Date(minMs), end: new Date(maxMs) };
  }

  private updateItemsForWindow(): void {
    if (!this.timeline || this.events.length === 0) return;
    const window = this.timeline.getWindow();
    const visibleSpanMs = window.end.getTime() - window.start.getTime();
    const visibleWindow: VisibleWindow = {
      startMs: window.start.getTime(),
      endMs: window.end.getTime(),
    };
    this.timeline.setItems(eventsToTimelineItems(this.events, visibleSpanMs, visibleWindow));
  }

  ngOnDestroy(): void {
    if (this.timeline) {
      this.timeline.off('rangechanged', this.rangeChangedHandler);
      this.timeline.destroy();
    }
    this.timeline = null;
  }
}
