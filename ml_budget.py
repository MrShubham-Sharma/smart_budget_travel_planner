import json

# All stay types the model knows about (must match train_models.py STAY_NIGHTLY_BASE)
VALID_STAY_TYPES = [
    'hostel', 'camping', 'dharamshala', 'ashram', 'guesthouse',
    'budget_hotel', 'homestay', 'heritage_hotel', '3star_hotel',
    'resort', '5star_hotel', 'houseboat', 'treehouse',
    'desert_camp', 'tent_resort',
]

class HypercubeBudgetEngine:
    """
    N-Dimensional Budget Hypercube Inference Engine (v2).
    Dimensions: days × group_size × travel_style × food_type × season × booking × stay_type
    """
    def __init__(self):
        self.grid = {}
        self.day_bins = []
        try:
            with open('models/budget_grid.json', 'r') as f:
                self.grid = json.load(f)
            self.day_bins = sorted([int(k) for k in self.grid.keys()])
            print("Loaded Budget Hypercube v2 parameters successfully.")
        except Exception as e:
            print("Error: Budget Hypercube missing or incompatible.", e)

    def predict(self, days, travel_style="mid", food_type="casual",
                group_size=1, season="shoulder", booking="normal",
                stay_type="budget_hotel"):
        if days <= 0:
            return 0.0
        if not self.grid:
            # Fallback when model file is absent
            return 1500 * days * group_size

        # ── Nearest-neighbour day discretisation ──────────────────────────
        closest_day = min(self.day_bins, key=lambda x: abs(x - days))

        # ── Clamp / normalise inputs ────────────────────────────────────
        grp = min(20, max(1, int(group_size)))

        style = travel_style.lower()
        if style not in ['budget', 'mid-range', 'mid', 'luxury']:
            style = 'mid'

        food = food_type.lower()
        if food not in ['street', 'casual', 'fine']:
            food = 'casual'

        s = season.lower()
        if s not in ['peak', 'off-peak', 'shoulder', 'holiday']:
            s = 'shoulder'

        b = booking.lower()
        if b not in ['last-minute', 'normal', 'advance']:
            b = 'normal'

        st = stay_type.lower().strip()
        if st not in VALID_STAY_TYPES:
            # Map legacy / frontend values gracefully
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
