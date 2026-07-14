Deploying to Render

1. Push your repository to GitHub (or connect your Git provider).

2. On Render (https://render.com), create a new Web Service and connect your repo.

3. Use these settings:
   - Environment: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT -w 4`
   - Port: leave unset (Render provides `$PORT`) or set env var `PORT=10000` if needed.

4. Add environment variables (Dashboard → Environment):
   - `MONGO_URI` (optional) — your MongoDB connection string.

5. Deploy. The app will be available at the Render URL.

Notes:
- Ensure `models/flood_model.pkl` and `models/scaler.pkl` are present in the repo or accessible during runtime.
- If you rely on `predictions_history.csv`, commit it or use MongoDB for persistence.
