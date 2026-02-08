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
import * as L from 'leaflet';
import { colorForCategory } from '../models/category-colors';
import type { EventApi } from '../event/event';

const MIN_RADIUS_PX = 2.5;
const MAX_RADIUS_PX = 22;
const IMPORTANCE_RADIUS_EXPONENT = 4;
const FIT_PADDING_PX = 40;
const FIT_MIN_ZOOM = 4;
const FIT_MAX_ZOOM = 7;
const HIGHLIGHT_WEIGHT = 3;
const HIGHLIGHT_FILL_OPACITY = 0.55;
const HIGHLIGHT_COLOR = '#ff9800';
const HIGHLIGHT_RADIUS_FACTOR = 1;

function radiusFromImportance(importance: number | null, dataMin: number, dataMax: number): number {
  const score = importance ?? dataMin;
  const range = dataMax - dataMin;
  const normalized = range <= 0 ? 1 : Math.max(0, Math.min(1, (score - dataMin) / range));
  const curved = Math.pow(normalized, IMPORTANCE_RADIUS_EXPONENT);
  return MIN_RADIUS_PX + curved * (MAX_RADIUS_PX - MIN_RADIUS_PX);
}

function centerOfMass(
  events: Array<{
    location_lat: number | null;
    location_lon: number | null;
    importance_score: number | null;
  }>,
): L.LatLngTuple | null {
  const withCoords = events.filter(
    (e) =>
      e.location_lat != null &&
      e.location_lon != null &&
      Number.isFinite(e.location_lat) &&
      Number.isFinite(e.location_lon),
  );
  if (withCoords.length === 0) return null;
  let sumLat = 0;
  let sumLon = 0;
  let totalMass = 0;
  for (const e of withCoords) {
    const lat = e.location_lat as number;
    const lon = e.location_lon as number;
    const m =
      e.importance_score != null && Number.isFinite(e.importance_score) ? e.importance_score : 0;
    sumLat += lat * m;
    sumLon += lon * m;
    totalMass += m;
  }
  if (totalMass <= 0) {
    sumLat = withCoords.reduce((s, e) => s + (e.location_lat as number), 0);
    sumLon = withCoords.reduce((s, e) => s + (e.location_lon as number), 0);
    return [sumLat / withCoords.length, sumLon / withCoords.length];
  }
  return [sumLat / totalMass, sumLon / totalMass];
}

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css',
})
export class MapComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('mapContainer') mapContainer!: ElementRef<HTMLElement>;
  @Input() events: EventApi[] = [];
  @Input() highlightedEventId: number | null = null;
  @Input() selectedEventId: number | null = null;
  @Output() markerSelect = new EventEmitter<number>();

  private map: L.Map | null = null;
  private circlesLayer: L.LayerGroup | null = null;
  private circleDataByEventId = new Map<
    number,
    { circle: L.CircleMarker; baseRadius: number; color: string }
  >();

  ngAfterViewInit(): void {
    const container = this.mapContainer?.nativeElement;
    if (!container) return;

    this.map = L.map(container).setView([20, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(this.map);

    this.circlesLayer = L.layerGroup().addTo(this.map);
    this.drawEvents(this.events);
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['events'] && this.circlesLayer) {
      this.drawEvents(this.events);
    }
    if (changes['highlightedEventId']) {
      this.applyHighlight();
    }
    if (changes['selectedEventId'] && this.selectedEventId != null && this.map) {
      this.centerOnEvent(this.selectedEventId);
    }
  }

  private centerOnEvent(eventId: number): void {
    const event = this.events.find((e) => e.id === eventId);
    if (
      !event ||
      event.location_lat == null ||
      event.location_lon == null ||
      !Number.isFinite(event.location_lat) ||
      !Number.isFinite(event.location_lon)
    ) {
      return;
    }
    this.map!.panTo([event.location_lat, event.location_lon]);
  }

  private applyHighlight(): void {
    const highlightedId = this.highlightedEventId;
    for (const [eventId, { circle, baseRadius, color }] of this.circleDataByEventId) {
      const highlighted = eventId === highlightedId;
      circle.setStyle({
        radius: highlighted ? baseRadius * HIGHLIGHT_RADIUS_FACTOR : baseRadius,
        weight: highlighted ? HIGHLIGHT_WEIGHT : 1.5,
        fillOpacity: highlighted ? HIGHLIGHT_FILL_OPACITY : 0.25,
        color: highlighted ? HIGHLIGHT_COLOR : color,
        fillColor: highlighted ? HIGHLIGHT_COLOR : color,
      });
    }
  }

  private drawEvents(events: EventApi[]): void {
    if (!this.circlesLayer) return;
    this.circlesLayer.clearLayers();
    this.circleDataByEventId.clear();

    const withLocation = events
      .filter(
        (e) =>
          e.location_lat != null &&
          e.location_lon != null &&
          Number.isFinite(e.location_lat) &&
          Number.isFinite(e.location_lon),
      )
      .sort((a, b) => (a.importance_score ?? -Infinity) - (b.importance_score ?? -Infinity));

    const importanceValues = withLocation
      .map((e) => e.importance_score)
      .filter((s): s is number => s != null && Number.isFinite(s));
    const dataMin = importanceValues.length > 0 ? Math.min(...importanceValues) : 0;
    const dataMax = importanceValues.length > 0 ? Math.max(...importanceValues) : 1;

    for (const event of withLocation) {
      const lat = event.location_lat as number;
      const lon = event.location_lon as number;
      const radius = radiusFromImportance(event.importance_score, dataMin, dataMax);

      const color = colorForCategory(event.category_id);
      const circle = L.circleMarker([lat, lon], {
        radius,
        color,
        fillColor: color,
        fillOpacity: 0.25,
        weight: 1.5,
      });
      circle.bindTooltip(event.title, {
        permanent: false,
        direction: 'top',
      });
      circle.on('click', () => this.markerSelect.emit(event.id));
      this.circleDataByEventId.set(event.id, { circle, baseRadius: radius, color });
      this.circlesLayer!.addLayer(circle);
    }
    this.applyHighlight();

    if (withLocation.length > 0 && this.map) {
      const latLngs = withLocation.map(
        (e) => [e.location_lat as number, e.location_lon as number] as L.LatLngTuple,
      );
      let bounds = L.latLngBounds(latLngs);
      if (withLocation.length === 1) {
        const pad = 0.01;
        bounds = L.latLngBounds(
          [latLngs[0][0] - pad, latLngs[0][1] - pad],
          [latLngs[0][0] + pad, latLngs[0][1] + pad],
        );
      }
      if (bounds.isValid()) {
        this.map.fitBounds(bounds, {
          padding: [FIT_PADDING_PX, FIT_PADDING_PX],
          maxZoom: FIT_MAX_ZOOM,
        });
        let zoom = this.map.getZoom();
        if (zoom < FIT_MIN_ZOOM) {
          this.map.setZoom(FIT_MIN_ZOOM);
          zoom = FIT_MIN_ZOOM;
        }
        const center = centerOfMass(withLocation);
        if (center) {
          this.map.setView(center, zoom);
        }
      }
    }
  }

  ngOnDestroy(): void {
    this.map?.remove();
    this.map = null;
    this.circlesLayer = null;
  }
}
