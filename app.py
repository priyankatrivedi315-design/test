import os
import datetime
import requests

from flask import Flask, jsonify, request, send_from_directory
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__, static_folder="static")

# =========================
# API URLs
# =========================
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WX_URL = "https://api.open-meteo.com/v1/forecast"

# =========================
# Weather Code Mapping
# =========================
WMO = {
    0: ("Clear Sky", "sunny"),
    1: ("Mainly Clear", "sunny"),
    2: ("Partly Cloudy", "partly-cloudy"),
    3: ("Overcast", "cloudy"),
    45: ("Foggy", "cloudy"),
    48: ("Foggy", "cloudy"),
    51: ("Light Drizzle", "rainy"),
    53: ("Drizzle", "rainy"),
    55: ("Heavy Drizzle", "rainy"),
    61: ("Rain", "rainy"),
    63: ("Rain", "rainy"),
    65: ("Heavy Rain", "rainy"),
    71: ("Snow", "snowy"),
    73: ("Snow", "snowy"),
    75: ("Heavy Snow", "snowy"),
    80: ("Rain Showers", "rainy"),
    81: ("Rain Showers", "rainy"),
    82: ("Heavy Rain Showers", "rainy"),
    95: ("Thunderstorm", "stormy"),
}

# =========================
# Retry Session
# =========================
def make_session():
    session = requests.Session()

    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )

    adapter = HTTPAdapter(max_retries=retry)

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


# =========================
# WMO Lookup
# =========================
def weather_lookup(code):
    return WMO.get(int(code), ("Unknown", "sunny"))


# =========================
# Geocode
# =========================
def geocode(city):
    session = make_session()

    response = session.get(
        GEO_URL,
        params={
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json"
        },
        timeout=15
    )

    response.raise_for_status()

    results = response.json().get("results")

    if not results:
        return None

    result = results[0]

    return {
        "lat": result["latitude"],
        "lon": result["longitude"],
        "city": result["name"],
        "region": result.get("admin1", ""),
        "country": result.get("country", ""),
    }


# =========================
# Search API
# =========================
@app.route("/api/search")
def search():

    q = request.args.get("q", "").strip()

    if not q:
        return jsonify([])

    session = make_session()

    try:
        response = session.get(
            GEO_URL,
            params={
                "name": q,
                "count": 6,
                "language": "en",
                "format": "json"
            },
            timeout=15
        )

        response.raise_for_status()

        results = response.json().get("results", [])

        output = []

        for r in results:
            output.append({
                "city": r["name"],
                "admin1": r.get("admin1", ""),
                "country": r.get("country", ""),
                "country_code": r.get("country_code", ""),
                "lat": r["latitude"],
                "lon": r["longitude"],
                "label": f"{r['name']}, {r.get('country', '')}"
            })

        return jsonify(output)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# Weather API
# =========================
@app.route("/api/weather")
def weather():

    city = request.args.get("city", "New York")

    lat = request.args.get("lat")
    lon = request.args.get("lon")

    try:

        if lat and lon:
            lat = float(lat)
            lon = float(lon)

            geo = {
                "lat": lat,
                "lon": lon,
                "city": city,
                "region": "",
                "country": ""
            }

        else:
            geo = geocode(city)

            if not geo:
                return jsonify({
                    "error": "City not found"
                }), 404

        session = make_session()

        response = session.get(
            WX_URL,
            params={
                "latitude": geo["lat"],
                "longitude": geo["lon"],

                "current": [
                    "temperature_2m",
                    "apparent_temperature",
                    "weather_code",
                    "wind_speed_10m",
                    "relative_humidity_2m",
                    "surface_pressure"
                ],

                "hourly": [
                    "temperature_2m",
                    "weather_code"
                ],

                "daily": [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min"
                ],

                "forecast_days": 15,
                "timezone": "auto"
            },
            timeout=20
        )

        response.raise_for_status()

        raw = response.json()

        current = raw["current"]

        code = current["weather_code"]

        description, condition = weather_lookup(code)

        today = datetime.date.today()

        # =====================
        # Hourly
        # =====================
        hourly = []

        hourly_times = raw["hourly"]["time"]
        hourly_temps = raw["hourly"]["temperature_2m"]
        hourly_codes = raw["hourly"]["weather_code"]

        for i in range(24):

            t = hourly_times[i]

            hour = int(t[11:13])

            _, cond = weather_lookup(hourly_codes[i])

            hourly.append({
                "time": f"{hour}:00",
                "temp": round(hourly_temps[i]),
                "condition": cond,
                "is_now": i == 0,
                "is_past": False
            })

        # =====================
        # Daily
        # =====================
        daily = []

        for i in range(1, 15):

            date = today + datetime.timedelta(days=i)

            _, cond = weather_lookup(
                raw["daily"]["weather_code"][i]
            )

            daily.append({
                "day": date.strftime("%A"),
                "date": date.strftime("%b %d"),
                "date_key": date.strftime("%Y-%m-%d"),
                "condition": cond,
                "high": round(raw["daily"]["temperature_2m_max"][i]),
                "low": round(raw["daily"]["temperature_2m_min"][i])
            })

        return jsonify({
            "location": f"{geo['city']}, {geo['country']}",
            "temperature": round(current["temperature_2m"]),
            "feels_like": round(current["apparent_temperature"]),
            "description": description,
            "condition": condition,
            "wind": round(current["wind_speed_10m"]),
            "humidity": round(current["relative_humidity_2m"]),
            "pressure": round(current["surface_pressure"]),
            "hourly": hourly,
            "daily": daily,
            "hourly_by_day": {}
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# =========================
# Frontend
# =========================
@app.route("/")
def home():
    return send_from_directory("static", "index.html")


# =========================
# Health
# =========================
@app.route("/health")
def health():
    return jsonify({
        "status": "ok"
    })


# =========================
# Run
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
