import json

# All stay types the model knows about (must match train_models.py)
VALID_STAY_TYPES = [
    'hostel', 'camping', 'dharamshala', 'ashram', 'guesthouse',
    'budget_hotel', 'homestay', 'heritage_hotel', '3star_hotel',
    'resort', '5star_hotel', 'houseboat', 'treehouse',
    'desert_camp', 'tent_resort',
]

# All food types (must match train_models.py FOOD_DAILY_COST)
VALID_FOOD_TYPES = [
    'veg_thali', 'nonveg_thali', 'local_cuisine',
    'dhaba', 'restaurant', 'hotel_buffet',
]

STAY_NIGHTLY_BASE = {
    'hostel':        500,    'camping':       700,
    'dharamshala':   300,    'ashram':        250,
    'guesthouse':    1100,   'budget_hotel':  1400,
    'homestay':      1600,   'heritage_hotel':3000,
    '3star_hotel':   2800,   'resort':        5500,
    '5star_hotel':   11000,  'houseboat':     7000,
    'treehouse':     4500,   'desert_camp':   4000,
    'tent_resort':   3500,
}

FOOD_DAILY_COST = {
    'veg_thali':    300,   'nonveg_thali': 450,
    'local_cuisine':600,   'dhaba':        250,
    'restaurant':   900,   'hotel_buffet': 1600,
}

TRANSPORT_DAILY_PP = {
    'budget':    350,   
    'mid-range': 700,   
    'mid':       700,
    'luxury':   2500,   
}

import pandas as pd
import joblib

class HypercubeBudgetEngine:
    """
    N-Dimensional Budget Hypercube Inference Engine (v2) - True Scikit-Learn Model.
    Dynamically predicts using RandomForestRegressor rather than hardcoded logic.
    """
    MODEL_PATH = 'models/budget_rf.pkl'

    def __init__(self):
        self.pipeline = None
        self._load()

    def _load(self):
        try:
            self.pipeline = joblib.load(self.MODEL_PATH)
            print("Loaded True ML Budget RandomForest Model successfully.")
        except Exception as e:
            print("Warning: Budget ML model not found or incomplete. Run train_models.py first.", e)
            self.pipeline = None

    def predict(self, days, travel_style="mid", food_type="casual",
                group_size=1, season="shoulder", booking="normal",
                stay_type="budget_hotel"):
        if days <= 0:
            return 0.0
            
        grp = min(20, max(1, int(group_size)))

        # Fallback dictionary matching aliases
        VALID_FOOD_TYPES = ['veg_thali', 'nonveg_thali', 'local_cuisine', 'dhaba', 'restaurant', 'hotel_buffet']
        VALID_STAY_TYPES = ['hostel', 'camping', 'dharamshala', 'ashram', 'guesthouse', 'budget_hotel', 'homestay', 'heritage_hotel', '3star_hotel', 'resort', '5star_hotel', 'houseboat', 'treehouse', 'desert_camp', 'tent_resort']

        style = travel_style.lower()
        if style not in ['budget', 'mid-range', 'mid', 'luxury']:
            style = 'mid'

        food = food_type.lower()
        if food not in VALID_FOOD_TYPES:
            _food_aliases = {
                'street': 'dhaba', 'casual': 'local_cuisine', 'fine': 'restaurant',
                'veg': 'veg_thali', 'nonveg': 'nonveg_thali', 'non-veg': 'nonveg_thali',
                'buffet': 'hotel_buffet', 'thali': 'veg_thali',
            }
            food = _food_aliases.get(food, 'local_cuisine')

        s = season.lower()
        if s not in ['peak', 'off-peak', 'shoulder', 'holiday']:
            s = 'shoulder'

        b = booking.lower()
        if b not in ['last-minute', 'normal', 'advance']:
            b = 'normal'

        st = stay_type.lower().strip()
        if st not in VALID_STAY_TYPES:
            _aliases = {
                'budget': 'budget_hotel', 'mid': '3star_hotel',
                'luxury': '5star_hotel', 'hotel': 'budget_hotel',
                'camp': 'camping',
            }
            st = _aliases.get(st, 'budget_hotel')

        # If pipeline not ready, return fallback math
        if not self.pipeline:
            self._load()
        if not self.pipeline:
            return round(1500 * days * grp, 2)

        # Prepare DataFrame to match the training pipeline schema
        df = pd.DataFrame([{
            'days': days,
            'group_size': grp,
            'travel_style': style,
            'food_type': food,
            'season': s,
            'booking': b,
            'stay_type': st
        }])
        
        # Real ML prediction (uses RandomForest + Pipeline logic)
        predicted_budget = float(self.pipeline.predict(df)[0])
        return round(predicted_budget, 2)

# Singleton instance
budget_model = HypercubeBudgetEngine()
