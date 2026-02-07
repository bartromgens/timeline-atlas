import {
  AfterViewInit,
  Component,
  DestroyRef,
  ElementRef,
  OnDestroy,
  ViewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Timeline } from 'vis-timeline';
import type { TimelineItem } from 'vis-timeline';
import { EventsService } from '../services/events.service';
import { eventsToTimelineItems } from './event-to-timeline-item';

@Component({
  selector: 'app-timeline',
  standalone: true,
  imports: [],
  templateUrl: './timeline.component.html',
  styleUrl: './timeline.component.css',
})
export class TimelineComponent implements AfterViewInit, OnDestroy {
  @ViewChild('timelineContainer') timelineContainer!: ElementRef<HTMLElement>;

  private timeline: Timeline | null = null;

  constructor(
    private eventsService: EventsService,
    private destroyRef: DestroyRef,
  ) {}

  ngAfterViewInit(): void {
    const container = this.timelineContainer?.nativeElement;
    if (!container) return;

    this.timeline = new Timeline(container, [], {
      editable: false,
      zoomKey: 'ctrlKey',
    });

    this.eventsService
      .getEvents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (events) => {
          const timelineItems = eventsToTimelineItems(events);
          this.timeline?.setItems(timelineItems);
          this.timeline?.fit();
        },
        error: () => {
          this.timeline?.setItems([
            {
              id: 0,
              content: 'Failed to load events',
              start: new Date().toISOString(),
              type: 'point',
            },
          ]);
        },
      });
  }

  ngOnDestroy(): void {
    this.timeline?.destroy();
    this.timeline = null;
  }
}
