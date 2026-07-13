import pickle
import numpy as np
import os

# ==============================
# Load Model and Scaler
# ==============================

MODEL_PATH = os.path.join("models", "flood_model.pkl")
SCALER_PATH = os.path.join("models", "scaler.pkl")

model = pickle.load(open(MODEL_PATH, "rb"))
scaler = pickle.load(open(SCALER_PATH, "rb"))

# ==============================
# Flood Prediction Function
# ==============================

def predict_flood(
        latitude,
        longitude,
        rainfall,
        temperature,
        humidity,
        river_discharge,
        water_level,
        elevation,
        population_density,
        infrastructure,
        historical_floods,
        cloud_visibility,
        seasonal_rainfall):

    features = np.array([[
        latitude,
        longitude,
        rainfall,
        temperature,
        humidity,
        river_discharge,
        water_level,
        elevation,
        population_density,
        infrastructure,
        historical_floods,
        cloud_visibility,
        seasonal_rainfall
    ]])

    features_scaled = scaler.transform(features)

    prediction = model.predict(features_scaled)[0]

    confidence = None

    if hasattr(model, "predict_proba"):

        confidence = round(
            np.max(model.predict_proba(features_scaled)) * 100,
            2
        )

    if prediction == 1:

        result = "⚠ HIGH FLOOD RISK"

    else:

        result = "✅ LOW FLOOD RISK"

    return result, confidence


# ==============================
# Test Prediction
# ==============================

if __name__ == "__main__":

    result, confidence = predict_flood(
        16.50,      # Latitude
        79.20,      # Longitude
        2200,       # Rainfall
        28,         # Temperature
        86,         # Humidity
        450,        # River Discharge
        8.5,        # Water Level
        240,        # Elevation
        1800,       # Population Density
        6,          # Infrastructure
        4,          # Historical Floods
        65,         # Cloud Visibility
        1900        # Seasonal Rainfall
    )

    print("=" * 45)
    print("      RISING WATER AI SYSTEM")
    print("=" * 45)
    print("Prediction :", result)

    if confidence is not None:
        print("Confidence :", confidence, "%")

    print("=" * 45)