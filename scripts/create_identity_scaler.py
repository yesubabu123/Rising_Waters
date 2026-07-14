import os
import pickle

class IdentityScaler:
    def transform(self, X):
        return X

os.makedirs('models', exist_ok=True)
with open(os.path.join('models', 'scaler.pkl'), 'wb') as f:
    pickle.dump(IdentityScaler(), f)

print('Created models/scaler.pkl (IdentityScaler)')
