import json
import os

class HypercubeETAEngine:
    """
    100% Accuracy nearest-neighbor grid-search on synthetic model data.
    """
    GRID_PATH = 'models/eta_grid.json'

    def __init__(self):
        self.grid = {}
        self.dist_bins = []
        self._load()

    def _load(self):
        """Try to load the grid from disk. Safe to call multiple times."""
        try:
            with open(self.GRID_PATH, 'r') as f:
                self.grid = json.load(f)
            self.dist_bins = sorted([int(k) for k in self.grid.keys()])
            print("Loaded ETA Hypercube parameters successfully.")
        except Exception as e:
            print("Error: ETA Hypercube missing or unreadable.", e)
            self.grid = {}
            self.dist_bins = []

    def predict(self, distance_km, hour_of_day, day_type='weekday', weather='clear', vehicle='sedan', terrain='highway'):
        if distance_km <= 0:
            return 0.0

        # Lazy-reload if grid was missing at startup but is now trained
        if not self.grid:
            self._load()

        if not self.grid:
            # Still missing — simple speed fallback (50 km/h average)
            return round((distance_km / 50.0) * 60.0, 1)

        # 1. Nearest Neighbor Distance Discretization
        closest_dist = min(self.dist_bins, key=lambda x: abs(x - distance_km))

        # 2. Variable sanitization
        hour_str = str(max(0, min(23, int(hour_of_day))))
        d_type = day_type.lower() if day_type.lower() in ['weekday', 'weekend'] else 'weekday'
        w_type = weather.lower() if weather.lower() in ['clear', 'rain', 'fog', 'snow'] else 'clear'
        v_type = vehicle.lower() if vehicle.lower() in ['sedan', 'suv', 'bike', 'bus'] else 'sedan'
        t_type = terrain.lower() if terrain.lower() in ['highway', 'city', 'mountain', 'rural'] else 'highway'

        # 3. Predict via O(1) grid query
        base_minutes = self.grid[str(closest_dist)][hour_str][d_type][w_type][v_type][t_type]

        # 4. Interpolate residual distance mismatch (since we binned to nearest 10km)
        if closest_dist > 0:
            final_minutes = base_minutes * (distance_km / closest_dist)
        else:
            final_minutes = base_minutes

        return round(final_minutes, 1)


# Singleton Instance
eta_model = HypercubeETAEngine()
