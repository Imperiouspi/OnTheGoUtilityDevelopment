const TORONTO_CENTER = [43.7, -79.4];
const TORONTO_BOUNDS = [[43.58, -79.64], [43.86, -79.10]];

const map = L.map("map", {
  center: TORONTO_CENTER,
  zoom: 12,
  maxBounds: [
    [43.4, -79.9],
    [44.0, -78.8],
  ],
});

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 18,
}).addTo(map);

let destinationMarker = null;
let heatmapLayer = null;
let destinationLatLng = null;

const generateBtn = document.getElementById("generate-btn");
const statusEl = document.getElementById("status");
const legendEl = document.getElementById("legend");
const pinInfoEl = document.getElementById("pin-info");
const pinCoordsEl = document.getElementById("pin-coords");
const gridSizeEl = document.getElementById("grid-size");
const departTimeEl = document.getElementById("depart-time");

// Auto-detect valid timetable date from MOTIS, fall back to GTFS start or next weekday 8 AM
(async function setDefaultDepartTime() {
  let errorDetail = "";
  let gtfsInfo = null;
  try {
    const resp = await fetch("/api/timetable-dates");
    const data = await resp.json();
    gtfsInfo = data.gtfs_info;
    if (resp.ok && data.suggested_time) {
      departTimeEl.value = data.suggested_time;
      const range = data.gtfs_info?.service_range || data.valid_date;
      statusEl.className = "success";
      statusEl.textContent = `MOTIS timetable active for ${data.valid_date} (feed covers ${range}). Click the map to set a destination.`;
      statusEl.classList.remove("hidden");
      return;
    }
    errorDetail = data.error || "Unknown error";
  } catch (e) {
    errorDetail = `Could not reach Flask server: ${e.message}`;
  }
  // Fallback: use GTFS start date if available, otherwise next weekday
  let fallback = new Date();
  fallback.setDate(fallback.getDate() + 1);
  const gs = gtfsInfo?.overall_start;
  if (gs && gs.length === 8) {
    const parsed = new Date(`${gs.slice(0,4)}-${gs.slice(4,6)}-${gs.slice(6,8)}T08:00:00`);
    if (!isNaN(parsed) && parsed > new Date()) fallback = parsed;
  }
  while (fallback.getDay() === 0 || fallback.getDay() === 6) {
    fallback.setDate(fallback.getDate() + 1);
  }
  fallback.setHours(8, 0, 0, 0);
  departTimeEl.value = fallback.toISOString().slice(0, 16);
  statusEl.className = "error";
  statusEl.textContent = errorDetail;
  statusEl.classList.remove("hidden");
})();

// Pin icon
const pinIcon = L.divIcon({
  className: "pin-icon",
  html: `<svg width="30" height="40" viewBox="0 0 30 40" xmlns="http://www.w3.org/2000/svg">
    <path d="M15 0C6.7 0 0 6.7 0 15c0 10.5 15 25 15 25s15-14.5 15-25C30 6.7 23.3 0 15 0z" fill="#c41e3a" stroke="#fff" stroke-width="2"/>
    <circle cx="15" cy="15" r="6" fill="#fff"/>
  </svg>`,
  iconSize: [30, 40],
  iconAnchor: [15, 40],
});

map.on("click", function (e) {
  const { lat, lng } = e.latlng;

  if (lat < 43.58 || lat > 43.86 || lng < -79.64 || lng > -79.10) {
    return;
  }

  destinationLatLng = e.latlng;

  if (destinationMarker) {
    destinationMarker.setLatLng(e.latlng);
  } else {
    destinationMarker = L.marker(e.latlng, { icon: pinIcon }).addTo(map);
  }

  pinCoordsEl.textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  pinInfoEl.classList.remove("hidden");
  generateBtn.disabled = false;
});

generateBtn.addEventListener("click", async function () {
  if (!destinationLatLng) return;

  generateBtn.disabled = true;
  statusEl.className = "loading";
  statusEl.textContent = "Querying MOTIS for travel times... this may take a minute.";
  statusEl.classList.remove("hidden");
  legendEl.classList.add("hidden");

  if (heatmapLayer) {
    map.removeLayer(heatmapLayer);
    heatmapLayer = null;
  }

  const gridSize = parseInt(gridSizeEl.value);
  const departTime = departTimeEl.value
    ? new Date(departTimeEl.value).toISOString()
    : null;

  try {
    const resp = await fetch("/api/heatmap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: destinationLatLng.lat,
        lng: destinationLatLng.lng,
        gridSize: gridSize,
        time: departTime,
      }),
    });

    if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

    const points = await resp.json();

    if (points.length === 0 || points.length <= 2) {
      statusEl.className = "error";
      statusEl.textContent =
        "No transit routes found. The GTFS feed likely doesn't cover the selected date/time. " +
        "Try re-running setup.sh to download fresh TTC data, then re-import MOTIS.";
      generateBtn.disabled = false;
      return;
    }

    renderHeatmap(points);

    statusEl.className = "success";
    statusEl.textContent = `Heat map generated with ${points.length} data points.`;
    legendEl.classList.remove("hidden");
  } catch (err) {
    statusEl.className = "error";
    statusEl.textContent = `Error: ${err.message}`;
  }

  generateBtn.disabled = false;
});

function minutesToColor(minutes) {
  // 0 min = bright green, 90+ min = dark red
  const t = Math.min(minutes / 90, 1);

  let r, g, b;
  if (t < 0.25) {
    // green -> yellow-green
    r = Math.round(t * 4 * 170);
    g = 255;
    b = 0;
  } else if (t < 0.5) {
    // yellow-green -> yellow
    r = 170 + Math.round((t - 0.25) * 4 * 85);
    g = 255;
    b = 0;
  } else if (t < 0.75) {
    // yellow -> orange-red
    r = 255;
    g = 255 - Math.round((t - 0.5) * 4 * 170);
    b = 0;
  } else {
    // orange-red -> dark red
    r = 255 - Math.round((t - 0.75) * 4 * 119);
    g = 85 - Math.round((t - 0.75) * 4 * 85);
    b = 0;
  }

  return `rgb(${r}, ${g}, ${b})`;
}

function renderHeatmap(points) {
  if (heatmapLayer) {
    map.removeLayer(heatmapLayer);
  }

  // Calculate cell size from the grid
  const lats = [...new Set(points.map((p) => p.lat))].sort((a, b) => a - b);
  const lngs = [...new Set(points.map((p) => p.lng))].sort((a, b) => a - b);

  const latStep = lats.length > 1 ? lats[1] - lats[0] : 0.01;
  const lngStep = lngs.length > 1 ? lngs[1] - lngs[0] : 0.01;

  const rectangles = [];
  for (const point of points) {
    const color = minutesToColor(point.minutes);
    const bounds = [
      [point.lat - latStep / 2, point.lng - lngStep / 2],
      [point.lat + latStep / 2, point.lng + lngStep / 2],
    ];

    const rect = L.rectangle(bounds, {
      color: "none",
      fillColor: color,
      fillOpacity: 0.5,
      weight: 0,
    });

    rect.bindTooltip(`${Math.round(point.minutes)} min`, {
      sticky: true,
    });

    rectangles.push(rect);
  }

  heatmapLayer = L.layerGroup(rectangles).addTo(map);
}
