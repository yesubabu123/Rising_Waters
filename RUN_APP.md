# Running the Rising_water App (consolidated)

This document explains how to run the full Rising_water project (frontend, backend, Flask app, and Streamlit UI) on Windows.

Quick run (PowerShell):

1. Open PowerShell and navigate to the project root:

```powershell
cd C:\Users\matla\Downloads\Rising_water
```

2. Run the helper script to start everything (opens new windows for each service):

```powershell
.\start_all.ps1
```

What the script does:
- Creates a Python virtual environment (`venv`) and installs `requirements.txt` if missing.
- Starts the Flask web app (`app.py`) on port 5000.
- Starts the Node backend in `backend/` on port 5001 (to avoid port conflict).
- Starts the React frontend in `frontend/` (usually on port 3000).
- Starts the Streamlit app on port 8501.

Manual commands (if you prefer to run services separately):

- Python environment + Flask:

```powershell
cd C:\Users\matla\Downloads\Rising_water
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

- Node backend (use port 5001):

```powershell
cd C:\Users\matla\Downloads\Rising_water\backend
$env:PORT=5001
npm start
```

- React frontend:

```powershell
cd C:\Users\matla\Downloads\Rising_water\frontend
npm install     # if not already done
npm start
```

- Streamlit:

```powershell
cd C:\Users\matla\Downloads\Rising_water
venv\Scripts\activate
streamlit run streamlit_app.py
```

Useful URLs after services start:
- Frontend React: http://127.0.0.1:3000
- Flask app (web UI): http://127.0.0.1:5000
- Node backend API: http://127.0.0.1:5001
- Streamlit UI: http://127.0.0.1:8501

Troubleshooting:
- If a port is already in use, change the port in `start_all.ps1` or set the environment variable before starting.
- Check logs in each window for errors; model files exist at `models/flood_model.pkl` and `models/scaler.pkl`.

Map disabled by default:
- The map is disabled by default now to avoid performance issues. The dashboard will show simple latitude/longitude inputs instead of the interactive map.
- To enable the map, set `ENABLE_MAP=1` before starting Flask (requires network access and may be slower).

PowerShell example to enable map:
```powershell
$env:ENABLE_MAP = '1'
$env:GOOGLE_MAPS_API_KEY = 'YOUR_KEY'  # optional for autocomplete
python app.py
```
