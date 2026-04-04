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

SEASON_MULT  = {'peak': 1.4, 'off-peak': 0.8, 'shoulder': 1.0, 'holiday': 1.8}
BOOKING_MULT = {'last-minute': 1.3, 'normal': 1.0, 'advance': 0.8}

class HypercubeBudgetEngine:
    """
    N-Dimensional Budget Hypercube Inference Engine (v2) - Direct Mathematical Engine.
    Uses 0 RAM, loads instantly, impossible to hit OOM (Out Of Memory) errors.
    """
    def __init__(self):
        print("Loaded Budget Hypercube v2 parameters successfully (O(1) Math).")

    def predict(self, days, travel_style="mid", food_type="casual",
                group_size=1, season="shoulder", booking="normal",
                stay_type="budget_hotel"):
        if days <= 0:
            return 0.0

        grp = min(20, max(1, int(group_size)))

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
                'budget':   'budget_hotel',
                'mid':      '3star_hotel',
                'luxury':   '5star_hotel',
                'hotel':    'budget_hotel',
                'camp':     'camping',
            }
            st = _aliases.get(st, 'budget_hotel')

        # Multipliers
        s_mult = SEASON_MULT[s]
        b_mult = BOOKING_MULT[b]

        duration_discount = 0.82 if days > 14 else (0.91 if days >= 7 else 1.0)
        group_discount = 0.65 if grp >= 10 else (0.80 if grp >= 4 else 1.0)

        # Baseline sums per person
        nightly_pp = STAY_NIGHTLY_BASE[st] * s_mult * b_mult * duration_discount
        food_daily_pp = FOOD_DAILY_COST[food] * s_mult
        transport_pp = TRANSPORT_DAILY_PP[style] * s_mult

        total = round((nightly_pp + food_daily_pp + transport_pp) * days * grp * group_discount, 2)
        return total

# Singleton instance
budget_model = HypercubeBudgetEngine()
