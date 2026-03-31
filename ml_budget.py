import json

class HypercubeBudgetEngine:
    """
    N-Dimensional Budget Hypercube Inference Engine.
    """
    def __init__(self):
        self.grid = {}
        self.day_bins = []
        try:
            with open('models/budget_grid.json', 'r') as f:
                self.grid = json.load(f)
            self.day_bins = sorted([int(k) for k in self.grid.keys()])
            print("Loaded Budget Hypercube parameters successfully.")
        except Exception as e:
            print("Error: Budget Hypercube missing.", e)
            
    def predict(self, days, travel_style="mid", food_type="casual", group_size=1, season="shoulder", booking="normal"):
        if days <= 0: return 0.0
        if not self.grid: return 1500 * days * group_size # Fallback
        
        # 1. Nearest Neighbor Discretization
        closest_day = min(self.day_bins, key=lambda x: abs(x - days))
        
        # Clamp group size to trained boundaries (1 to 20)
        grp = min(20, max(1, int(group_size)))
        
        style = travel_style.lower()
        if style not in ['budget', 'mid-range', 'mid', 'luxury']: style = 'mid'
        
        food = food_type.lower()
        if food not in ['street', 'casual', 'fine']: food = 'casual'
            
        s = season.lower()
        if s not in ['peak', 'off-peak', 'shoulder', 'holiday']: s = 'shoulder'
            
        b = booking.lower()
        if b not in ['last-minute', 'normal', 'advance']: b = 'normal'
        
        # O(1) Query
        base_budget = self.grid[str(closest_day)][str(grp)][style][food][s][b]
        
        # Interpolate day variance if prediction exceeds 60 trained days limit
        if closest_day > 0 and days != closest_day:
            adjustment = days / closest_day
            final_budget = base_budget * adjustment
        else:
            final_budget = base_budget
            
        return round(final_budget, 2)
        
# Singleton Instance
budget_model = HypercubeBudgetEngine()
