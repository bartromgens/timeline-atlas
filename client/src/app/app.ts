import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { MapComponent } from './map/map.component';
import { TimelineComponent } from './timeline/timeline.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, TimelineComponent, MapComponent],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly projectName = 'Timeline Atlas';
}
