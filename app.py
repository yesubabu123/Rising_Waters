import os
import pickle
from pathlib import Path

from flask import Flask, redirect, render_template, request
from pymongo import MongoClient

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "flood_model.pkl"
SCALER_PATH = MODELS_DIR / "scaler.pkl"
TEMPLATE_DIR = BASE_DIR / "frontend" / "templates"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
app.config["JSON_SORT_KEYS"] = False

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/rising_waters")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    db = client["rising_waters"]
    print("✅ Successfully connected to MongoDB!")
except Exception as exc:
    db = None
    print(f"❌ MongoDB connection failed: {exc}")

model = None
scaler = None

try:
    with MODEL_PATH.open("rb") as handle:
        model = pickle.load(handle)
    if SCALER_PATH.exists():
        with SCALER_PATH.open("rb") as handle:
            scaler = pickle.load(handle)
    print("✅ Successfully loaded machine learning model!")
except Exception as exc:
    print(f"❌ Error loading model: {exc}")
    model = None
    scaler = None


@app.route("/")
def home():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username and password:
            return redirect("/predict")
        error = "Please enter a username and password."
    return render_template("login.html", error=error, model_status="ready" if model else "unavailable")


@app.route("/predict")
def predict():
    message = "Prediction service is ready." if model else "Prediction model is currently unavailable on this server."
    return render_template("error.html", error=message)


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", error="Page not found"), 404


@app.errorhandler(500)
def server_error(_error):
    return render_template("error.html", error="Internal server error"), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)