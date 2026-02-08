import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { TimelineDisplayOptions } from './event-to-timeline-item';
import {
  DEFAULT_FILTER_BY_VISIBLE_MAP_AREA,
  DEFAULT_MAX_EVENT_SPAN_VISIBLE_RATIO,
  DEFAULT_MAX_OVERLAPPING_EVENTS,
  DEFAULT_MIN_VISIBLE_EVENTS,
  DEFAULT_SHORT_EVENT_FRACTION,
} from './event-to-timeline-item';

@Component({
  selector: 'app-timeline-settings',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './timeline-settings.component.html',
  styleUrl: './timeline-settings.component.css',
})
export class TimelineSettingsComponent {
  @Input() options: TimelineDisplayOptions = {
    minVisibleEvents: DEFAULT_MIN_VISIBLE_EVENTS,
    maxOverlappingEvents: DEFAULT_MAX_OVERLAPPING_EVENTS,
    shortEventFraction: DEFAULT_SHORT_EVENT_FRACTION,
    maxEventSpanVisibleRatio: DEFAULT_MAX_EVENT_SPAN_VISIBLE_RATIO,
    filterByVisibleMapArea: DEFAULT_FILTER_BY_VISIBLE_MAP_AREA,
  };
  @Output() optionsChange = new EventEmitter<TimelineDisplayOptions>();

  readonly minVisibleEventsMin = 10;
  readonly minVisibleEventsMax = 100;
  readonly maxOverlappingMin = 5;
  readonly maxOverlappingMax = 40;
  readonly maxEventSpanVisibleRatioMin = 1;
  readonly maxEventSpanVisibleRatioMax = 10;

  get shortEventFractionPercent(): number {
    return Math.round(this.options.shortEventFraction * 100);
  }

  onShortEventFractionPercentChange(percent: number): void {
    this.emit({
      ...this.options,
      shortEventFraction: percent / 100,
    });
  }

  onMinVisibleEventsChange(value: number): void {
    this.emit({ ...this.options, minVisibleEvents: value });
  }

  onMaxOverlappingChange(value: number): void {
    this.emit({ ...this.options, maxOverlappingEvents: value });
  }

  onMaxEventSpanVisibleRatioChange(value: number): void {
    this.emit({ ...this.options, maxEventSpanVisibleRatio: value });
  }

  onFilterByVisibleMapAreaChange(value: boolean): void {
    this.emit({ ...this.options, filterByVisibleMapArea: value });
  }

  private emit(next: TimelineDisplayOptions): void {
    this.options = next;
    this.optionsChange.emit(next);
  }
}
