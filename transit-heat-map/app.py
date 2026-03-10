import concurrent.futures
import math
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

MOTIS_URL = "http://localhost:8080"

# Toronto bounding box
TORONTO_BOUNDS = {
    "south": 43.58,
    "north": 43.86,
    "west": -79.64,
    "east": -79.10,
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/heatmap", methods=["POST"])
def heatmap():
    data = request.get_json()
    dest_lat = data["lat"]
    dest_lng = data["lng"]
    grid_size = data.get("gridSize", 30)
    time_str = data.get("time")

    if time_str:
        depart_time = time_str
    else:
        depart_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    points = _generate_grid(grid_size)

    results = _query_travel_times(points, dest_lat, dest_lng, depart_time)

    return jsonify(results)


def _generate_grid(grid_size):
    """Generate a grid of points across Toronto."""
    bounds = TORONTO_BOUNDS
    lat_step = (bounds["north"] - bounds["south"]) / grid_size
    lng_step = (bounds["east"] - bounds["west"]) / grid_size

    points = []
    for i in range(grid_size + 1):
        for j in range(grid_size + 1):
            lat = bounds["south"] + i * lat_step
            lng = bounds["west"] + j * lng_step
            points.append((lat, lng))
    return points


def _query_single_route(from_lat, from_lng, to_lat, to_lng, depart_time):
    """Query MOTIS for a single origin -> destination route."""
    try:
        resp = requests.get(
            f"{MOTIS_URL}/api/v1/plan",
            params={
                "fromPlace": f"{from_lat},{from_lng}",
                "toPlace": f"{to_lat},{to_lng}",
                "time": depart_time,
                "arriveBy": "false",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        itineraries = data.get("itineraries", [])
        if not itineraries:
            return None

        # Return the shortest travel time in minutes
        best = min(itineraries, key=lambda it: it.get("duration", math.inf))
        duration_seconds = best.get("duration", 0)
        return duration_seconds / 60.0

    except (requests.RequestException, KeyError, ValueError):
        return None


def _query_travel_times(points, dest_lat, dest_lng, depart_time):
    """Query travel times from all grid points to the destination in parallel."""
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        future_to_point = {}
        for lat, lng in points:
            dist = _haversine(lat, lng, dest_lat, dest_lng)
            if dist < 0.3:
                results.append({"lat": lat, "lng": lng, "minutes": 0})
                continue

            future = executor.submit(
                _query_single_route, lat, lng, dest_lat, dest_lng, depart_time
            )
            future_to_point[future] = (lat, lng)

        for future in concurrent.futures.as_completed(future_to_point):
            lat, lng = future_to_point[future]
            minutes = future.result()
            if minutes is not None:
                results.append({"lat": lat, "lng": lng, "minutes": minutes})

    return results


def _haversine(lat1, lng1, lat2, lng2):
    """Calculate distance in km between two points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
