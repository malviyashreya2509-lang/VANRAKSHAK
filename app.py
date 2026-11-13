from flask import Flask, render_template, request, jsonify
import requests
import logging
from datetime import datetime

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# LOCATION SEARCH
# ==========================================

@app.route("/api/location")
def location():

    try:
        query = request.args.get("q", "").strip()

        if not query:
            return jsonify({
                "error": "Please enter a location"
            }), 400

        response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": query,
                "count": 5,
                "language": "en",
                "format": "json"
            },
            timeout=15
        )

        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if not results:
            return jsonify({
                "error": "Location not found"
            }), 404

        locations = []

        for item in results:

            locations.append({
                "name": item.get("name"),
                "country": item.get("country"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "lat": item.get("latitude"),
                "lon": item.get("longitude"),
                "admin1": item.get("admin1")
            })

        return jsonify({
            "results": locations,
            "locations": locations
        })

    except requests.exceptions.RequestException as e:

        logging.error("Location API error: %s", e)

        return jsonify({
            "error": "Location service unavailable"
        }), 502

    except Exception as e:

        logging.exception("Location error")

        return jsonify({
            "error": str(e)
        }), 500


# ==========================================
# WEATHER API
# ==========================================

@app.route("/api/weather")
def weather():

    try:

        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))

        # Validate coordinates
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):

            return jsonify({
                "error": "Invalid coordinates"
            }), 400

        # Open-Meteo API
        url = "https://api.open-meteo.com/v1/forecast"

        params = {

            "latitude": lat,
            "longitude": lon,
            "timezone": "auto",
            "forecast_days": 1,

            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "precipitation,"
                "rain,"
                "wind_speed_10m"
            ),

            "hourly": (
                "soil_moisture_0_to_1cm,"
                "shortwave_radiation"
            )
        }

        r = requests.get(
            url,
            params=params,
            timeout=20
        )

        logging.info("Weather API status: %s", r.status_code)

        if r.status_code != 200:

            logging.error("Weather API response: %s", r.text)

            return jsonify({
                "error": "Weather API unavailable",
                "details": r.text
            }), 502

        data = r.json()

        current = data.get("current", {})
        hourly = data.get("hourly", {})

        # Current weather values
        temperature = current.get("temperature_2m")

        humidity = current.get(
            "relative_humidity_2m"
        )

        rainfall = current.get("precipitation")

        rain = current.get("rain")

        wind_speed = current.get(
            "wind_speed_10m"
        )

        # Hourly values
        times = hourly.get("time", [])

        soils = hourly.get(
            "soil_moisture_0_to_1cm", []
        )

        radiation = hourly.get(
            "shortwave_radiation", []
        )

        soil = None
        solar = None

        if times:

            current_time = current.get("time", "")

            # Find nearest matching hour
            index = next(
                (
                    i for i, t in enumerate(times)
                    if t[:13] == current_time[:13]
                ),
                0
            )

            if index < len(soils):
                soil = soils[index]

            if index < len(radiation):
                solar = radiation[index]

        # Weather response
        result = {

            "temperature": temperature,

            "humidity": humidity,

            "rainfall": rainfall,

            "rain": rain,

            "wind_speed": wind_speed,

            "soil": soil,

            "soil_moisture": soil,

            "solar": solar,

            "solar_radiation": solar,

            "latitude": lat,

            "longitude": lon,

            "location": data.get("timezone")

        }

        return jsonify(result)

    except ValueError:

        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    except requests.exceptions.Timeout:

        logging.error("Weather API timeout")

        return jsonify({
            "error": "Weather API timeout"
        }), 504

    except requests.exceptions.RequestException as e:

        logging.error("Weather connection error: %s", e)

        return jsonify({
            "error": "Weather service unavailable"
        }), 502

    except Exception as e:

        logging.exception("Weather error")

        return jsonify({
            "error": "Internal weather error",
            "details": str(e)
        }), 500


# ==========================================
# FOREST FIRE RISK CALCULATION
# ==========================================

def calculate_risk_score(
    temperature,
    humidity,
    rainfall,
    wind_speed,
    soil_moisture,
    solar_radiation
):

    score = 0

    # Temperature contribution (0-25)
    if temperature is not None:

        score += min(
            max((temperature - 15) / 30 * 25, 0),
            25
        )

    # Humidity contribution (0-20)
    if humidity is not None:

        score += min(
            max((100 - humidity) / 100 * 20, 0),
            20
        )

    # Rainfall contribution (0-20)
    if rainfall is not None:

        score += min(
            max((10 - rainfall) / 10 * 20, 0),
            20
        )

    # Wind contribution (0-15)
    if wind_speed is not None:

        score += min(
            max(wind_speed / 60 * 15, 0),
            15
        )

    # Soil moisture contribution (0-10)
    if soil_moisture is not None:

        score += min(
            max((1 - soil_moisture) * 10, 0),
            10
        )

    # Solar radiation contribution (0-10)
    if solar_radiation is not None:

        score += min(
            max(solar_radiation / 1000 * 10, 0),
            10
        )

    return round(min(max(score, 0), 100), 2)


def get_risk_level(score):

    if score < 20:
        return "Low"

    elif score < 40:
        return "Moderate"

    elif score < 60:
        return "High"

    elif score < 80:
        return "Very High"

    else:
        return "Extreme"


# ==========================================
# RISK API
# ==========================================

@app.route("/api/risk", methods=["POST"])
def risk():

    try:

        data = request.get_json(silent=True) or {}

        # Read weather values
        temperature = data.get("temperature")

        humidity = data.get("humidity")

        rainfall = data.get(
            "rainfall",
            data.get("rain", 0)
        )

        wind_speed = data.get("wind_speed")

        soil_moisture = data.get(
            "soil_moisture",
            data.get("soil")
        )

        solar_radiation = data.get(
            "solar_radiation",
            data.get("solar")
        )

        # Convert to numbers
        temperature = (
            float(temperature)
            if temperature is not None else None
        )

        humidity = (
            float(humidity)
            if humidity is not None else None
        )

        rainfall = (
            float(rainfall)
            if rainfall is not None else None
        )

        wind_speed = (
            float(wind_speed)
            if wind_speed is not None else None
        )

        soil_moisture = (
            float(soil_moisture)
            if soil_moisture is not None else None
        )

        solar_radiation = (
            float(solar_radiation)
            if solar_radiation is not None else None
        )

        # Validate required weather inputs
        if temperature is None or humidity is None:

            return jsonify({
                "error": "Temperature and humidity required"
            }), 400

        # Risk calculation
        risk_score = calculate_risk_score(
            temperature,
            humidity,
            rainfall,
            wind_speed,
            soil_moisture,
            solar_radiation
        )

        risk_level = get_risk_level(risk_score)

        # Recommendations
        recommendations = []

        if risk_score >= 60:

            recommendations.append(
                "High fire danger. Increase forest monitoring."
            )

            recommendations.append(
                "Avoid open flames in forest areas."
            )

            recommendations.append(
                "Alert nearby forest authorities."
            )

        elif risk_score >= 40:

            recommendations.append(
                "Monitor forest conditions regularly."
            )

            recommendations.append(
                "Avoid burning activities near vegetation."
            )

        else:

            recommendations.append(
                "Continue routine forest monitoring."
            )

        return jsonify({

            "risk_score": risk_score,

            "score": risk_score,

            "risk_level": risk_level,

            "level": risk_level,

            "recommendations": recommendations,

            "message": (
                "Forest fire risk calculated successfully"
            )

        })

    except (ValueError, TypeError):

        return jsonify({
            "error": "Invalid weather input values"
        }), 400

    except Exception as e:

        logging.exception("Risk calculation error")

        return jsonify({
            "error": str(e)
        }), 500


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
