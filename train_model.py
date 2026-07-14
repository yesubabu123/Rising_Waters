import os
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# 1. Simple training data (Rainfall, River Level, Temperature)
X = np.array([
    [120, 5.5, 24],  # Flood
    [10, 1.2, 30],   # No Flood
    [150, 6.2, 22],  # Flood
    [5, 0.8, 28],    # No Flood
    [90, 4.1, 25],   # Flood
    [2, 0.5, 32]     # No Flood
])

# Labels: 1 = Flood, 0 = No Flood
y = np.array([1, 0, 1, 0, 1, 0])

print("🤖 Training the flood prediction model...")

# 2. Train the model
model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(X, y)

# 3. Create the 'models' directory if it doesn't exist
os.makedirs("models", exist_ok=True)

# 4. Save the model directly to models/flood_model.pkl
model_path = os.path.join("models", "flood_model.pkl")
with open(model_path, "wb") as f:
    pickle.dump(model, f)

print("✅ Success! Your new 'flood_model.pkl' has been created inside the 'models' folder.")