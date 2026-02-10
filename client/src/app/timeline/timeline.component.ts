import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { Timeline } from 'vis-timeline';
import type { DataGroup, TimelineItem } from 'vis-timeline';
import { colorForCategory } from '../models/category-colors';
import type { CategoryApi, EventApi } from '../event/event';
import { eventEndDate, eventStartDate } from '../event/event';
import {
  eventsToTimelineItems,
  MIN_SPAN_MS,
  type VisibleWindow,
  type TimelineDisplayOptions,
  DEFAULT_FILTER_BY_VISIBLE_MAP_AREA,
  DEFAULT_MAX_EVENT_SPAN_VISIBLE_RATIO,
  DEFAULT_MAX_OVERLAPPING_EVENTS,
  DEFAULT_MIN_VISIBLE_EVENTS,
  DEFAULT_SHORT_EVENT_FRACTION,
} from './event-to-timeline-item';
import type { MapBounds } from '../map/map.component';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { TimelineSettingsComponent } from './timeline-settings.component';

const UNCATEGORIZED_GROUP_ID = 'uncategorized';

function endOfToday(): Date {
  const d = new Date();
  d.setHours(23, 59, 59, 999);
  return d;
}

@Component({
  selector: 'app-timeline',
  standalone: true,
  imports: [TimelineSettingsComponent, MatButtonModule, MatIconModule],
  templateUrl: './timeline.component.html',
  styleUrl: './timeline.component.css',
})
export class TimelineComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('timelineContainer') timelineContainer!: ElementRef<HTMLElement>;
  @Input() events: EventApi[] = [];
  @Input() categories: CategoryApi[] = [];
  @Input() mapBounds: MapBounds | null = null;
  @Input() highlightedEventId: number | null = null;
  @Output() timelineItemHover = new EventEmitter<number | null>();
  @Output() timelineItemSelect = new EventEmitter<number>();
  @Output() filterByVisibleMapAreaChange = new EventEmitter<boolean>();

  settingsOpen = false;
  displayOptions: TimelineDisplayOptions = {
    minVisibleEvents: DEFAULT_MIN_VISIBLE_EVENTS,
    maxOverlappingEvents: DEFAULT_MAX_OVERLAPPING_EVENTS,
    shortEventFraction: DEFAULT_SHORT_EVENT_FRACTION,
    maxEventSpanVisibleRatio: DEFAULT_MAX_EVENT_SPAN_VISIBLE_RATIO,
    filterByVisibleMapArea: DEFAULT_FILTER_BY_VISIBLE_MAP_AREA,
  };

  private timeline: Timeline | null = null;
  private currentItemIds = new Set<number>();
  private rangeChangedHandler = (): void => this.updateItemsForWindow();
  private itemOverHandler = (props: { item: number | string }): void => {
    const id = typeof props.item === 'number' ? props.item : Number(props.item);
    this.timelineItemHover.emit(id);
  };
  private itemOutHandler = (): void => this.timelineItemHover.emit(null);
  private itemClickHandler = (props: { item: number | string }): void => {
    const id = typeof props.item === 'number' ? props.item : Number(props.item);
    this.timelineItemSelect.emit(id);
  };

  ngAfterViewInit(): void {
    const container = this.timelineContainer?.nativeElement;
    if (!container) return;

    this.timeline = new Timeline(container, [], [], {
      editable: false,
      selectable: true,
      zoomKey: 'ctrlKey',
      groupHeightMode: 'fitItems',
      stack: true,
      stackSubgroups: false,
      orientation: { axis: 'top', item: 'top' },
      margin: {
        item: {
          horizontal: 0,
          vertical: 5,
        },
      },
    });
    this.timeline.on('rangechanged', this.rangeChangedHandler);
    this.timeline.on('itemover', this.itemOverHandler);
    this.timeline.on('itemout', this.itemOutHandler);
    this.timeline.on('click', this.itemClickHandler);
    this.applyEvents();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['events'] || changes['categories']) {
      this.applyEvents();
    } else if (changes['mapBounds']) {
      this.updateItemsForWindow();
    }
    if (changes['highlightedEventId']) {
      this.scheduleApplySelection();
    }
  }

  private eventsForTimeline(): EventApi[] {
    if (!this.displayOptions.filterByVisibleMapArea || this.mapBounds == null) {
      return this.events;
    }
    const b = this.mapBounds;
    return this.events.filter((e) => {
      if (
        e.location_lat == null ||
        e.location_lon == null ||
        !Number.isFinite(e.location_lat) ||
        !Number.isFinite(e.location_lon)
      ) {
        return false;
      }
      return (
        e.location_lat >= b.south &&
        e.location_lat <= b.north &&
        e.location_lon >= b.west &&
        e.location_lon <= b.east
      );
    });
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
    ].reverse();
    return ordered.map((categoryId, index) => {
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
        order: index,
      };
    });
  }

  private applyEvents(): void {
    if (!this.timeline) return;
    const filtered = this.eventsForTimeline();
    if (this.events.length === 0) {
      this.currentItemIds.clear();
      this.timeline.setGroups([]);
      this.timeline.setItems([]);
      this.scheduleApplySelection();
      return;
    }
    this.timeline.setGroups(this.buildGroups());
    const range = this.eventDateRange(filtered);
    if (range) {
      const spanMs = Math.max(range.end.getTime() - range.start.getTime(), MIN_SPAN_MS);
      const visibleWindow: VisibleWindow = {
        startMs: range.start.getTime(),
        endMs: range.end.getTime(),
      };
      const items = eventsToTimelineItems(filtered, spanMs, visibleWindow, this.displayOptions);
      this.currentItemIds = new Set(items.map((i) => Number(i.id)));
      const windowRange = this.dateRangeFromItems(items) ?? range;
      const maxDate = endOfToday();
      const windowEnd =
        windowRange.end.getTime() > maxDate.getTime() ? maxDate : windowRange.end;
      this.timeline.setWindow(windowRange.start, windowEnd, { animation: false });
      this.timeline.setItems(items);
    } else {
      this.currentItemIds.clear();
      this.timeline.setItems([]);
    }
    this.scheduleApplySelection();
  }

  private dateRangeFromItems(
    items: TimelineItem[],
  ): { start: Date; end: Date } | null {
    if (items.length === 0) return null;
    let minMs = Infinity;
    let maxMs = -Infinity;
    for (const item of items) {
      const startMs = new Date(item.start as string).getTime();
      if (!Number.isFinite(startMs)) continue;
      const endMs = item.end != null ? new Date(item.end as string).getTime() : startMs;
      minMs = Math.min(minMs, startMs);
      maxMs = Math.max(maxMs, Number.isFinite(endMs) ? endMs : startMs);
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

  private eventDateRange(events: EventApi[]): { start: Date; end: Date } | null {
    let minMs = Infinity;
    let maxMs = -Infinity;
    for (const e of events) {
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
    const filtered = this.eventsForTimeline();
    if (!this.timeline || this.events.length === 0) return;
    const window = this.timeline.getWindow();
    const visibleSpanMs = window.end.getTime() - window.start.getTime();
    const visibleWindow: VisibleWindow = {
      startMs: window.start.getTime(),
      endMs: window.end.getTime(),
    };
    const items = eventsToTimelineItems(
      filtered,
      visibleSpanMs,
      visibleWindow,
      this.displayOptions,
    );
    this.currentItemIds = new Set(items.map((i) => Number(i.id)));
    this.timeline.setItems(items);
    this.scheduleApplySelection();
  }

  private scheduleApplySelection(): void {
    setTimeout(() => this.applySelection(), 0);
  }

  private applySelection(): void {
    if (!this.timeline) return;
    const id = this.highlightedEventId;
    if (id != null && this.currentItemIds.has(id)) {
      this.timeline.setSelection([id]);
    } else {
      this.timeline.setSelection([]);
    }
  }

  toggleSettings(): void {
    this.settingsOpen = !this.settingsOpen;
  }

  onDisplayOptionsChange(options: TimelineDisplayOptions): void {
    this.displayOptions = options;
    this.filterByVisibleMapAreaChange.emit(options.filterByVisibleMapArea);
    this.updateItemsForWindow();
  }

  ngOnDestroy(): void {
    if (this.timeline) {
      this.timeline.off('rangechanged', this.rangeChangedHandler);
      this.timeline.off('itemover', this.itemOverHandler);
      this.timeline.off('itemout', this.itemOutHandler);
      this.timeline.off('click', this.itemClickHandler);
      this.timeline.destroy();
    }
    this.timeline = null;
  }
}
