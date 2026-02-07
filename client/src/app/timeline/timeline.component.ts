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
import type { EventApi } from '../models/event';
import { eventsToTimelineItems } from './event-to-timeline-item';

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

  private timeline: Timeline | null = null;
  private rangeChangedHandler = (): void => this.updateItemsForWindow();

  ngAfterViewInit(): void {
    const container = this.timelineContainer?.nativeElement;
    if (!container) return;

    this.timeline = new Timeline(container, [], {
      editable: false,
      zoomKey: 'ctrlKey',
    });
    this.timeline.on('rangechanged', this.rangeChangedHandler);
    this.applyEvents();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['events']) {
      this.applyEvents();
    }
  }

  private applyEvents(): void {
    if (!this.timeline) return;
    if (this.events.length === 0) {
      this.timeline.setItems([]);
      return;
    }
    this.timeline.setItems(eventsToTimelineItems(this.events));
    this.timeline.fit();
  }

  private updateItemsForWindow(): void {
    if (!this.timeline || this.events.length === 0) return;
    const window = this.timeline.getWindow();
    const visibleSpanMs = window.end.getTime() - window.start.getTime();
    this.timeline.setItems(eventsToTimelineItems(this.events, visibleSpanMs));
  }

  ngOnDestroy(): void {
    if (this.timeline) {
      this.timeline.off('rangechanged', this.rangeChangedHandler);
      this.timeline.destroy();
    }
    this.timeline = null;
  }
}
