import {
  AfterViewInit,
  Component,
  DestroyRef,
  ElementRef,
  OnDestroy,
  ViewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import * as L from 'leaflet';
import { EventsService } from '../services/events.service';
import type { EventApi } from '../models/event';

const MIN_RADIUS_PX = 4;
const MAX_RADIUS_PX = 24;

function radiusFromImportance(
  importance: number | null,
  dataMin: number,
  dataMax: number,
): number {
  const score = importance ?? dataMin;
  const range = dataMax - dataMin;
  const normalized =
    range <= 0 ? 1 : Math.max(0, Math.min(1, (score - dataMin) / range));
  return MIN_RADIUS_PX + normalized * (MAX_RADIUS_PX - MIN_RADIUS_PX);
}

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css',
})
export class MapComponent implements AfterViewInit, OnDestroy {
  @ViewChild('mapContainer') mapContainer!: ElementRef<HTMLElement>;

  private map: L.Map | null = null;
  private circlesLayer: L.LayerGroup | null = null;

  constructor(
    private eventsService: EventsService,
    private destroyRef: DestroyRef,
  ) {}

  ngAfterViewInit(): void {
    const container = this.mapContainer?.nativeElement;
    if (!container) return;

    this.map = L.map(container).setView([20, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(this.map);

    this.circlesLayer = L.layerGroup().addTo(this.map);

    this.eventsService
      .getEvents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (events) => this.drawEvents(events),
        error: () => {},
      });
  }

  private drawEvents(events: EventApi[]): void {
    if (!this.circlesLayer) return;
    this.circlesLayer.clearLayers();

    const withLocation = events.filter(
      (e) =>
        e.location_lat != null &&
        e.location_lon != null &&
        Number.isFinite(e.location_lat) &&
        Number.isFinite(e.location_lon),
    );

    const importanceValues = withLocation
      .map((e) => e.importance_score)
      .filter((s): s is number => s != null && Number.isFinite(s));
    const dataMin =
      importanceValues.length > 0 ? Math.min(...importanceValues) : 0;
    const dataMax =
      importanceValues.length > 0 ? Math.max(...importanceValues) : 1;

    for (const event of withLocation) {
      const lat = event.location_lat as number;
      const lon = event.location_lon as number;
      const radius = radiusFromImportance(
        event.importance_score,
        dataMin,
        dataMax,
      );

      const circle = L.circleMarker([lat, lon], {
        radius,
        color: '#1976d2',
        fillColor: '#1976d2',
        fillOpacity: 0.25,
        weight: 1.5,
      });
      circle.bindTooltip(event.title, {
        permanent: false,
        direction: 'top',
      });
      this.circlesLayer!.addLayer(circle);
    }
  }

  ngOnDestroy(): void {
    this.map?.remove();
    this.map = null;
    this.circlesLayer = null;
  }
}
