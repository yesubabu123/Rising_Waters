import os
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# Define the exact custom class your app.py is looking for
class IdentityScaler:
    def fit(self, X, y=None):
        return self
    def transform(self, X):
        return X
    def fit_transform(self, X, y=None):
        return X

# 1. Dummy training data
X = np.array([
    [120, 5.5, 24],
    [10, 1.2, 30],
    [150, 6.2, 22],
    [5, 0.8, 28],
    [90, 4.1, 25],
    [2, 0.5, 32]
])

y = np.array([1, 0, 1, 0, 1, 0])

print("🤖 Training the model with IdentityScaler tracking...")

# 2. Initialize the matching custom scaler
scaler = IdentityScaler()
X_scaled = scaler.fit_transform(X)

# 3. Train the classifier
model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(X_scaled, y)

# 4. Make sure directory exists
os.makedirs("models", exist_ok=True)

# 5. Save the generated files
with open(os.path.join("models", "flood_model.pkl"), "wb") as f:
    pickle.dump(model, f)

with open(os.path.join("models", "scaler.pkl"), "wb") as f:
    pickle.dump(scaler, f)

print("✅ Success! Fixed scaler.pkl generated for IdentityScaler alignment.")