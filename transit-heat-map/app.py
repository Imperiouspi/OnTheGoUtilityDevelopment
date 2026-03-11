import concurrent.futures
import logging
import math
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

MOTIS_URL = "http://localhost:8080"
_api_prefix = None

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

    api = _detect_api_prefix()
    if not api:
        return jsonify({"error": "Cannot reach MOTIS server"}), 502

    points = _generate_grid(grid_size)

    results = _query_travel_times(points, dest_lat, dest_lng, depart_time, api)

    return jsonify(results)


@app.route("/api/debug")
def debug():
    """Probe MOTIS to help diagnose connectivity issues."""
    info = {"motis_url": MOTIS_URL, "api_prefix": _api_prefix}
    try:
        resp = requests.get(MOTIS_URL, timeout=5)
        info["root_status"] = resp.status_code
    except requests.RequestException as e:
        info["root_error"] = str(e)

    api = _detect_api_prefix()
    info["detected_api"] = api

    if api:
        # Try a single test query near downtown Toronto
        test_url = f"{MOTIS_URL}{api}/plan"
        now = datetime.now(timezone.utc)
        params = {
            "fromPlace": "43.6532,-79.3832",
            "toPlace": "43.7000,-79.4000",
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "arriveBy": "false",
        }
        try:
            resp = requests.get(test_url, params=params, timeout=15)
            info["test_query_status"] = resp.status_code
            info["test_query_response"] = resp.json()
        except requests.RequestException as e:
            info["test_query_error"] = str(e)

    return jsonify(info)


def _detect_api_prefix():
    """Auto-detect which MOTIS API version is available."""
    global _api_prefix
    if _api_prefix is not None:
        return _api_prefix

    candidates = ["/api/v1", "/api/v2", "/api/v3", "/api/v4", "/api/v5", "/api"]
    for prefix in candidates:
        try:
            now = datetime.now(timezone.utc)
            resp = requests.get(
                f"{MOTIS_URL}{prefix}/plan",
                params={
                    "fromPlace": "43.6532,-79.3832",
                    "toPlace": "43.6600,-79.3900",
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M"),
                },
                timeout=10,
            )
            if resp.status_code != 404:
                _api_prefix = prefix
                log.info(f"Detected MOTIS API prefix: {prefix} (status {resp.status_code})")
                return _api_prefix
        except requests.RequestException:
            continue

    log.warning("Could not detect MOTIS API version")
    return None


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


def _parse_depart_time(depart_time):
    """Split a departure time string into separate date and time params for MOTIS."""
    try:
        dt = datetime.fromisoformat(depart_time.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def _query_single_route(from_lat, from_lng, to_lat, to_lng, depart_time, api_prefix):
    """Query MOTIS for a single origin -> destination route."""
    try:
        date_str, time_str = _parse_depart_time(depart_time)
        resp = requests.get(
            f"{MOTIS_URL}{api_prefix}/plan",
            params={
                "fromPlace": f"{from_lat},{from_lng}",
                "toPlace": f"{to_lat},{to_lng}",
                "date": date_str,
                "time": time_str,
                "arriveBy": "false",
            },
            timeout=15,
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


def _query_travel_times(points, dest_lat, dest_lng, depart_time, api_prefix):
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
                _query_single_route, lat, lng, dest_lat, dest_lng, depart_time, api_prefix
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
