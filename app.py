from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/location")
def location():
    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify({"results": []})

    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": query,
                "count": 10,
                "language": "en"
            },
            timeout=15
        )
        r.raise_for_status()
        data = r.json()

        places = data.get("results", [])

        # Indian locations ko preference
        india = [
            p for p in places
            if p.get("country_code") == "IN"
        ]

        if india:
            places = india

        return jsonify({"results": places})

    except requests.RequestException:
        return jsonify({
            "error": "Location service unavailable"
        }), 502


@app.route("/api/weather")
def weather():
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return jsonify({"error": "Invalid coordinates"}), 400

        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "precipitation,"
                    "wind_speed_10m,"
                    "shortwave_radiation"
                ),
                "hourly": "soil_moisture_0_to_1cm",
                "forecast_days": 1,
                "timezone": "auto"
            },
            timeout=20
        )

        r.raise_for_status()
        data = r.json()

        current = data.get("current", {})
        hourly = data.get("hourly", {})

        times = hourly.get("time", [])
        soils = hourly.get("soil_moisture_0_to_1cm", [])

        soil = None

        if times and soils:
            current_time = current.get("time", "")[:13]

            index = min(
                range(len(times)),
                key=lambda i: abs(
                    times[i][:13] - current_time
                )
            )

            if index < len(soils):
                soil = soils[index]

        return jsonify({
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "rainfall": current.get("precipitation"),
            "wind": current.get("wind_speed_10m"),
            "solar": current.get("shortwave_radiation"),
            "soil": soil
        })

    except ValueError:
        return jsonify({"error": "Invalid coordinates"}), 400

    except requests.RequestException:
        return jsonify({
            "error": "Weather service unavailable"
        }), 502


@app.route("/api/risk", methods=["POST"])
def risk():

    data = request.get_json(silent=True) or {}

    try:
        temp = float(data["temperature"])
        humidity = float(data["humidity"])
        rainfall = float(data["rainfall"])
        wind = float(data["wind"])
        vegetation = float(data["vegetation"])
        soil = float(data["soil"])
        solar = float(data["solar"])
        history = int(data["history"])

    except (KeyError, ValueError, TypeError):
        return jsonify({
            "error": "Missing or invalid parameters"
        }), 400

    humidity = max(0, min(100, humidity))
    vegetation = max(0, min(100, vegetation))

    # Soil moisture API returns fraction 0-1
    soil = max(0, min(1, soil)) * 100

    temp_risk = max(0, min(100, (temp - 10) / 35 * 100))
    humidity_risk = 100 - humidity
    rainfall_risk = max(0, 100 - max(0, rainfall) * 5)
    wind_risk = max(0, min(100, wind / 60 * 100))
    soil_risk = 100 - soil
    solar_risk = max(0, min(100, solar / 1000 * 100))
    history_risk = 100 if history == 1 else 0

    score = (
        temp_risk * 0.20 +
        humidity_risk * 0.15 +
        rainfall_risk * 0.15 +
        wind_risk * 0.10 +
        vegetation * 0.15 +
        soil_risk * 0.10 +
        solar_risk * 0.10 +
        history_risk * 0.05
    ) * 3

    score = round(max(0, min(300, score)), 1)

    if score <= 60:
        level = "LOW"
    elif score <= 120:
        level = "MODERATE"
    elif score <= 180:
        level = "HIGH"
    elif score <= 240:
        level = "VERY HIGH"
    else:
        level = "EXTREME"

    return jsonify({
        "score": score,
        "level": level
    })


if __name__ == "__main__":
    app.run(debug=True)