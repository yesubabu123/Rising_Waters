from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import pickle
import numpy as np
import json
from datetime import datetime, timedelta
import logging
import os
from functools import wraps
import csv
import threading
import webbrowser
from pymongo import MongoClient

# ==============================
# FLASK APP INITIALIZATION
# ==============================
app = Flask(__name__)
CORS(app)

# Rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# ==============================
# CONFIGURATION
# ==============================
app.config['JSON_SORT_KEYS'] = False
LOG_FILE = 'flood_predictions.log'
PREDICTIONS_CSV = 'predictions_history.csv'

# ==============================
# LOGGING SETUP
# ==============================
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

logger = logging.getLogger(__name__)

# ==============================
# LOAD MODEL + SCALER
# ==============================
try:
    model = pickle.load(open("models/flood_model.pkl", "rb"))
    scaler = pickle.load(open("models/scaler.pkl", "rb"))
    logger.info("✅ Model and Scaler loaded successfully!")
except Exception as e:
    logger.error(f"❌ Error loading model: {str(e)}")
    model = None
    scaler = None

# ==============================
# MONGODB CONFIGURATION
# ==============================
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

# ==============================
# FEATURE CONFIGURATION
# ==============================
FEATURES = [
    "latitude",
    "longitude",
    "annual_rainfall",
    "temperature",
    "humidity",
    "river_discharge",
    "water_level",
    "elevation",
    "population_density",
    "infrastructure",
    "historical_floods",
    "cloud_visibility",
    "seasonal_rainfall"
]

FEATURE_LABELS = {
    "latitude": "Latitude (°)",
    "longitude": "Longitude (°)",
    "annual_rainfall": "Annual Rainfall (mm)",
    "temperature": "Temperature (°C)",
    "humidity": "Humidity (%)",
    "river_discharge": "River Discharge (m³/s)",
    "water_level": "Water Level (m)",
    "elevation": "Elevation (m)",
    "population_density": "Population Density (per km²)",
    "infrastructure": "Infrastructure Index",
    "historical_floods": "Historical Floods (count)",
    "cloud_visibility": "Cloud Visibility (%)",
    "seasonal_rainfall": "Seasonal Rainfall (mm)"
}

FEATURE_RANGES = {
    "latitude": (-90, 90),
    "longitude": (-180, 180),
    "annual_rainfall": (0, 12000),
    "temperature": (-50, 60),
    "humidity": (0, 100),
    "river_discharge": (0, 50000),
    "water_level": (-50, 50),
    "elevation": (-500, 9000),
    "population_density": (0, 100000),
    "infrastructure": (0, 1),
    "historical_floods": (0, 1000),
    "cloud_visibility": (0, 100),
    "seasonal_rainfall": (0, 5000)
}

# How many recent predictions to show in the dashboard
RECENT_PREDICTIONS = int(os.environ.get('RECENT_PREDICTIONS', 10))

# Authentication configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change_this_secret_key')
USERS_FILE = 'users.json'
ADMIN_USERNAME = os.environ.get('APP_AUTH_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('APP_AUTH_PASS', 'admin123')
AUTH_USERS = {
    ADMIN_USERNAME: ADMIN_PASSWORD
}


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


# Load persisted users into AUTH_USERS
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

# Risk prediction mapping with recommendations
RISK_MAPPING = {
    0: {
        "label": "LOW RISK",
        "icon": "✅",
        "color": "success",
        "level": "Low",
        "recommendations": [
            "Area is generally safe from flooding",
            "Continue regular monitoring of weather",
            "Maintain emergency preparedness",
            "Keep drainage systems clear",
            "Update flood insurance annually"
        ]
    },
    1: {
        "label": "MEDIUM RISK",
        "icon": "⚠️",
        "color": "warning",
        "level": "Medium",
        "recommendations": [
            "Monitor weather forecasts closely",
            "Prepare emergency supplies (water, food, first aid)",
            "Ensure drainage systems are clear",
            "Have evacuation plan ready for family",
            "Keep sandbags and barriers accessible",
            "Inform family members of flood risk",
            "Move valuable items to higher floors",
            "Review flood insurance coverage"
        ]
    },
    2: {
        "label": "HIGH RISK",
        "icon": "🚨",
        "color": "danger",
        "level": "High",
        "recommendations": [
            "IMMEDIATE ALERT: Flood risk is critical",
            "EVACUATE IF NECESSARY: Follow local authorities",
            "Move to higher ground immediately",
            "Contact emergency services if needed (Emergency: 911)",
            "Keep emergency supplies accessible",
            "Do not attempt to drive through flooded areas",
            "Listen to local news for updates",
            "Stay in contact with family members",
            "Unplug electrical appliances before evacuation",
            "Turn off gas supply if instructed"
        ]
    }
}

MODEL_ACCURACY = 100.0


def load_history_from_csv():
    history = []
    if not os.path.isfile(PREDICTIONS_CSV):
        return history

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


def load_history_from_mongo():
    history = []
    if mongo_collection is None:
        return history

    try:
        for doc in mongo_collection.find().sort('timestamp', 1):
            history.append({
                'latitude': doc.get('latitude'),
                'longitude': doc.get('longitude'),
                'annual_rainfall': doc.get('rainfall'),
                'temperature': doc.get('temperature'),
                'humidity': doc.get('humidity'),
                'river_discharge': doc.get('river_discharge'),
                'water_level': doc.get('water_level'),
                'elevation': doc.get('elevation'),
                'population_density': doc.get('population_density'),
                'infrastructure': doc.get('infrastructure'),
                'historical_floods': doc.get('historical_floods'),
                'cloud_visibility': doc.get('cloud_visibility'),
                'seasonal_rainfall': doc.get('seasonal_rainfall'),
                'prediction_int': int(doc.get('prediction_int', -1)),
                'prediction': int(doc.get('prediction_int', -1)),
                'prediction_label': doc.get('prediction_label', doc.get('prediction', 'Unknown')),
                'timestamp': doc.get('timestamp', ''),
                'risk_level': doc.get('risk', 'Unknown')
            })
    except Exception as e:
        logger.error(f"Error loading history from MongoDB: {e}")

    return history


def load_history():
    history = []
    if mongo_collection is not None:
        history = load_history_from_mongo()
        if history:
            return history

    return load_history_from_csv()


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
        'total_predictions': total_predictions,
        'safe_cases': safe_cases,
        'flood_cases': flood_cases,
        'todays_predictions': todays_predictions,
        'accuracy': f"{round(MODEL_ACCURACY, 1)}%",
        'recent_predictions': recent_predictions,
        'all_predictions': list(reversed(history))
    }


@app.context_processor
def inject_user_context():
    return {
        'current_user': get_current_user(),
        'is_admin': is_admin()
    }

# ==============================
# VALIDATION FUNCTIONS
# ==============================
def validate_input(feature, value):
    """Validate individual feature value"""
    try:
        value = float(value)
        min_val, max_val = FEATURE_RANGES[feature]
        
        if value < min_val or value > max_val:
            return False, f"{FEATURE_LABELS[feature]} must be between {min_val} and {max_val}"
        return True, value
    except ValueError:
        return False, f"Invalid value for {FEATURE_LABELS[feature]}"

def validate_all_inputs(data_dict):
    """Validate all input features"""
    for feature in FEATURES:
        if feature not in data_dict:
            return False, f"Missing feature: {FEATURE_LABELS[feature]}"
        
        is_valid, result = validate_input(feature, data_dict[feature])
        if not is_valid:
            return False, result
    
    return True, "All inputs valid"

# ==============================
# CHATBOT RESPONSES
# ==============================

def generate_chat_response(user_message):
    """Generate simple app-related chatbot responses."""
    message = str(user_message).strip().lower()
    if not message:
        return "Please ask a question about flood risk or the prediction dashboard."

    if any(keyword in message for keyword in ["input", "feature", "data", "value"]):
        return (
            "This app predicts flood risk using location, weather, water, terrain, infrastructure, "
            "and historical flood data. Fill in the form fields and click Predict to get a recommendation."
        )

    if any(keyword in message for keyword in ["risk", "high", "medium", "low", "danger", "safe"]):
        return (
            "The model returns Low, Medium, or High flood risk. High means urgent preparedness, Medium means "
            "you should monitor conditions and prepare supplies, and Low means lower flood risk."
        )

    if any(keyword in message for keyword in ["model", "accuracy", "predict", "machine", "learning"]):
        return (
            "The app uses a trained machine learning model to estimate flood risk from environmental features. "
            "It returns a risk level and confidence for your input values."
        )

    if any(keyword in message for keyword in ["recommend", "prepare", "action", "what should i do"]):
        return (
            "If flood risk is high, move to higher ground, follow local authority instructions, and keep emergency supplies ready. "
            "For medium risk, stay alert and keep your drainage paths clear."
        )

    if any(keyword in message for keyword in ["history", "dashboard", "recent", "prediction history"]):
        return (
            "The dashboard shows total predictions, flood cases, safe cases, and the most recent prediction history. "
            "Use the dashboard to review recent risk assessments and compare the current prediction."
        )

    if any(keyword in message for keyword in ["how", "what", "why", "where"]):
        return (
            "Ask me about how to use the flood prediction form, what each feature means, or how to interpret the risk levels. "
            "I can help explain the app and how to use it."
        )

    return (
        "I can help with flood risk predictions, input feature meanings, and dashboard usage. "
        "Ask a question like 'How do I use the prediction form?' or 'What does high risk mean?'."
    )

# ==============================
# PREDICTION LOGGING
# ==============================
def save_prediction(input_dict, prediction, probability):
    """Save prediction to CSV for analytics and MongoDB for persistence"""
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
        logger.error(f"Error saving prediction to CSV: {str(e)}")

    try:
        save_prediction_to_mongo(input_dict, prediction, probability, timestamp)
    except Exception as e:
        logger.error(f"Error saving prediction to MongoDB: {str(e)}")


def save_prediction_to_mongo(input_dict, prediction, probability, timestamp):
    """Save prediction document to MongoDB collection."""
    if mongo_collection is None:
        raise RuntimeError('MongoDB collection not initialized')

    document = {
        'latitude': float(input_dict['latitude']),
        'longitude': float(input_dict['longitude']),
        'rainfall': float(input_dict['annual_rainfall']),
        'temperature': float(input_dict['temperature']),
        'humidity': float(input_dict['humidity']),
        'river_discharge': float(input_dict['river_discharge']),
        'water_level': float(input_dict['water_level']),
        'elevation': float(input_dict['elevation']),
        'population_density': float(input_dict['population_density']),
        'infrastructure': float(input_dict['infrastructure']),
        'historical_floods': float(input_dict['historical_floods']),
        'cloud_visibility': float(input_dict['cloud_visibility']),
        'seasonal_rainfall': float(input_dict['seasonal_rainfall']),
        'prediction_int': int(prediction),
        'prediction_label': RISK_MAPPING[prediction]['label'],
        'prediction': RISK_MAPPING[prediction]['label'],
        'risk': RISK_MAPPING[prediction]['level'],
        'probability': probability,
        'date': timestamp.split('T')[0],
        'timestamp': timestamp
    }

    mongo_collection.insert_one(document)

# ==============================
# HOME PAGE / LOGIN REDIRECT
# ==============================
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
            save_users({k: v for k, v in AUTH_USERS.items() if k != os.environ.get('APP_AUTH_USER', 'admin') or v != os.environ.get('APP_AUTH_PASS', 'admin123')})
            session['authenticated'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))

    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not is_admin():
        return render_template('error.html', error='Admin access required'), 403

    stats = collect_dashboard_stats()
    message = None

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create_user':
            username = request.form.get('new_username', '').strip()
            password = request.form.get('new_password', '').strip()
            if not username or not password:
                message = 'Please provide both username and password.'
            elif username in AUTH_USERS:
                message = 'This username already exists.'
            else:
                AUTH_USERS[username] = password
                save_users({k: v for k, v in AUTH_USERS.items() if k != ADMIN_USERNAME or v != ADMIN_PASSWORD})
                message = f'User {username} created successfully.'
        elif action == 'delete_user':
            username = request.form.get('delete_username')
            if username == ADMIN_USERNAME:
                message = 'Cannot delete admin user.'
            elif username in AUTH_USERS:
                AUTH_USERS.pop(username, None)
                save_users({k: v for k, v in AUTH_USERS.items() if k != ADMIN_USERNAME or v != ADMIN_PASSWORD})
                message = f'User {username} deleted successfully.'
            else:
                message = 'User not found.'

    users = [
        {'username': uname, 'is_admin': uname == ADMIN_USERNAME}
        for uname in sorted(AUTH_USERS)
    ]

    return render_template(
        'admin.html',
        all_predictions=stats['all_predictions'],
        users=users,
        message=message,
        total_predictions=stats['total_predictions'],
        flood_cases=stats['flood_cases'],
        safe_cases=stats['safe_cases'],
        todays_predictions=stats['todays_predictions'],
        accuracy=stats['accuracy']
    )


@app.route('/admin/export')
@login_required
def admin_export():
    if not is_admin():
        return render_template('error.html', error='Admin access required'), 403
    if not os.path.isfile(PREDICTIONS_CSV):
        return render_template('error.html', error='No predictions available to export.'), 404
    return send_from_directory(
        directory=os.getcwd(),
        filename=PREDICTIONS_CSV,
        as_attachment=True
    )


@app.route('/dashboard')
@login_required
def dashboard():
    stats = collect_dashboard_stats()
    return render_template(
        'dashboard.html',
        total_predictions=stats['total_predictions'],
        flood_cases=stats['flood_cases'],
        safe_cases=stats['safe_cases'],
        todays_predictions=stats['todays_predictions'],
        accuracy=stats['accuracy'],
        recent_predictions=stats['recent_predictions'],
        recent_count=RECENT_PREDICTIONS,
        google_api_key=os.environ.get('GOOGLE_MAPS_API_KEY', ''),
        enable_map=os.environ.get('ENABLE_MAP', '0') in ('1', 'true', 'True')
    )


# ==============================
# PREDICTION ROUTE (WEB FORM)
# ==============================
@app.route("/predict", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def predict():
    """Process prediction from web form"""
    try:
        if model is None or scaler is None:
            logger.error("Model or scaler not loaded")
            return render_template(
                "error.html",
                error="Model not loaded. Please check server logs."
            ), 500

        # Collect and validate input
        input_dict = {}
        input_data = []
        
        for feature in FEATURES:
            value_str = request.form.get(feature, '')
            if not value_str:
                return render_template(
                    "error.html",
                    error=f"Missing value for {FEATURE_LABELS[feature]}"
                ), 400
            
            is_valid, result = validate_input(feature, value_str)
            if not is_valid:
                return render_template(
                    "error.html",
                    error=result
                ), 400
            
            input_dict[feature] = result
            input_data.append(result)

        # Make prediction
        final_input = scaler.transform([input_data])
        prediction = int(model.predict(final_input)[0])
        raw_probability = model.predict_proba(final_input)[0]
        
        prob_dict = {0: 0.0, 1: 0.0, 2: 0.0}
        for idx, cls in enumerate(model.classes_):
            prob_dict[int(cls)] = float(raw_probability[idx])
        probability = [prob_dict[0], prob_dict[1], prob_dict[2]]

        # Log prediction
        logger.info(f"Web Prediction: Risk={RISK_MAPPING[prediction]['label']}, "
                   f"Lat={input_dict['latitude']}, Lon={input_dict['longitude']}")
        
        # Save to CSV
        save_prediction(input_dict, prediction, probability)

        # Get risk info
        risk_info = RISK_MAPPING[prediction]

        # Render result
        return render_template(
            "result.html",
            prediction=prediction,
            risk_label=risk_info["label"],
            risk_icon=risk_info["icon"],
            risk_color=risk_info["color"],
            risk_level=risk_info["level"],
            probability=probability,
            recommendations=risk_info["recommendations"],
            latitude=round(input_dict["latitude"], 4),
            longitude=round(input_dict["longitude"], 4),
            annual_rainfall=round(input_dict["annual_rainfall"], 2),
            temperature=round(input_dict["temperature"], 2),
            humidity=round(input_dict["humidity"], 2),
            river_discharge=round(input_dict["river_discharge"], 2),
            water_level=round(input_dict["water_level"], 2),
            elevation=round(input_dict["elevation"], 2),
            population_density=round(input_dict["population_density"], 2),
            infrastructure=round(input_dict["infrastructure"], 2),
            historical_floods=int(input_dict["historical_floods"]),
            cloud_visibility=round(input_dict["cloud_visibility"], 2),
            seasonal_rainfall=round(input_dict["seasonal_rainfall"], 2)
        )

    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        return render_template(
            "error.html",
            error=f"An error occurred: {str(e)}"
        ), 500

# ==============================
# API ENDPOINT (JSON)
# ==============================
@app.route("/api/predict", methods=["POST"])
@limiter.limit("60 per minute")
def api_predict():
    """Process prediction from JSON API"""
    try:
        if model is None or scaler is None:
            return jsonify({"error": "Model not loaded"}), 500

        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # Validate all inputs
        is_valid, message = validate_all_inputs(data)
        if not is_valid:
            return jsonify({"error": message}), 400

        # Prepare input
        input_data = [float(data[feature]) for feature in FEATURES]
        input_dict = {feature: float(data[feature]) for feature in FEATURES}

        # Make prediction
        final_input = scaler.transform([input_data])
        prediction = int(model.predict(final_input)[0])
        raw_probability = model.predict_proba(final_input)[0]

        prob_dict = {0: 0.0, 1: 0.0, 2: 0.0}
        for idx, cls in enumerate(model.classes_):
            prob_dict[int(cls)] = float(raw_probability[idx])
        probability = [prob_dict[0], prob_dict[1], prob_dict[2]]

        # Log and save
        logger.info(f"API Prediction: Risk={RISK_MAPPING[prediction]['label']}")
        save_prediction(input_dict, prediction, probability)

        # Get risk info
        risk_info = RISK_MAPPING[prediction]

        # Map prediction integer to standard MERN string
        prediction_str = "LOW" if prediction == 0 else "MEDIUM" if prediction == 1 else "HIGH"
        confidence = float(probability[prediction])
        # Calculate risk score based on probability distribution
        risk_score = float(probability[1] * 50 + probability[2] * 100)

        return jsonify({
            "success": True,
            "prediction": prediction_str,
            "prediction_int": prediction,
            "risk_label": risk_info["label"],
            "risk_level": risk_info["level"],
            "riskScore": round(risk_score, 2),
            "confidence": round(confidence, 4),
            "probability": {
                "low": round(probability[0], 4),
                "medium": round(probability[1], 4),
                "high": round(probability[2], 4)
            },
            "recommendations": risk_info["recommendations"],
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({"error": str(e)}), 400

# ==============================
# BATCH PREDICTION API
# ==============================
@app.route("/api/batch-predict", methods=["POST"])
@limiter.limit("10 per minute")
def batch_predict():
    """Process multiple predictions at once"""
    try:
        if model is None or scaler is None:
            return jsonify({"error": "Model not loaded"}), 500

        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({"error": "Expected list of predictions"}), 400

        results = []
        for item in data:
            # Validate
            is_valid, message = validate_all_inputs(item)
            if not is_valid:
                results.append({"error": message})
                continue

            # Predict
            input_data = [float(item[feature]) for feature in FEATURES]
            final_input = scaler.transform([input_data])
            prediction = int(model.predict(final_input)[0])
            raw_probability = model.predict_proba(final_input)[0]
            
            prob_dict = {0: 0.0, 1: 0.0, 2: 0.0}
            for idx, cls in enumerate(model.classes_):
                prob_dict[int(cls)] = float(raw_probability[idx])
            probability = [prob_dict[0], prob_dict[1], prob_dict[2]]

            risk_info = RISK_MAPPING[prediction]
            results.append({
                "success": True,
                "prediction": prediction,
                "risk_label": risk_info["label"],
                "probability": probability
            })

        logger.info(f"Batch prediction: {len(results)} items processed")
        return jsonify({"results": results, "count": len(results)})

    except Exception as e:
        logger.error(f"Batch prediction error: {str(e)}")
        return jsonify({"error": str(e)}), 400

# ==============================
# API ENDPOINTS - INFO & STATUS
# ==============================
@app.route("/api/status")
def status():
    """Get server status"""
    return jsonify({
        "status": "running",
        "model_loaded": model is not None,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route("/api/model-info")
def model_info():
    """Get model details"""
    return jsonify({
        "name": "Flood Risk Prediction Model",
        "type": "Random Forest Classifier",
        "features": len(FEATURES),
        "accuracy": 1.0,
        "framework": "Scikit-learn"
    })

@app.route("/api/features")
def features():
    """Get feature information"""
    features_info = []
    for feature in FEATURES:
        min_val, max_val = FEATURE_RANGES[feature]
        features_info.append({
            "name": feature,
            "label": FEATURE_LABELS[feature],
            "min": min_val,
            "max": max_val
        })
    return jsonify({"features": features_info})

@app.route("/api/risk-levels")
def risk_levels():
    """Get risk level information"""
    return jsonify(RISK_MAPPING)

# ==============================
# PREDICTION HISTORY
# ==============================
@app.route("/api/history")
@limiter.limit("20 per minute")
def get_history():
    """Get recent predictions (last 100)"""
    try:
        predictions = []
        count = 0

        if mongo_collection is not None:
            docs = mongo_collection.find().sort('timestamp', -1).limit(100)
            for doc in docs:
                count += 1
                predictions.append({
                    'latitude': doc.get('latitude'),
                    'longitude': doc.get('longitude'),
                    'prediction_int': int(doc.get('prediction_int', -1)),
                    'prediction_label': doc.get('prediction_label', doc.get('prediction', 'Unknown')),
                    'risk_level': doc.get('risk', 'Unknown'),
                    'probability': doc.get('probability', {}),
                    'timestamp': doc.get('timestamp', '')
                })

            return jsonify({
                'predictions': predictions,
                'count': count,
                'source': 'mongodb'
            })

        if not os.path.isfile(PREDICTIONS_CSV):
            return jsonify({'predictions': [], 'count': 0, 'source': 'csv'})

        with open(PREDICTIONS_CSV, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = [row for row in reader]
            count = len(rows)
            predictions = list(reversed(rows[-100:]))

        return jsonify({
            'predictions': predictions,
            'count': count,
            'source': 'csv'
        })

    except Exception as e:
        logger.error(f"History retrieval error: {str(e)}")
        return jsonify({'error': str(e)}), 400

# ==============================
# STATIC FILES
# ==============================
@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per minute")
def api_chat():
    """Process simple chatbot messages for app guidance."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "No message provided."}), 400

        user_message = str(data.get('message', '')).strip()
        if not user_message:
            return jsonify({"error": "Please type a message."}), 400

        response = generate_chat_response(user_message)
        logger.info(f"Chat request: {user_message}")
        return jsonify({"success": True, "response": response})

    except Exception as e:
        logger.error(f"Chat API error: {str(e)}")
        return jsonify({"error": "Failed to process chat message."}), 500


@app.route("/logs")
def get_logs():
    """Get application logs (last 50 lines)"""
    try:
        if not os.path.isfile(LOG_FILE):
            return "No logs available"
        
        with open(LOG_FILE, 'r') as f:
            logs = f.readlines()[-50:]
        
        return '<br>'.join(logs), 200, {'Content-Type': 'text/html'}
    except Exception as e:
        return f"Error reading logs: {str(e)}", 500

# ==============================
# ERROR HANDLERS
# ==============================
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    logger.warning(f"404 Not Found: {request.path}")
    return render_template("error.html", error="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"500 Server Error: {str(e)}")
    return render_template("error.html", error="Internal server error"), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limiting"""
    logger.warning(f"Rate limit exceeded: {request.remote_addr}")
    return render_template("error.html", error="Too many requests. Please try again later."), 429

# ==============================
# RUN APP
# ==============================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 Flood Prediction System Starting")
    logger.info("=" * 50)
    app.run(debug=True, host="127.0.0.1", port=5000)