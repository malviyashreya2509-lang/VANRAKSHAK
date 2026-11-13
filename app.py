from flask import Flask, render_template, request, jsonify
import requests
import logging
import os
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

    except requests.exceptions.RequestException:

        logging.exception("Location API error")

        return jsonify({
            "error": "Location service unavailable"
        }), 502

    except Exception:

        logging.exception("Location error")

        return jsonify({
            "error": "Location search failed"
        }), 500


# ==========================================
# WEATHER API - WEATHERAPI.COM
# ==========================================

@app.route("/api/weather")
def weather():

    try:

        lat = request.args.get("lat", type=float)
        lon = request.args.get("lon", type=float)

        # Validate coordinates
        if lat is None or lon is None:

            return jsonify({
                "success": False,
                "error": "Latitude and longitude required"
            }), 400

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):

            return jsonify({
                "success": False,
                "error": "Invalid coordinates"
            }), 400

        # Get API key from Render Environment
        api_key = os.environ.get("WEATHER_API_KEY")

        if not api_key:

            return jsonify({
                "success": False,
                "error": "Weather API key missing"
            }), 500

        # WeatherAPI current weather
        url = "https://api.weatherapi.com/v1/current.json"

        params = {
            "key": api_key,
            "q": f"{lat},{lon}",
            "aqi": "no"
        }

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        logging.info(
            "WeatherAPI status: %s",
            response.status_code
        )

        if response.status_code != 200:

            logging.error(
                "WeatherAPI response: %s",
                response.text
            )

            return jsonify({
                "success": False,
                "error": "Weather API unavailable"
            }), 502

        data = response.json()

        current = data.get("current", {})
        location_data = data.get("location", {})

        # Weather values
        temperature = current.get("temp_c")
        humidity = current.get("humidity")
        rainfall = current.get("precip_mm")
        wind_speed = current.get("wind_kph")

        # Soil moisture and solar unavailable
        soil = None
        solar = None

        result = {

            "success": True,

            "temperature": temperature,

            "humidity": humidity,

            "rainfall": rainfall,

            "rain": rainfall,

            "wind_speed": wind_speed,

            "soil": soil,

            "soil_moisture": soil,

            "solar": solar,

            "solar_radiation": solar,

            "latitude": location_data.get("lat", lat),

            "longitude": location_data.get("lon", lon),

            "location": location_data.get("name"),

            "country": location_data.get("country"),

            "weather_time": current.get("last_updated")

        }

        return jsonify(result)

    except requests.exceptions.Timeout:

        logging.error("Weather API timeout")

        return jsonify({
            "success": False,
            "error": "Weather API timeout"
        }), 504

    except requests.exceptions.RequestException:

        logging.exception("Weather connection error")

        return jsonify({
            "success": False,
            "error": "Weather connection failed"
        }), 502

    except Exception:

        logging.exception("Weather error")

        return jsonify({
            "success": False,
            "error": "Internal weather error"
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


# ==========================================
# RISK LEVEL
# ==========================================

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

        # Weather inputs
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

        # Convert values safely
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

        # Validate required inputs
        if temperature is None or humidity is None:

            return jsonify({
                "error": "Temperature and humidity required"
            }), 400

        if not (0 <= humidity <= 100):

            return jsonify({
                "error": "Humidity must be between 0 and 100"
            }), 400

        if rainfall is not None and rainfall < 0:

            return jsonify({
                "error": "Rainfall cannot be negative"
            }), 400

        if wind_speed is not None and wind_speed < 0:

            return jsonify({
                "error": "Wind speed cannot be negative"
            }), 400

        # Calculate risk
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

        if risk_score >= 80:

            recommendations.extend([
                "Extreme fire danger. Immediate forest monitoring required.",
                "Avoid all open flames and burning activities.",
                "Alert forest authorities immediately.",
                "Increase patrols in vulnerable forest areas."
            ])

        elif risk_score >= 60:

            recommendations.extend([
                "Very high fire danger. Increase forest monitoring.",
                "Avoid open flames in forest areas.",
                "Alert nearby forest authorities.",
                "Monitor vulnerable forest zones regularly."
            ])

        elif risk_score >= 40:

            recommendations.extend([
                "High fire danger. Monitor forest conditions regularly.",
                "Avoid burning activities near vegetation.",
                "Keep fire prevention equipment ready."
            ])

        elif risk_score >= 20:

            recommendations.extend([
                "Moderate fire risk. Continue forest monitoring.",
                "Avoid careless disposal of burning materials.",
                "Maintain awareness of changing weather conditions."
            ])

        else:

            recommendations.extend([
                "Low fire risk under current weather conditions.",
                "Continue routine forest monitoring.",
                "Follow standard forest fire prevention practices."
            ])

        return jsonify({

            "success": True,

            "risk_score": risk_score,

            "score": risk_score,

            "risk_level": risk_level,

            "level": risk_level,

            "recommendations": recommendations,

            "message": "Forest fire risk calculated successfully"

        })

    except (ValueError, TypeError):

        return jsonify({
            "error": "Invalid weather input values"
        }), 400

    except Exception:

        logging.exception("Risk calculation error")

        return jsonify({
            "error": "Risk calculation failed"
        }), 500


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
