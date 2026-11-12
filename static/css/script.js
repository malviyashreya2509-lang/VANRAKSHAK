let currentWeather = null;

function setLocation(lat, lon) {
    document.getElementById("latitude").value = lat;
    document.getElementById("longitude").value = lon;
}

async function searchLocation() {
    const query = document.getElementById("locationInput").value.trim();
    const results = document.getElementById("locationResults");

    if (!query) {
        results.textContent = "Please enter a location.";
        return;
    }

    results.textContent = "Searching location...";

    try {
        const response = await fetch(
            `/api/location?q=${encodeURIComponent(query)}`
        );
        const data = await response.json();

        results.innerHTML = "";

        if (!response.ok || data.error) {
            results.textContent = "Location service unavailable. Try again.";
            return;
        }

        if (!data.results || data.results.length === 0) {
            results.textContent =
                "No location found. Try 'Deoghar, Jharkhand'.";
            return;
        }

        data.results.forEach(place => {
            const option = document.createElement("div");
            option.className = "location-option";

            option.textContent =
                `${place.name}, ${place.admin1 || ""}, ${place.country}`;

            option.onclick = () => {
                setLocation(place.latitude, place.longitude);
                results.textContent =
                    `Selected: ${place.name}, ${place.country}`;
            };

            results.appendChild(option);
        });

    } catch (error) {
        results.textContent = "Connection error. Check your internet.";
        console.error(error);
    }
}

function getGPS() {
    const results = document.getElementById("locationResults");

    if (!navigator.geolocation) {
        results.textContent = "GPS is not supported by this browser.";
        return;
    }

    results.textContent = "Getting GPS location...";

    navigator.geolocation.getCurrentPosition(
        position => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            setLocation(lat, lon);
            results.textContent =
                `GPS detected: ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
        },
        error => {
            const messages = {
                1: "Location permission denied. Allow location in browser settings.",
                2: "GPS location unavailable. Try again.",
                3: "GPS request timed out. Try again."
            };

            results.textContent =
                messages[error.code] || "Unable to get GPS location.";
        },
        {
            enableHighAccuracy: true,
            timeout: 20000,
            maximumAge: 0
        }
    );
}

async function loadWeather() {
    const lat = document.getElementById("latitude").value.trim();
    const lon = document.getElementById("longitude").value.trim();

    if (lat === "" || lon === "") {
        alert("Search a location or enter latitude and longitude.");
        return;
    }

    if (
        Number(lat) < -90 || Number(lat) > 90 ||
        Number(lon) < -180 || Number(lon) > 180
    ) {
        alert("Latitude must be -90 to 90 and longitude -180 to 180.");
        return;
    }

    const button = document.querySelector(
        'button[onclick="loadWeather()"]'
    );
    button.textContent = "Loading weather...";
    button.disabled = true;

    try {
        const response = await fetch(
            `/api/weather?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`
        );
        const data = await response.json();

        if (!response.ok || data.error) {
            alert(data.error || "Weather data unavailable.");
            return;
        }

        currentWeather = data;

        document.getElementById("temperature").textContent =
            `${data.temperature ?? "--"} °C`;

        document.getElementById("humidity").textContent =
            `${data.humidity ?? "--"} %`;

        document.getElementById("rainfall").textContent =
            `${data.rainfall ?? "--"} mm`;

        document.getElementById("wind").textContent =
            `${data.wind ?? "--"} km/h`;

        document.getElementById("soil").textContent =
            data.soil == null ? "Unavailable" : `${data.soil}`;

        document.getElementById("solar").textContent =
            `${data.solar ?? "--"} W/m²`;

        alert("Weather data loaded successfully!");

    } catch (error) {
        alert("Network error while fetching weather.");
        console.error(error);
    } finally {
        button.textContent = "Get Weather Data";
        button.disabled = false;
    }
}

async function calculateRisk() {
    if (!currentWeather) {
        alert("Please load weather data first.");
        return;
    }

    const vegetation = Number(
        document.getElementById("vegetation").value
    );

    if (vegetation < 0 || vegetation > 100 || !Number.isFinite(vegetation)) {
        alert("Vegetation dryness must be between 0 and 100.");
        return;
    }

    const soil = currentWeather.soil ?? 0.3;

    const payload = {
        temperature: currentWeather.temperature,
        humidity: currentWeather.humidity,
        rainfall: currentWeather.rainfall,
        wind: currentWeather.wind,
        solar: currentWeather.solar,
        soil: soil,
        vegetation: vegetation,
        history: Number(document.getElementById("history").value)
    };

    try {
        const response = await fetch("/api/risk", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok || data.error) {
            alert(data.error || "Risk calculation failed.");
            return;
        }

        document.getElementById("riskScore").textContent =
            `${data.score} / 300`;

        document.getElementById("riskLevel").textContent = data.level;

        const messages = {
            "LOW": "Low estimated fire risk.",
            "MODERATE": "Moderate risk. Continue monitoring.",
            "HIGH": "High risk. Increased monitoring recommended.",
            "VERY HIGH": "Very high risk. Alert forest authorities.",
            "EXTREME": "Extreme estimated risk. Immediate assessment recommended."
        };

        document.getElementById("riskMessage").textContent =
            messages[data.level] || "Analysis completed.";

    } catch (error) {
        alert("Network error during risk calculation.");
        console.error(error);
    }
}
