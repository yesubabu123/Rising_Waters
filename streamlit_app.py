import streamlit as st
import pickle
import numpy as np

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(
    page_title="Flood Prediction System",
    page_icon="🌊",
    layout="wide"
)

# ==============================
# LOAD MODEL + SCALER
# ==============================
model = pickle.load(open("models/flood_model.pkl", "rb"))
scaler = pickle.load(open("models/scaler.pkl", "rb"))

# ==============================
# TITLE
# ==============================
st.title("🌊 Flood Prediction System")
st.write("Enter the environmental details below and click Predict.")

# ==============================
# INPUT FIELDS
# ==============================
col1, col2 = st.columns(2)

with col1:
    latitude = st.number_input("Latitude", value=13.0827)
    longitude = st.number_input("Longitude", value=80.2707)
    annual_rainfall = st.number_input("Annual Rainfall (mm)", value=900.0)
    temperature = st.number_input("Temperature (°C)", value=32.0)
    humidity = st.number_input("Humidity (%)", value=60.0)
    river_discharge = st.number_input("River Discharge (m³/s)", value=120.0)
    water_level = st.number_input("Water Level (m)", value=2.5)

with col2:
    elevation = st.number_input("Elevation (m)", value=45.0)
    population_density = st.number_input("Population Density", value=1200)
    infrastructure = st.number_input("Infrastructure", value=80)
    historical_floods = st.number_input("Historical Floods", value=0)
    cloud_visibility = st.number_input("Cloud Visibility", value=70.0)
    seasonal_rainfall = st.number_input("Seasonal Rainfall", value=800.0)

# ==============================
# PREDICT BUTTON
# ==============================
if st.button("Predict Flood Risk"):

    input_data = np.array([[
        latitude,
        longitude,
        annual_rainfall,
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

    input_scaled = scaler.transform(input_data)

    prediction = model.predict(input_scaled)[0]

    st.subheader("Prediction Result")

    if prediction == 2:
        st.error("🌊 HIGH FLOOD RISK")

    elif prediction == 1:
        st.warning("⚠️ MEDIUM FLOOD RISK")

    else:
        st.success("✅ LOW / SAFE AREA")