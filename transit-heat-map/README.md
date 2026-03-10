# Transit Heat Map

A web app that generates a heat map showing TTC (Toronto Transit Commission) travel times. Place a pin anywhere in Toronto and see how long it takes to get there by public transit from every part of the city.

Uses a self-hosted [MOTIS](https://github.com/motis-project/motis) instance (the routing engine behind [Transitous](https://transitous.org/)) with TTC GTFS data for transit routing.

## Features

- Interactive Leaflet map of Toronto
- Click to place a destination pin
- Generates a colour-coded heat map grid showing travel time in minutes
- Configurable grid resolution and departure time
- Parallel route queries for reasonable generation speed

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- ~3 GB disk space for Ontario OSM data + TTC GTFS

## Setup

### 1. Download transit data

```bash
chmod +x setup.sh
./setup.sh
```

This downloads:
- TTC GTFS schedule data from the City of Toronto Open Data portal
- Ontario OSM extract from Geofabrik (needed for street routing / walking segments)

### 2. Import data into MOTIS

```bash
docker compose run --rm motis import
```

This preprocesses the GTFS and OSM data. It may take several minutes.

### 3. Start MOTIS

```bash
docker compose up -d
```

MOTIS will be available at `http://localhost:8080`.

### 4. Start the web app

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` in your browser.

## Usage

1. Click anywhere on the Toronto map to place a destination pin
2. Optionally adjust the grid resolution and departure time
3. Click **Generate Heat Map**
4. Wait for the heat map to render (higher resolutions take longer)

The heat map colours range from green (short travel time) to red (long travel time).

## Architecture

```
Browser  <-->  Flask (port 5000)  <-->  MOTIS (port 8080)
                  |                         |
              Serves UI              TTC GTFS + OSM data
              Fans out route         RAPTOR transit routing
              queries in parallel
```

- **Flask backend**: Generates a grid of origin points across Toronto, queries MOTIS for each origin→destination route in parallel, returns travel times as JSON
- **Leaflet frontend**: Renders the map, handles pin placement, draws coloured rectangles for the heat map
- **MOTIS**: Self-hosted transit routing engine using the RAPTOR algorithm with TTC schedule data

## Configuration

- `motis-config.yml` — MOTIS server settings and timetable config
- `docker-compose.yml` — Docker service definition for MOTIS
- Grid resolution and departure time are adjustable in the UI

## Data Sources

- **TTC GTFS**: [City of Toronto Open Data](https://open.toronto.ca/dataset/ttc-routes-and-schedules/)
- **OSM**: [Geofabrik Ontario extract](https://download.geofabrik.de/north-america/canada/)
