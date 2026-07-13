import pandas as pd
import pickle
import os

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

print("🚀 FINAL MODEL TRAINING STARTED")

# Load dataset
data = pd.read_csv("dataset/flood_risk_dataset_india.csv.xlsx")
data.columns = data.columns.str.strip()

target = "Flood Occurred"

feature_columns = [
    "Latitude",
    "Longitude",
    "Annual Rainfall (mm)",
    "Temperature (°C)",
    "Humidity (%)",
    "River Discharge (m3/s)",
    "Water Level (m)",
    "Elevation (m)",
    "Population Density",
    "Infrastructure",
    "Historical Floods",
    "Cloud Visibility(%)",
    "Seasonal Rainfall"
]

X = data[feature_columns]
y = data[target]

X = X.fillna(X.mean(numeric_only=True))

print("TOTAL FEATURES:", X.shape[1])

# Split RAW data (IMPORTANT FIX)
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# Scaling
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Model
rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=None,
    min_samples_split=5,
    random_state=42
)

rf.fit(X_train_scaled, y_train)

pred = rf.predict(X_test_scaled)

accuracy = accuracy_score(y_test, pred)

print("🎯 Accuracy:", round(accuracy * 100, 2), "%")

# Save model + scaler
os.makedirs("models", exist_ok=True)

pickle.dump(rf, open("models/flood_model.pkl", "wb"))
pickle.dump(scaler, open("models/scaler.pkl", "wb"))

print("💾 Model & Scaler Saved Successfully")
print("🎉 TRAINING COMPLETED")