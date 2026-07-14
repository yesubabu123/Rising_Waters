from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import pickle
import numpy as np
import json
from datetime import datetime
import logging
import os
from functools import wraps
import csv
from pymongo import MongoClient

app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')
CORS(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

app.config['JSON_SORT_KEYS'] = False
LOG_FILE = 'flood_predictions.log'
PREDICTIONS_CSV = 'predictions_history.csv'

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

logger = logging.getLogger(__name__)

try:
    model = pickle.load(open("models/flood_model.pkl", "rb"))
    scaler = pickle.load(open("models/scaler.pkl", "rb"))
    logger.info("✅ Model and Scaler loaded successfully!")
except Exception as e:
    logger.error(f"❌ Error loading model: {str(e)}")
    model = None
    scaler = None

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB = os.environ.get('MONGO_DB', 'flood_prediction_db')
MONGO_COLLECTION = os.environ.get('MONGO_COLLECTION', 'predictions')

try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_client.server_info()
    mongo_db = mongo_client[MONGO_DB]
    mongo_collection = mongo_db[MONGO_COLLECTION]
    logger.info('✅ Connected to MongoDB successfully')
except Exception as e:
    mongo_collection = None
    logger.error(f'❌ MongoDB connection failed: {e}')

FEATURES = [
    "latitude", "longitude", "annual_rainfall", "temperature", "humidity",
    "river_discharge", "water_level", "elevation", "population_density",
    "infrastructure", "historical_floods", "cloud_visibility", "seasonal_rainfall"
]

FEATURE_LABELS = {
    "latitude": "Latitude (°)", "longitude": "Longitude (°)",
    "annual_rainfall": "Annual Rainfall (mm)", "temperature": "Temperature (°C)",
    "humidity": "Humidity (%)", "river_discharge": "River Discharge (m³/s)",
    "water_level": "Water Level (m)", "elevation": "Elevation (m)",
    "population_density": "Population Density (per km²)", "infrastructure": "Infrastructure Index",
    "historical_floods": "Historical Floods (count)", "cloud_visibility": "Cloud Visibility (%)",
    "seasonal_rainfall": "Seasonal Rainfall (mm)"
}

FEATURE_RANGES = {
    "latitude": (-90, 90), "longitude": (-180, 180), "annual_rainfall": (0, 12000),
    "temperature": (-50, 60), "humidity": (0, 100), "river_discharge": (0, 50000),
    "water_level": (-50, 50), "elevation": (-500, 9000), "population_density": (0, 100000),
    "infrastructure": (0, 1), "historical_floods": (0, 1000), "cloud_visibility": (0, 100),
    "seasonal_rainfall": (0, 5000)
}

RECENT_PREDICTIONS = int(os.environ.get('RECENT_PREDICTIONS', 10))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change_this_secret_key')
USERS_FILE = 'users.json'
ADMIN_USERNAME = os.environ.get('APP_AUTH_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('APP_AUTH_PASS', 'admin123')
AUTH_USERS = {ADMIN_USERNAME: ADMIN_PASSWORD}

def load_users():
    if os.path.isfile(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

AUTH_USERS.update(load_users())

def is_authenticated():
    return session.get('authenticated', False)

def is_admin():
    return session.get('username') == ADMIN_USERNAME

def get_current_user():
    return session.get('username')

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

RISK_MAPPING = {
    0: {"label": "LOW RISK", "icon": "✅", "color": "success", "level": "Low",
        "recommendations": ["Area is generally safe", "Monitor weather regularly", "Keep systems clear"]},
    1: {"label": "MEDIUM RISK", "icon": "⚠️", "color": "warning", "level": "Medium",
        "recommendations": ["Monitor weather closely", "Prepare emergency supplies", "Have evacuation plan ready"]},
    2: {"label": "HIGH RISK", "icon": "🚨", "color": "danger", "level": "High",
        "recommendations": ["IMMEDIATE ALERT", "EVACUATE if necessary", "Contact emergency services"]}
}

MODEL_ACCURACY = 100.0

def validate_input(feature, value):
    try:
        value = float(value)
        min_val, max_val = FEATURE_RANGES[feature]
        if value < min_val or value > max_val:
            return False, f"{FEATURE_LABELS[feature]} must be between {min_val} and {max_val}"
        return True, value
    except ValueError:
        return False, f"Invalid value for {FEATURE_LABELS[feature]}"

def validate_all_inputs(data_dict):
    for feature in FEATURES:
        if feature not in data_dict:
            return False, f"Missing feature: {FEATURE_LABELS[feature]}"
        is_valid, result = validate_input(feature, data_dict[feature])
        if not is_valid:
            return False, result
    return True, "All inputs valid"

def load_history():
    history = []
    if mongo_collection is not None:
        try:
            for doc in mongo_collection.find().sort('timestamp', 1):
                history.append({
                    'latitude': doc.get('latitude'), 'longitude': doc.get('longitude'),
                    'annual_rainfall': doc.get('rainfall'), 'temperature': doc.get('temperature'),
                    'humidity': doc.get('humidity'), 'river_discharge': doc.get('river_discharge'),
                    'water_level': doc.get('water_level'), 'elevation': doc.get('elevation'),
                    'population_density': doc.get('population_density'),
                    'infrastructure': doc.get('infrastructure'),
                    'historical_floods': doc.get('historical_floods'),
                    'cloud_visibility': doc.get('cloud_visibility'),
                    'seasonal_rainfall': doc.get('seasonal_rainfall'),
                    'prediction': int(doc.get('prediction_int', -1)),
                    'prediction_label': doc.get('prediction_label', 'Unknown'),
                    'timestamp': doc.get('timestamp', ''),
                    'risk_level': doc.get('risk', 'Unknown')
                })
        except Exception as e:
            logger.error(f"Error loading history from MongoDB: {e}")
            history = []
    if not history and os.path.isfile(PREDICTIONS_CSV):
        try:
            with open(PREDICTIONS_CSV, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    try:
                        row['prediction'] = int(row.get('prediction', -1))
                    except ValueError:
                        row['prediction'] = -1
                    history.append(row)
        except Exception as e:
            logger.error(f"Error loading history from CSV: {e}")
    return history

def collect_dashboard_stats():
    history = load_history()
    total_predictions = len(history)
    safe_cases = sum(1 for row in history if row.get('prediction') == 0)
    flood_cases = sum(1 for row in history if row.get('prediction') in (1, 2))
    today = datetime.now().date()
    todays_predictions = 0
    for row in history:
        timestamp = row.get('timestamp')
        if timestamp:
            try:
                if datetime.fromisoformat(timestamp).date() == today:
                    todays_predictions += 1
            except ValueError:
                continue
    recent_predictions = list(reversed(history[-RECENT_PREDICTIONS:]))
    for item in recent_predictions:
        item['prediction_label'] = item.get('prediction_label', 'Unknown')
        item['risk_level'] = RISK_MAPPING.get(item.get('prediction'), {}).get('level', 'Unknown')
        try:
            latitude = float(item.get('latitude', 0))
            longitude = float(item.get('longitude', 0))
            item['location'] = f"{latitude:.2f}, {longitude:.2f}"
        except (ValueError, TypeError):
            item['location'] = 'Unknown'
        if item.get('prediction') == 2:
            item['prediction_name'] = 'Flood Likely'
        elif item.get('prediction') == 1:
            item['prediction_name'] = 'Flood Possible'
        else:
            item['prediction_name'] = 'No Flood'
    return {
        'total_predictions': total_predictions, 'safe_cases': safe_cases,
        'flood_cases': flood_cases, 'todays_predictions': todays_predictions,
        'accuracy': f"{round(MODEL_ACCURACY, 1)}%", 'recent_predictions': recent_predictions,
        'all_predictions': list(reversed(history))
    }

@app.context_processor
def inject_user_context():
    return {'current_user': get_current_user(), 'is_admin': is_admin()}

@app.route("/")
def home():
    if is_authenticated():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_authenticated():
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            error = 'Username and password are required.'
        elif AUTH_USERS.get(username) != password:
            error = 'Invalid username or password.'
        else:
            session['authenticated'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
    return render_template('login.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if is_authenticated():
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()
        if not username or not password or not confirm:
            error = 'All fields are required.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif username in AUTH_USERS:
            error = 'Username is already taken.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'
        else:
            AUTH_USERS[username] = password
            save_users({k: v for k, v in AUTH_USERS.items()})
            session['authenticated'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    stats = collect_dashboard_stats()
    return render_template('dashboard.html', **stats)

@app.route("/predict", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per minute")
def predict():
    if request.method == "GET":
        return render_template("predict.html", features=FEATURES, feature_labels=FEATURE_LABELS)
    try:
        if model is None or scaler is None:
            return render_template("error.html", error="Model not loaded"), 500
        input_dict, input_data, error = {}, [], None
        for feature in FEATURES:
            value_str = request.form.get(feature, '')
            if not value_str:
                return render_template("error.html", error=f"Missing value for {FEATURE_LABELS[feature]}"), 400
            is_valid, result = validate_input(feature, value_str)
            if not is_valid:
                return render_template("error.html", error=result), 400
            input_dict[feature] = result
            input_data.append(result)
        final_input = scaler.transform([input_data])
        prediction = int(model.predict(final_input)[0])
        raw_probability = model.predict_proba(final_input)[0]
        prob_dict = {0: 0.0, 1: 0.0, 2: 0.0}
        for idx, cls in enumerate(model.classes_):
            prob_dict[int(cls)] = float(raw_probability[idx])
        probability = [prob_dict[0], prob_dict[1], prob_dict[2]]
        logger.info(f"Web Prediction: Risk={RISK_MAPPING[prediction]['label']}")
        timestamp = datetime.now().isoformat()
        try:
            file_exists = os.path.isfile(PREDICTIONS_CSV)
            with open(PREDICTIONS_CSV, 'a', newline='') as csvfile:
                fieldnames = FEATURES + ['prediction', 'prediction_label', 'timestamp']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                row_data = input_dict.copy()
                row_data['prediction'] = prediction
                row_data['prediction_label'] = RISK_MAPPING[prediction]['label']
                row_data['timestamp'] = timestamp
                writer.writerow(row_data)
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
        risk_info = RISK_MAPPING[prediction]
        return render_template("result.html", prediction=prediction, risk_label=risk_info["label"],
                             risk_icon=risk_info["icon"], risk_color=risk_info["color"],
                             risk_level=risk_info["level"], probability=probability,
                             recommendations=risk_info["recommendations"], **{k: round(v, 2) if isinstance(v, float) else int(v) if isinstance(v, int) else v for k, v in input_dict.items()})
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        return render_template("error.html", error=f"An error occurred: {str(e)}"), 500

@app.route("/api/predict", methods=["POST"])
@limiter.limit("60 per minute")
def api_predict():
    try:
        if model is None or scaler is None:
            return jsonify({"error": "Model not loaded"}), 500
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        is_valid, message = validate_all_inputs(data)
        if not is_valid:
            return jsonify({"error": message}), 400
        input_data = [float(data[feature]) for feature in FEATURES]
        final_input = scaler.transform([input_data])
        prediction = int(model.predict(final_input)[0])
        raw_probability = model.predict_proba(final_input)[0]
        prob_dict = {0: 0.0, 1: 0.0, 2: 0.0}
        for idx, cls in enumerate(model.classes_):
            prob_dict[int(cls)] = float(raw_probability[idx])
        probability = [prob_dict[0], prob_dict[1], prob_dict[2]]
        logger.info(f"API Prediction: Risk={RISK_MAPPING[prediction]['label']}")
        risk_info = RISK_MAPPING[prediction]
        prediction_str = "LOW" if prediction == 0 else "MEDIUM" if prediction == 1 else "HIGH"
        confidence = float(probability[prediction])
        risk_score = float(probability[1] * 50 + probability[2] * 100)
        return jsonify({
            "success": True, "prediction": prediction_str, "prediction_int": prediction,
            "risk_label": risk_info["label"], "risk_level": risk_info["level"],
            "riskScore": round(risk_score, 2), "confidence": round(confidence, 4),
            "probability": {"low": round(probability[0], 4), "medium": round(probability[1], 4), "high": round(probability[2], 4)},
            "recommendations": risk_info["recommendations"], "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({"error": str(e)}), 400

@app.route("/api/status")
def status():
    return jsonify({
        "status": "running", "model_loaded": model is not None,
        "timestamp": datetime.now().isoformat(), "version": "1.0.0"
    })

@app.route("/api/features")
def features():
    features_info = []
    for feature in FEATURES:
        min_val, max_val = FEATURE_RANGES[feature]
        features_info.append({"name": feature, "label": FEATURE_LABELS[feature], "min": min_val, "max": max_val})
    return jsonify({"features": features_info})

@app.errorhandler(404)
def not_found(e):
    logger.warning(f"404 Not Found: {request.path}")
    return render_template("error.html", error="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 Server Error: {str(e)}")
    return render_template("error.html", error="Internal server error"), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    logger.warning(f"Rate limit exceeded: {request.remote_addr}")
    return render_template("error.html", error="Too many requests. Please try again later."), 429

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info("=" * 50)
    logger.info("🚀 Flood Prediction System Starting")
    logger.info("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)