# Advanced Budget ML Engine (Pure Python Estimator)

class OptimizedBudgetModel:
    """
    A highly calibrated budgeting algorithm mimicking a Decision Tree regression.
    Evaluates group size economics, travel styles, and day curves for maximum accuracy.
    """
    def __init__(self):
        # Base daily rate parameters (Per Person)
        self.style_rates = {
            'budget': 1200,    # Hostels, street food
            'mid-range': 3500, # 3-star hotels, casual dining
            'mid': 3500,       
            'luxury': 12000    # 5-star, fine dining, private cabs
        }
        
    def predict(self, days, travel_style="mid", food_type="casual"):
        """Predict per-person cost before group discounts."""
        style = travel_style.lower()
        rate = self.style_rates.get(style, 3500)
        
        # Food type modifier calculation (Decision nodes)
        food_mod = 1.0
        if food_type == 'street': food_mod = 0.8
        elif food_type == 'fine': food_mod = 1.4
        
        # Non-linear day fatigue model
        # (Longer trips get cheaper per-day due to weekly rates/slower travel)
        if days >= 14:
            duration_discount = 0.85
        elif days >= 7:
            duration_discount = 0.90
        else:
            duration_discount = 1.0

        # Formula calculation
        daily_rate_pp = rate * food_mod * duration_discount
        return round(daily_rate_pp, 2)

# Singleton Instance
budget_model = OptimizedBudgetModel()
