import json

# All stay types the model knows about (must match train_models.py)
VALID_STAY_TYPES = [
    'hostel', 'camping', 'friend_house', 'home', 'family_stay',
    'budget_hotel', '3star_hotel', 'resort', '5star_hotel',
    'dharamshala', 'ashram', 'guesthouse', 'homestay', 'heritage_hotel',
    'houseboat', 'treehouse', 'desert_camp', 'tent_resort'
]

# All food types (must match train_models.py FOOD_DAILY_COST)
VALID_FOOD_TYPES = [
    'veg_thali', 'nonveg_thali', 'local_cuisine',
    'dhaba', 'restaurant', 'hotel_buffet',
]

# Genuine Indian travel base costs (per person, per night/day)
STAY_NIGHTLY_BASE = {
    'hostel':        300,    'camping':       400,
    'friend_house':  0,      'home':          0,
    'family_stay':   0,      'budget_hotel':  700,
    '3star_hotel':   1800,   'resort':        3500,
    '5star_hotel':   6000,   'dharamshala':   150,
    'ashram':        200,    'guesthouse':    500,
    'homestay':      600,    'heritage_hotel': 2500,
    'houseboat':     2500,   'treehouse':     1800,
    'desert_camp':   1200,   'tent_resort':   1200
}

FOOD_DAILY_COST = {
    'veg_thali':    150,   'nonveg_thali': 220,
    'local_cuisine':300,   'dhaba':        120,
    'restaurant':   500,   'hotel_buffet': 900,
    'no_food':      0,
}

TRANSPORT_DAILY_PP = {
    'budget':    200,   
    'mid-range': 450,   
    'mid':       450,
    'luxury':   1200,   
}

# Destination cost multipliers — modest to avoid extreme inflation
DESTINATION_MULTIPLIERS = {
    'budget':   0.85,
    'standard': 1.0,
    'premium':  1.15,
    'luxury':   1.30   # Reduced from 1.6 — prevents Goa trips showing 1 lakh+
}

# Map common destinations to cost categories
DESTINATION_CATEGORIES = {
    # Luxury destinations
    'goa': 'luxury', 'kerala': 'luxury', 'shimla': 'luxury', 'manali': 'luxury', 
    'darjeeling': 'luxury', 'ooty': 'luxury', 'kodaikanal': 'luxury', 'nainital': 'luxury',
    'rishikesh': 'luxury', 'mussoorie': 'luxury', 'gangtok': 'luxury', 'coorg': 'luxury',
    'andaman': 'luxury', 'nicobar': 'luxury', 'lakshadweep': 'luxury', 'diu': 'luxury',
    'pondicherry': 'luxury', 'mahabaleshwar': 'luxury', 'lonavala': 'luxury', 'khandala': 'luxury',
    
    # Premium destinations  
    'jaipur': 'premium', 'udaipur': 'premium', 'jodhpur': 'premium', 'jaisalmer': 'premium',
    'agra': 'premium', 'varanasi': 'premium', 'khajuraho': 'premium', 'amritsar': 'premium',
    'pondicherry': 'premium', 'mysore': 'premium', 'hampi': 'premium', 'badami': 'premium',
    'alleppey': 'premium', 'munnar': 'premium', 'thekkady': 'premium', 'kochi': 'premium',
    'hyderabad': 'premium', 'bangalore': 'premium', 'chennai': 'premium', 'pune': 'premium',
    'ahmedabad': 'premium', 'surat': 'premium', 'vadodara': 'premium', 'rajkot': 'premium',
    
    # Standard destinations (default)
    'delhi': 'standard', 'mumbai': 'standard', 'bangalore': 'standard', 'chennai': 'standard',
    'kolkata': 'standard', 'hyderabad': 'standard', 'pune': 'standard', 'ahmedabad': 'standard',
    'surat': 'standard', 'kanpur': 'standard', 'nagpur': 'standard', 'lucknow': 'standard',
    'indore': 'standard', 'bhopal': 'standard', 'patna': 'standard', 'ranchi': 'standard',
    'raipur': 'standard', 'bhubaneswar': 'standard', 'chandigarh': 'standard', 'dehradun': 'standard',
    
    # Budget destinations
    'allahabad': 'budget', 'meerut': 'budget', 'faridabad': 'budget', 'ghaziabad': 'budget',
    'noida': 'budget', 'gurgaon': 'budget', 'gwalior': 'budget', 'jabalpur': 'budget',
    'vijayawada': 'budget', 'visakhapatnam': 'budget', 'coimbatore': 'budget', 'madurai': 'budget',
    'tiruchirappalli': 'budget', 'salem': 'budget', 'tirunelveli': 'budget'
}

import pandas as pd
import joblib
import warnings

# Suppress sklearn InconsistentVersionWarning from joblib loading
warnings.filterwarnings("ignore", category=UserWarning)
try:
    import sklearn
    warnings.filterwarnings("ignore", module="sklearn")
except Exception:
    pass

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
                stay_type="budget_hotel", is_family=False, destination=""):
        if days <= 0:
            return 0.0
            
        grp = min(20, max(1, int(group_size)))

        # Fallback dictionary matching aliases
        VALID_FOOD_TYPES = ['veg_thali', 'nonveg_thali', 'local_cuisine', 'dhaba', 'restaurant', 'hotel_buffet']
        VALID_STAY_TYPES = ['hostel', 'camping', 'dharamshala', 'ashram', 'guesthouse', 'budget_hotel', 'homestay', 'heritage_hotel', '3star_hotel', 'resort', '5star_hotel', 'houseboat', 'treehouse', 'desert_camp', 'tent_resort', 'friend_house', 'home', 'family_stay']

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
                'camp': 'camping', 'guesthouse': 'budget_hotel',
                'homestay': 'budget_hotel', 'friend': 'friend_house',
                'home': 'home', 'family': 'family_stay'
            }
            st = _aliases.get(st, 'budget_hotel')

        # Process destination for cost adjustment
        dest_multiplier = 1.0  # Default multiplier
        if destination:
            dest_lower = destination.lower().strip()
            # Extract city name (remove "India" or other suffixes)
            dest_city = dest_lower.split(',')[0].strip()
            dest_category = DESTINATION_CATEGORIES.get(dest_city, 'standard')
            dest_multiplier = DESTINATION_MULTIPLIERS.get(dest_category, 1.0)

        # If pipeline not ready, return fallback math
        if not self.pipeline:
            self._load()
        if not self.pipeline:
            return round(1500 * days * grp * dest_multiplier, 2)

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

        # Apply destination cost multiplier
        predicted_budget = predicted_budget * dest_multiplier

        # ── SMART PRICING ADJUSTMENTS ──
        
        # 1. Family / Group Discount (Shared rooms, cabs, bulk food)
        if grp >= 3:
            # e.g., 3 people = 12.5% off, 4 = 15% off, max 30% off for 10+
            discount_pct = min(0.30, 0.05 + (grp * 0.025))
            predicted_budget = predicted_budget * (1.0 - discount_pct)
            
        # 2. Specific Family Discount (Requested by user)
        if is_family:
            # Additional 20% discount for family travel
            predicted_budget = predicted_budget * 0.80

        # 3. Staying with Family / Friends / Home (no room/food costs)
        if st in ['friend_house', 'home', 'family_stay']:
            # No room rent and no food costs (home-cooked meals).
            # Only transport costs remain - estimate ~20% of total budget
            predicted_budget = predicted_budget * 0.20

        return round(predicted_budget, 2)

# Singleton instance
budget_model = HypercubeBudgetEngine()
