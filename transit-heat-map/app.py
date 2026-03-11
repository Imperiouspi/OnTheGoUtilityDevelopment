import concurrent.futures
import logging
import math
from datetime import datetime, timedelta, timezone

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


@app.route("/api/timetable-dates")
def timetable_dates():
    """Probe MOTIS to discover the valid timetable date range."""
    api = _detect_api_prefix()
    if not api:
        return jsonify({"error": "Cannot reach MOTIS server"}), 502

    valid_date = _find_valid_date(api)
    if valid_date:
        return jsonify({
            "valid_date": valid_date.strftime("%Y-%m-%d"),
            "suggested_time": valid_date.strftime("%Y-%m-%dT08:00"),
        })
    return jsonify({"error": "No valid timetable dates found in MOTIS"}), 404


def _find_valid_date(api_prefix):
    """Probe MOTIS with different dates to find one with active transit service."""
    today = datetime.now(timezone.utc)

    def _has_service(dt):
        """Check if MOTIS has transit service on the given date at 8 AM."""
        test_time = dt.replace(hour=8, minute=0, second=0)
        try:
            resp = requests.get(
                f"{MOTIS_URL}{api_prefix}/plan",
                params={
                    "fromPlace": "43.6532,-79.3832",
                    "toPlace": "43.7000,-79.4000",
                    "time": test_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "arriveBy": "false",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return bool(resp.json().get("itineraries"))
        except requests.RequestException:
            pass
        return False

    # Quick check: today and a few nearby weekdays
    for offset in [0, 1, 2, -1, -2]:
        dt = today + timedelta(days=offset)
        if dt.weekday() < 5 and _has_service(dt):
            log.info(f"Found valid timetable date: {dt.date()}")
            return dt.replace(hour=8, minute=0, second=0)

    # Scan monthly increments backwards (up to 18 months)
    for months_back in range(1, 19):
        dt = today - timedelta(days=months_back * 30)
        # Find next Tuesday from this date
        while dt.weekday() != 1:
            dt += timedelta(days=1)
        if _has_service(dt):
            log.info(f"Found valid timetable date: {dt.date()}")
            return dt.replace(hour=8, minute=0, second=0)

    return None


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
        params = {
            "fromPlace": "43.6532,-79.3832",
            "toPlace": "43.7000,-79.4000",
            "time": _to_motis_time(),
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
            resp = requests.get(
                f"{MOTIS_URL}{prefix}/plan",
                params={
                    "fromPlace": "43.6532,-79.3832",
                    "toPlace": "43.6600,-79.3900",
                    "time": _to_motis_time(),
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


def _to_motis_time(depart_time=None):
    """Convert a departure time string to ISO 8601 with Z suffix for MOTIS."""
    if depart_time:
        try:
            dt = datetime.fromisoformat(depart_time.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _query_single_route(from_lat, from_lng, to_lat, to_lng, depart_time, api_prefix):
    """Query MOTIS for a single origin -> destination route."""
    try:
        resp = requests.get(
            f"{MOTIS_URL}{api_prefix}/plan",
            params={
                "fromPlace": f"{from_lat},{from_lng}",
                "toPlace": f"{to_lat},{to_lng}",
                "time": _to_motis_time(depart_time),
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

        failed = 0
        for future in concurrent.futures.as_completed(future_to_point):
            lat, lng = future_to_point[future]
            minutes = future.result()
            if minutes is not None:
                results.append({"lat": lat, "lng": lng, "minutes": minutes})
            else:
                failed += 1

    log.info(f"Heatmap query complete: {len(results)} succeeded, {failed} failed out of {len(points)} grid points")
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
