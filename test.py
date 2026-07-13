import numpy as np
import pickle

model = pickle.load(open("models/flood_model.pkl", "rb"))
scaler = pickle.load(open("models/scaler.pkl", "rb"))

def predict():
    sample = np.array([[13.08, 79.96, 1200, 30, 80, 500, 3.5, 50, 1000, 2, 1, 70, 800]])

    scaled = scaler.transform(sample)
    result = model.predict(scaled)

    print("Prediction:", "FLOOD RISK ⚠" if result[0] == 1 else "SAFE ✅")

predict()