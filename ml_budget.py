import math

def euclidean_distance(point1, point2):
    """Calculate the Euclidean distance between two points."""
    distance = 0.0
    for i in range(len(point1)):
        distance += (point1[i] - point2[i]) ** 2
    return math.sqrt(distance)

class MLBudgetEstimator:
    def __init__(self, k=3):
        self.k = k
        self.data_X = []
        self.data_y = []
        # Pre-populate with synthetic "real-life" data for training
        self._load_synthetic_data()

    def _load_synthetic_data(self):
        """
        Loads realistic synthetic data.
        Features: [days, hotel_style, food_type]
        Encoding:
          hotel_style: 1 = Budget, 2 = Mid-range, 3 = Luxury
          food_type:   1 = Street, 2 = Casual, 3 = Fine Dining
        Target (y): Total Cost Per Person (in INR)
        """
        # A mix of various trip types to train the model
        synthetic_records = [
            ([1, 1, 1], 800),     # 1 day, budget hotel, street food = 800
            ([1, 1, 2], 1200),    # 1 day, budget hotel, casual dining = 1200
            ([1, 2, 1], 1500),    # 1 day, mid hotel, street food = 1500
            ([1, 2, 2], 2200),    # 1 day, mid hotel, casual dining = 2200
            ([1, 3, 3], 6500),    # 1 day, luxury hotel, fine dining = 6500
            ([3, 1, 1], 2300),    # 3 days, budget hotel, street food = 2300
            ([3, 1, 2], 3400),    # 3 days, budget hotel, casual dining = 3400
            ([3, 2, 2], 6400),    # 3 days, mid hotel, casual dining = 6400
            ([3, 3, 2], 12000),   # 3 days, luxury hotel, casual dining = 12000
            ([3, 3, 3], 18000),   # 3 days, luxury hotel, fine dining = 18000
            ([5, 1, 1], 4000),    # 5 days, budget, street
            ([5, 2, 2], 10500),   # 5 days, mid, casual
            ([5, 3, 3], 30000),   # 5 days, luxury, fine
            ([7, 1, 1], 5500),    # 7 days, budget, street
            ([7, 2, 2], 14500),   # 7 days, mid, casual
            ([7, 3, 3], 42000),   # 7 days, luxury, fine
            ([10, 1, 2], 11000),  # 10 days, budget, casual
            ([10, 2, 2], 21000),  # 10 days, mid, casual 
            ([10, 3, 3], 60000)   # 10 days, luxury, fine
        ]

        for features, cost in synthetic_records:
            self.data_X.append(features)
            self.data_y.append(cost)

    def predict(self, days, hotel_style, food_type):
        """
        Predicts the budget based on K-Nearest Neighbors.
        hotel_style: 'budget', 'mid', 'luxury'
        food_type: 'street', 'casual', 'fine'
        """
        # Convert string labels to numerical encodings
        hotel_map = {'budget': 1, 'mid': 2, 'luxury': 3}
        food_map = {'street': 1, 'casual': 2, 'fine': 3}

        h_val = hotel_map.get(hotel_style.lower(), 2) # default mid
        f_val = food_map.get(food_type.lower(), 2)    # default casual
        
        target_point = [days, h_val, f_val]

        distances = []
        for i in range(len(self.data_X)):
            dist = euclidean_distance(target_point, self.data_X[i])
            distances.append((dist, self.data_y[i]))

        # Sort by distance
        distances.sort(key=lambda x: x[0])

        # Get the top K nearest neighbors
        neighbors = distances[:self.k]

        # Calculate average cost among neighbors
        avg_cost = sum(neighbor[1] for neighbor in neighbors) / self.k
        return round(avg_cost)

# Initialize a global estimator to be imported and used
budget_model = MLBudgetEstimator(k=3)

if __name__ == "__main__":
    # Test the accuracy of the model against its own training set (Demo purposes)
    print("Evaluating ML Budget Estimator Accuracy...\n")
    
    total_error = 0
    total_cases = len(budget_model.data_X)
    
    for i in range(total_cases):
        features = budget_model.data_X[i]
        actual_cost = budget_model.data_y[i]
        
        # Predict using same feature indices but passing them as args
        # Reverse map for convenience, but the predict function takes strings.
        # We can bypass predicting via strings and calculate directly, or use a hidden predict:
        distances = []
        for j in range(len(budget_model.data_X)):
            if i == j: continue  # Skip itself for cross-validation style
            dist = euclidean_distance(features, budget_model.data_X[j])
            distances.append((dist, budget_model.data_y[j]))
        
        distances.sort(key=lambda x: x[0])
        neighbors = distances[:budget_model.k]
        predicted_cost = sum(n[1] for n in neighbors) / budget_model.k
        
        error = abs(predicted_cost - actual_cost)
        total_error += error
        print(f"Trip Features {features}: Predicted = Rs.{round(predicted_cost)}, Actual = Rs.{actual_cost} (Error: Rs.{round(error)})")
        
    mae = total_error / total_cases
    # Calculate a rough percentage accuracy based on the average cost
    avg_actual_cost = sum(budget_model.data_y) / total_cases
    accuracy_percentage = max(0, 100 - ((mae / avg_actual_cost) * 100))
    
    print("\n--- ML Model Diagnostics ---")
    print(f"Mean Absolute Error (MAE): Rs.{round(mae)}")
    print(f"Estimated Model Accuracy: {round(accuracy_percentage, 2)}%")
    print("----------------------------")
