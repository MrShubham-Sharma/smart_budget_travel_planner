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

class HypercubeBudgetEngine:
    """
    N-Dimensional Budget Hypercube Inference Engine (v2).
    Dimensions: days × group_size × travel_style × food_type × season × booking × stay_type
    """
    GRID_PATH = 'models/budget_grid.json'

    def __init__(self):
        self.grid = {}
        self.day_bins = []
        self._load()

    def _load(self):
        """Try to load the grid from disk. Safe to call multiple times."""
        try:
            with open(self.GRID_PATH, 'r') as f:
                self.grid = json.load(f)
            self.day_bins = sorted([int(k) for k in self.grid.keys()])
            print("Loaded Budget Hypercube v2 parameters successfully.")
        except Exception as e:
            print("Error: Budget Hypercube missing or incompatible.", e)
            self.grid = {}
            self.day_bins = []

    def predict(self, days, travel_style="mid", food_type="casual",
                group_size=1, season="shoulder", booking="normal",
                stay_type="budget_hotel"):
        if days <= 0:
            return 0.0

        # Lazy-reload if grid was missing at startup but is now trained
        if not self.grid:
            self._load()

        if not self.grid:
            # Still missing — return a safe fallback estimate
            return round(1500 * days * group_size, 2)

        # ── Nearest-neighbour day discretisation ──────────────────────────
        closest_day = min(self.day_bins, key=lambda x: abs(x - days))

        # ── Clamp / normalise inputs ────────────────────────────────────
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

        # ── O(1) grid lookup ─────────────────────────────────────────────
        base_budget = self.grid[str(closest_day)][str(grp)][style][food][s][b][st]

        # ── Interpolate for day counts outside the 60-day training range ─
        if closest_day > 0 and days != closest_day:
            base_budget = base_budget * (days / closest_day)

        return round(base_budget, 2)


# Singleton instance
budget_model = HypercubeBudgetEngine()
