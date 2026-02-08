import { DecimalPipe } from '@angular/common';
import { Component, Input } from '@angular/core';
import type { EventApi } from '../event/event';
import { parseEventTime } from '../event/event';

@Component({
  selector: 'app-event-details',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './event-details.component.html',
  styleUrl: './event-details.component.css',
})
export class EventDetailsComponent {
  @Input() event: EventApi | null = null;
  @Input() isLoggedIn = false;

  formatTime(time: { value: string } | null): string {
    const date = parseEventTime(time);
    if (!date) return '';
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }

  get dateLabel(): string {
    const e = this.event;
    if (!e) return '';
    if (e.start_time?.value && e.end_time?.value) {
      return `${this.formatTime(e.start_time)} – ${this.formatTime(e.end_time)}`;
    }
    if (e.point_in_time?.value) return this.formatTime(e.point_in_time);
    if (e.start_time?.value) return this.formatTime(e.start_time);
    if (e.end_time?.value) return this.formatTime(e.end_time);
    return '';
  }
}
