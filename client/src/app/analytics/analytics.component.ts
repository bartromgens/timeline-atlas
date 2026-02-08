import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import type { EventApi } from '../event/event';
import { EventsService } from '../event/events.service';

export interface HistogramBucket {
  label: string;
  min: number;
  max: number;
  count: number;
}

export interface DistributionChart {
  title: string;
  buckets: HistogramBucket[];
  maxCount: number;
  total: number;
}

function computeLinearBuckets(
  values: number[],
  numBuckets: number,
  formatter: (min: number, max: number) => string,
): HistogramBucket[] {
  const filtered = values.filter((v) => Number.isFinite(v));
  if (filtered.length === 0) {
    return [];
  }
  const lo = Math.min(...filtered);
  const hi = Math.max(...filtered);
  const step = hi > lo ? (hi - lo) / numBuckets : 1;
  const buckets: HistogramBucket[] = [];
  for (let i = 0; i < numBuckets; i++) {
    const min = lo + i * step;
    const max = i === numBuckets - 1 ? hi + 0.001 : lo + (i + 1) * step;
    const count = filtered.filter((v) => v >= min && (i === numBuckets - 1 ? v <= max : v < max)).length;
    buckets.push({ label: formatter(min, max), min, max, count });
  }
  return buckets;
}

function computeLogBuckets(
  values: number[],
  numBuckets: number,
  formatter: (min: number, max: number) => string,
): HistogramBucket[] {
  const filtered = values.filter((v) => Number.isFinite(v) && v > 0);
  if (filtered.length === 0) {
    return values.filter((v) => v === 0).length
      ? [{ label: '0', min: 0, max: 0, count: values.filter((v) => v === 0).length }]
      : [];
  }
  const minVal = Math.min(...filtered);
  const maxVal = Math.max(...filtered);
  const logMin = Math.log10(Math.max(minVal, 0.1));
  const logMax = Math.log10(Math.max(maxVal, 0.1));
  const step = (logMax - logMin) / numBuckets;
  const buckets: HistogramBucket[] = [];
  for (let i = 0; i < numBuckets; i++) {
    const bMin = Math.pow(10, logMin + i * step);
    const bMax = i === numBuckets - 1 ? maxVal + 1 : Math.pow(10, logMin + (i + 1) * step);
    const count = filtered.filter((v) => v >= bMin && v < bMax).length;
    buckets.push({ label: formatter(bMin, bMax), min: bMin, max: bMax, count });
  }
  const zeros = values.filter((v) => v === 0).length;
  if (zeros > 0) {
    buckets.unshift({ label: '0', min: 0, max: 0, count: zeros });
  }
  return buckets;
}

function formatRange(min: number, max: number): string {
  if (min === max) return String(min);
  if (max >= 1e6) return `${(min / 1e6).toFixed(1)}M–${(max / 1e6).toFixed(1)}M`;
  if (max >= 1e3) return `${(min / 1e3).toFixed(0)}k–${(max / 1e3).toFixed(0)}k`;
  return `${Math.round(min)}–${Math.round(max)}`;
}

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsComponent implements OnInit {
  events = signal<EventApi[]>([]);
  loading = signal(true);
  error = signal(false);

  importanceChart = computed<DistributionChart | null>(() => {
    const ev = this.events();
    if (ev.length === 0) return null;
    const values = ev.map((e) => e.importance_score).filter((v): v is number => v != null);
    const buckets = computeLinearBuckets(values, 12, (a, b) => `${a.toFixed(1)}–${b.toFixed(1)}`);
    const counts = buckets.map((b) => b.count);
    return {
      title: 'Importance score',
      buckets,
      maxCount: Math.max(0, ...counts),
      total: values.length,
    };
  });

  pageviewsChart = computed<DistributionChart | null>(() => {
    const ev = this.events();
    if (ev.length === 0) return null;
    const values = ev.map((e) => e.pageviews_30d);
    const buckets = computeLogBuckets(values, 10, formatRange);
    const counts = buckets.map((b) => b.count);
    return {
      title: 'Pageviews (30d)',
      buckets,
      maxCount: Math.max(0, ...counts),
      total: values.length,
    };
  });

  sitelinksChart = computed<DistributionChart | null>(() => {
    const ev = this.events();
    if (ev.length === 0) return null;
    const values = ev.map((e) => e.sitelink_count);
    const buckets = computeLogBuckets(values, 10, formatRange);
    const counts = buckets.map((b) => b.count);
    return {
      title: 'Sitelinks',
      buckets,
      maxCount: Math.max(0, ...counts),
      total: values.length,
    };
  });

  backlinksChart = computed<DistributionChart | null>(() => {
    const ev = this.events();
    if (ev.length === 0) return null;
    const values = ev.map((e) => e.backlink_count);
    const buckets = computeLogBuckets(values, 10, formatRange);
    const counts = buckets.map((b) => b.count);
    return {
      title: 'Backlinks',
      buckets,
      maxCount: Math.max(0, ...counts),
      total: values.length,
    };
  });

  constructor(
    private eventsService: EventsService,
    private destroyRef: DestroyRef,
  ) {}

  ngOnInit(): void {
    this.eventsService
      .getEvents(null)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (events) => {
          this.events.set(events);
          this.loading.set(false);
          this.error.set(false);
        },
        error: () => {
          this.loading.set(false);
          this.error.set(true);
        },
      });
  }
}
