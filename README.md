# FiestaBoard Smart Commute & Traffic Plugin 🚗⏱️

[![FiestaBoard](https://img.shields.io/badge/FiestaBoard-Plugin-blue.svg)](https://fiestaboard.app)
[![Python](https://img.shields.io/badge/Python-3.9+-brightgreen.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-26%20passed-success.svg)](tests/)

Real-time traffic and smart commute route comparison for your **Vestaboard** and split-flap displays using [FiestaBoard](https://fiestaboard.app).

---

## 💡 Why This Plugin?

The default FiestaBoard traffic plugin only accepts a single origin and destination address. Because standard routing engines automatically pick the default fastest route, choosing the same start and destination twice yields two identical times.

**Smart Commute** allows you to pick the **exact same start and destination**, but compare **two distinct routes** (e.g., *Autobahn A1* vs. *Landstraße B3*) side-by-side with live traffic delays, delta savings, and visual status badges!

---

## 🔌 Supported Data Providers

| Provider | Cost & Limits | Credit Card Required? | Best For |
|---|---|---|---|
| **TomTom (Default)** | **100% Free** (2,500 calls/day = 75,000/mo) | ❌ **No credit card needed** | **Recommended!** Zero cost, no billing risk, industry-leading live traffic |
| **Google Routes API** | Pay-as-you-go ($5-$10/1k requests) | ⚠️ **Yes (Google Cloud Billing)** | Users with existing GCP projects |
| **Demo Mode** | Free simulation | ❌ No | Instant visual testing without an API key |

---

## ✨ Features

- 🛣️ **Dual-Route Comparison**: Compare Route 1 and Route 2 between the same (or different) origin and destination.
- 🎯 **3 Route Differentiation Modes**:
  1. **Waypoints / Via-Points (`via`)**: Pass intermediate corridors (e.g. `"A1"`, `"Kreuz Leverkusen"`, or city names). Non-stop via points ensure the route follows your desired corridor without adding stopover delays.
  2. **Avoidances (`avoid_highways`, `avoid_tolls`)**: Easily compare a highway route with a scenic/local country road.
  3. **Alternative Routes Index (`alternative_index`)**: Automatically pick the primary route (index 0) vs. secondary alternate route (index 1).
- 🎨 **Visual Traffic Color Badges**: Instant glance at traffic conditions using Vestaboard color tiles:
  - `{66}` **Green**: Clear flow (delay < 5 mins)
  - `{65}` **Yellow**: Moderate traffic (5–14 mins delay)
  - `{63}` **Red**: Heavy congestion (delay ≥ 15 mins)
- ⏱️ **Delta & Recommendations**: Automatically computes which route is faster, how many minutes you save, and displays a clean recommendation string (e.g., `TAKE B3 (-6M)`).
- 🔔 **Event Triggers**:
  - **Heavy Traffic Alert**: Triggers when a route exceeds the configurable heavy traffic threshold (default: 15 mins delay).
  - **Faster Alternative Alert**: Triggers when the alternative route is at least 5 minutes faster than the primary route.
- 🧪 **Instant Demo Mode**: Preview and test board layouts immediately without any credentials.
- 🌍 **Metric & Imperial**: Full support for both `metric` (km) and `imperial` (miles).

---

## 📐 Board Layout Examples

### Vestaboard Flagship (22 × 6)

```text
COMMUTE: HOME TO WORK
A1 AUTOBAHN:  34M {63}
B3 LANDSTR:   28M {66}
REC: TAKE B3 (-6 MIN)
A1 DELAY: +12 MIN
UPDATED: 07:45
```

### Vestaboard Note (15 × 3)

```text
A1: 34M {63} +12M
B3: 28M {66} FAST
TAKE B3 (-6M)
```

---

## ⚙️ Configuration Guide

In the FiestaBoard Web UI under **Integrations > Smart Commute**, configure your commute parameters:

### 1. General & Provider Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `enabled` | boolean | `true` | Enable or disable the plugin |
| `provider` | string | `"tomtom"` | Choose `"tomtom"`, `"google_routes"`, or `"demo"` |
| `api_key` | string | `""` | API Key from TomTom or Google Cloud |
| `origin` | string | `""` | Default start address (e.g. `Musterstr. 1, Berlin` or `52.52,13.40`) |
| `destination` | string | `""` | Default destination address (e.g. `Alexanderplatz, Berlin` or `52.51,13.38`) |
| `unit_system` | string | `"metric"` | Choose `"metric"` (km) or `"imperial"` (miles) |
| `delay_threshold_mins` | integer | `5` | Minutes of delay before status turns yellow |
| `heavy_delay_threshold_mins` | integer | `15` | Minutes of delay before status turns red |
| `refresh_seconds` | integer | `300` | Polling interval in seconds (minimum 60) |
| `demo_mode` | boolean | `false` | Enable simulated data for instant testing |

### 2. Route 1 Configuration

| Setting | Type | Default | Description |
|---|---|---|---|
| `route1_name` | string | `"Route 1"` | Display name (e.g. `A1 Autobahn`) |
| `route1_gpx_path` | string | `""` | **GPX Route File**: Relative path (e.g. `routes/route1.gpx`) or absolute path to a GPX track. Reconstructs exact road geometry! |
| `route1_maps_url` | string | `""` | **Google Maps Link**: Share link (`https://maps.app.goo.gl/...`). Start, destination, and dragged waypoints are automatically extracted! |
| `route1_origin` | string | `""` | Specific start address (leave empty to use default or if using Maps Link/GPX) |
| `route1_destination` | string | `""` | Specific destination address (leave empty to use default or if using Maps Link/GPX) |
| `route1_via` | string | `""` | Optional waypoint corridor (e.g. `A1` or `Kreuz Hilden`) |
| `route1_avoid_highways`| boolean | `false` | Avoid highways for Route 1 |
| `route1_avoid_tolls` | boolean | `false` | Avoid tolls for Route 1 |
| `route1_alternative_index` | integer | `0` | Route alternative index (0 = primary route) |

### 3. Route 2 Configuration

| Setting | Type | Default | Description |
|---|---|---|---|
| `route2_name` | string | `"Route 2"` | Display name (e.g. `B3 Landstr.`) |
| `route2_gpx_path` | string | `""` | **GPX Route File**: Relative path (e.g. `routes/route2.gpx`) or absolute path to a GPX track. Reconstructs exact road geometry! |
| `route2_maps_url` | string | `""` | **Google Maps Link**: Share link (`https://maps.app.goo.gl/...`). Start, destination, and dragged waypoints are automatically extracted! |
| `route2_origin` | string | `""` | Specific start address (leave empty to use default or if using Maps Link/GPX) |
| `route2_destination` | string | `""` | Specific destination address (leave empty to use default or if using Maps Link/GPX) |
| `route2_via` | string | `""` | Optional waypoint corridor (e.g. `B3` or `Dormagen`) |
| `route2_avoid_highways`| boolean | `false` | Avoid highways for Route 2 (forces local roads) |
| `route2_avoid_tolls` | boolean | `false` | Avoid tolls for Route 2 |
| `route2_alternative_index` | integer | `1` | Route alternative index (1 = alternative 1) |

---

## 🔑 Getting a Free TomTom API Key (Recommended)

1. Sign up for a free developer account at [developer.tomtom.com](https://developer.tomtom.com/). **No credit card is required!**
2. In your dashboard under **My Apps / Keys**, copy your default API Key.
3. Paste the key into the `api_key` field in FiestaBoard.
4. With 2,500 free requests per day, polling every 5 minutes only uses ~288 requests/day (~11% of the free allowance).

---

## 📊 Available Template Variables

| Variable | Group | Description | Example |
|---|---|---|---|
| `commute.route1_name` | Route 1 | Display name of Route 1 | `A1 Autobahn` |
| `commute.route1_duration` | Route 1 | Travel duration in traffic | `34m` |
| `commute.route1_duration_mins` | Route 1 | Integer travel minutes | `34` |
| `commute.route1_static_duration` | Route 1 | Normal duration without traffic | `22m` |
| `commute.route1_delay` | Route 1 | Traffic delay string | `+12m` |
| `commute.route1_delay_mins` | Route 1 | Integer delay minutes | `12` |
| `commute.route1_distance` | Route 1 | Distance with unit | `32.4 km` |
| `commute.route1_summary` | Route 1 | Road summary | `via A1` |
| `commute.route1_badge` | Route 1 | Vestaboard color tile | `{63}` |
| `commute.route1_status` | Route 1 | Status text | `HEAVY` |
| `commute.route2_name` | Route 2 | Display name of Route 2 | `B3 Landstr.` |
| `commute.route2_duration` | Route 2 | Travel duration in traffic | `28m` |
| `commute.route2_duration_mins` | Route 2 | Integer travel minutes | `28` |
| `commute.route2_static_duration` | Route 2 | Normal duration without traffic | `27m` |
| `commute.route2_delay` | Route 2 | Traffic delay string | `+1m` |
| `commute.route2_delay_mins` | Route 2 | Integer delay minutes | `1` |
| `commute.route2_distance` | Route 2 | Distance with unit | `26.1 km` |
| `commute.route2_summary` | Route 2 | Road summary | `via B3` |
| `commute.route2_badge` | Route 2 | Vestaboard color tile | `{66}` |
| `commute.route2_status` | Route 2 | Status text | `CLEAR` |
| `commute.faster_route` | Comparison | Identifier of faster route | `Route 2` |
| `commute.faster_route_name` | Comparison | Name of faster route | `B3 Landstr.` |
| `commute.time_diff` | Comparison | Formatted time savings | `6m` |
| `commute.time_diff_mins` | Comparison | Integer time savings minutes | `6` |
| `commute.recommendation` | Comparison | Actionable suggestion | `TAKE B3 (-6M)` |
| `commute.recommendation_badge` | Comparison | Suggestion tile | `{66}` |
| `commute.last_updated` | System | Time of last update | `07:45` |

---

## 🧪 Development & Testing

```bash
# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Run unit tests and coverage
pytest --cov=plugins/commute tests/
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
