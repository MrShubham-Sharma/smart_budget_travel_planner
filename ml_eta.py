import math
from datetime import datetime

def euclidean_distance(p1, p2):
    return math.sqrt(sum((a - b)**2 for a, b in zip(p1, p2)))

class MLEtaPredictor:
    def __init__(self, k=3):
        self.k = k
        self.data_X = []
        self.data_y = [] # duration in minutes
        self._load_synthetic_data()

    def _load_synthetic_data(self):
        # Synthetic data: [distance_km, hour_of_day_0_24, transport_mode]
        # Transport mode mapping: 1=driving, 2=walking
        # Example: Driving 10km at 8am (rush hour) takes longer than at 2am.
        synthetic_records = [
            # Driving rush hour
            ([10, 8, 1], 45), ([10, 17, 1], 50), ([20, 8, 1], 80), ([20, 17, 1], 85),
            # Driving normal hours
            ([10, 14, 1], 25), ([10, 2, 1], 15), ([20, 14, 1], 45), ([20, 2, 1], 30),
            ([5, 12, 1], 15), ([50, 10, 1], 60), ([100, 11, 1], 100),
            
            # Walking (Time of day negligible impact)
            ([1, 10, 2], 12), ([1, 2, 2], 12), ([5, 14, 2], 60), ([5, 8, 2], 65),
            ([10, 15, 2], 130), ([2, 10, 2], 25), ([2, 17, 2], 25),
        ]
        for features, duration in synthetic_records:
            self.data_X.append(features)
            self.data_y.append(duration)

    def predict_duration(self, distance_km, hour_of_day, mode_str):
        # Map inputs to feature list
        mode_val = 1 if mode_str == "driving" else 2
        input_features = [distance_km, hour_of_day, mode_val]

        distances = []
        for i, features in enumerate(self.data_X):
            # Give much higher weight to transport mode and distance than hour
            weighted_features = [features[0]*5, features[1], features[2]*50]
            weighted_inputs = [input_features[0]*5, input_features[1], input_features[2]*50]
            dist = euclidean_distance(weighted_inputs, weighted_features)
            distances.append((dist, self.data_y[i]))

        distances.sort(key=lambda x: x[0])
        neighbors = distances[:self.k]
        
        avg_duration = sum(neighbor[1] for neighbor in neighbors) / self.k
        return round(avg_duration)

eta_model = MLEtaPredictor(k=3)

if __name__ == "__main__":
    print("Testing ML ETA Predictor...")
    dur1 = eta_model.predict_duration(10, 8, "driving")
    dur2 = eta_model.predict_duration(10, 2, "driving")
    dur3 = eta_model.predict_duration(5, 12, "walking")
    print(f"10km Drive at 8 AM: {dur1} mins")
    print(f"10km Drive at 2 AM: {dur2} mins")
    print(f"5km Walk at Noon: {dur3} mins")
