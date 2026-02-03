# timeline-atlas

An interactive visualization tool that combines geographic and temporal data from Wikipedia to explore historical events through a zoomable timeline and interactive map interface.

## 🎯 Project Goal

Create an intuitive, Google Maps-style interface for exploring historical events where:
- **Timeline zoom reveals detail**: Major events visible when zoomed out, minor events appear when zoomed in
- **Geographic filtering**: Events displayed on an interactive map can be filtered by visible region
- **Bidirectional interaction**: Map and timeline are synchronized - filtering one updates the other
- **Rich context**: Each event links to Wikipedia articles with descriptions, images, and related information

The system is designed to work with any historical period or topic from Wikipedia/Wikidata. Initial implementation will focus on World War II (1939-1945) as a proof of concept.

## ✨ Core Features

### 1. Zoomable Timeline
- Smooth zoom controls similar to Google Maps
- Dynamic detail levels: event visibility adapts to zoom level
- Configurable time ranges based on selected historical period
- Support for both point events (e.g., battles) and duration events (e.g., campaigns)

### 2. Interactive Geographic Map
- Display events on a world map with precise coordinates
- Pan and zoom map controls
- Event clustering for dense areas
- Visual markers for events

### 3. Synchronized Filtering
- Filter timeline by visible map region
- Filter map by visible timeline range
- Combine filters: view events in specific regions during specific time periods

### 4. Event Details
- Click any event to view details popup
- Wikipedia article summary and link
- Related images from Wikimedia Commons
- Date precision (day/month/year)
- Geographic context
- Related events (part of larger campaigns, etc.)

## 🛠 Core Technologies

### Backend
- **Python 3.12+**: Core language
- **Django 5.0+**: Web framework
- **Django REST Framework**: RESTful API

### Frontend
- **Angular 18+**: Frontend framework
- **Leaflet**: Interactive maps
- **Angular Material**: UI components

### Data Sources
- **Wikidata**: Structured event data via SPARQL queries
- **Wikipedia API**: Article content, summaries, and images
- **Wikimedia Commons**: Historical photographs and maps

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL with PostGIS extension

### Backend Setup
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Frontend Setup
```bash
cd client
npm install
ng serve
```

### Import Initial Data
```bash
# Import events from Wikidata for a specific topic/period
python manage.py import_events --topic "World War II" --start-year 1939 --end-year 1945
```

## 📡 API Endpoints

### Events
- `GET /api/events/` - List events with filters
  - Query params: `start_date`, `end_date`, `min_lat`, `max_lat`, `min_lng`, `max_lng`, `zoom_level`
- `GET /api/events/{id}/` - Event detail
- `GET /api/events/date-range/` - Get min/max dates in dataset

## 🔄 Data Import Process

1. **SPARQL Query**: Fetch events from Wikidata based on topic/time period
2. **Data Enrichment**: Get Wikipedia article content and images
3. **Geocoding**: Ensure all events have valid coordinates
4. **Importance Scoring**: Calculate importance levels based on page views and links
5. **Database Storage**: Save to a database

## 🛣 Roadmap

### Phase 1: MVP (Current)
- [x] Project setup and architecture
- [ ] Basic timeline with zoom
- [ ] Basic map with markers
- [ ] Event data model and API
- [ ] Wikidata import script
- [ ] Synchronized filtering
- [ ] Initial dataset: World War II (1939-1945)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Note**: This project is for educational purposes. All historical data is sourced from Wikipedia/Wikidata and subject to their respective licenses (CC BY-SA, CC0).
