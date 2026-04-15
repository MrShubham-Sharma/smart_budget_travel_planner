# 🤖 Machine Learning Architecture - Smart Budget Travel Planner

## Overview
The Smart Budget Travel Planner uses **two distinct ML models** to provide intelligent budget predictions and ETA calculations for Indian domestic travel.

---

## 1️⃣ BUDGET PREDICTION MODEL

### Algorithm: **Random Forest Regressor**

#### Technical Details:
- **Type**: Supervised Learning (Regression)
- **Framework**: Scikit-Learn
- **Model Complexity**: 30 decision trees with max depth of 15
- **Training Data**: 50,000 synthetic travel records
- **File**: `models/budget_rf.pkl` (trained pipeline)

#### How It Works:

**1. Feature Engineering Pipeline:**
```
Raw Input → Categorical Encoding → RandomForest → Budget Prediction
```

The model processes these **7 input features**:
```
1. days              → Trip duration (1-60 days)
2. group_size        → Number of travelers (1-20 people)
3. travel_style      → Budget/Mid-range/Luxury
4. food_type         → Dhaba/Veg Thali/Restaurant/Hotel Buffet/etc.
5. season            → Peak/Off-peak/Shoulder/Holiday
6. booking           → Last-minute/Normal/Advance
7. stay_type         → Budget Hotel/Resort/Friend's House/Home/etc.
```

**2. Categorical Encoding (OneHotEncoder):**
```
Input Features:
  travel_style='mid'      → [0, 1, 0] (one-hot encoded)
  food_type='dhaba'       → [0, 1, 0, 0, 0, 0] (one-hot)
  season='shoulder'       → [0, 0, 1, 0] (one-hot)
  booking='normal'        → [0, 1, 0] (one-hot)
  stay_type='budget_hotel' → [0, 0, 1, ...] (one-hot)
```

**3. Random Forest Training:**
- **30 decision trees** are trained independently
- Each tree learns different patterns in travel costs
- Final prediction = **Average of all 30 tree predictions**
- Handles non-linear relationships (e.g., group size effects)

**4. Training Data Generation** (Synthetic Data):
```python
Base Costs:
  - Accommodation: ₹200 - ₹11,000 per night
  - Food: ₹250 - ₹1,600 per day
  - Transport: ₹350 - ₹2,500 per person/day

Generated Formula:
  base_budget = (nightly_cost + food_cost + transport_cost) × days × group_size
  
Applied Discounts:
  - Group Discount: 5-30% for 3+ people
  - Family Discount: 20% when traveling with family
  - Stay Discount: 80% for home/friend stays (no accommodation/food cost)
  
Random Noise: ±15% to simulate real-world price fluctuation
```

#### Model Output Adjustments:

```
Step 1: RandomForest Core Prediction
        ↓
Step 2: Destination Multiplier (0.8x - 1.6x)
        - Budget cities (Allahabad): 0.8x
        - Standard cities (Delhi): 1.0x
        - Premium cities (Jaipur): 1.3x
        - Luxury destinations (Goa): 1.6x
        ↓
Step 3: Group Discount (3+ people)
        - 3 people: 12.5% off
        - 4 people: 15% off
        - 10+ people: max 30% off
        ↓
Step 4: Family Travel Discount
        - If family flag = True: 20% off
        ↓
Step 5: Accommodation Type Discount
        - If home/friend stay: 80% off (only transport remains)
        ↓
Final Budget Prediction
```

#### Example Prediction:
```
Input:
  - 3 days trip
  - 4 people (family)
  - Destination: Goa (luxury = 1.6x)
  - Stay: Budget Hotel
  - Food: Dhaba
  - Travel Style: Mid-range
  - Season: Shoulder
  - Booking: Normal

Processing:
  1. RandomForest predicts: ₹28,000 (base)
  2. Destination multiplier (1.6x): ₹44,800
  3. Group discount (4 people: 15%): ₹38,080
  4. Family discount (20%): ₹30,464
  
Final Prediction: ₹30,464 total (₹7,616 per person)
```

#### Where It's Used:
- **API Endpoint**: `/api/predict-budget` (POST)
- **Frontend**: Budget Calculator in Trip Planner modal
- **Trigger**: User clicks "Calculate" button or modifies travel parameters
- **Input Source**: Form values (destination, dates, group size, preferences)

---

## 2️⃣ ETA (ESTIMATED TIME ARRIVAL) PREDICTION MODEL

### Algorithm: **Hypercube Grid-Based Nearest Neighbor Search**

#### Technical Details:
- **Type**: Synthetic Lookup Table with Nearest Neighbor Interpolation
- **Data Structure**: Nested JSON dictionary (hypercube)
- **Dimensions**: 6D (Distance × Hour × Day Type × Weather × Vehicle × Terrain)
- **Grid Size**: ~1.5 million data points
- **File**: `models/eta_grid.json`

#### Grid Dimensions:

```
1. Distance: 0-5000 km (500 bins, 10km each)
2. Hour: 0-23 (24 hours)
3. Day Type: [weekday, weekend] (2 options)
4. Weather: [clear, rain, fog, snow] (4 options)
5. Vehicle: [sedan, suv, bike, bus] (4 options)
6. Terrain: [highway, city, mountain, rural] (4 options)

Total Combinations: 500 × 24 × 2 × 4 × 4 × 4 = 1,536,000 entries
```

#### How It Works:

**1. Grid Construction During Training:**
```python
for distance in 0-5000 km (step 10):
  for hour in 0-23:
    for day_type in [weekday, weekend]:
      for weather in [clear, rain, fog, snow]:
        for vehicle in [sedan, suv, bike, bus]:
          for terrain in [highway, city, mountain, rural]:
            Calculate: base_ETA_minutes = distance / speed(hour, weather, terrain, vehicle)
            Store in JSON structure
```

**2. Prediction Process (O(1) Lookup):**
```
User Input:
  distance = 150 km
  hour = 14 (2 PM)
  day_type = 'weekday'
  weather = 'rain'
  
Lookup Process:
  1. Find nearest distance bin: 150 → bin 150
  2. Direct O(1) dictionary access:
     eta_grid['150']['14']['weekday']['rain'][vehicle][terrain]
  3. Get base ETA: ~180 minutes
  4. Interpolate for residual distance:
     final_ETA = base_ETA × (actual_distance / bin_distance)
     final_ETA = 180 × (150 / 150) = 180 minutes
```

**3. Complexity Factors:**

```
Speed Multipliers:
  ├── Hour Effect:
  │   ├── 8-9 AM (morning rush): 1.6x slower
  │   ├── 5-6 PM (evening rush): 1.6x slower
  │   └── off-peak hours: 1.0x
  │
  ├── Day Effect:
  │   ├── Weekend 11 AM - 3 PM: 1.3x slower
  │   └── Weekday: 1.0x
  │
  ├── Weather Effect:
  │   ├── Clear: 1.0x
  │   ├── Rain: 1.25x slower
  │   ├── Fog: 1.4x slower
  │   └── Snow: 1.8x slower
  │
  ├── Terrain Effect:
  │   ├── Highway: fastest (base speed)
  │   ├── Rural: 1.2x slower
  │   ├── City: 1.5x slower
  │   └── Mountain: 1.8x slower
  │
  └── Vehicle Effect:
      ├── Sedan: baseline
      ├── SUV: 1.1x slower
      ├── Bike: 0.8x (faster)
      └── Bus: 1.3x slower
```

#### Storage Optimization:
- **Format**: JSON (lightweight, human-readable)
- **Size**: ~5-10 MB
- **Lookup Time**: O(1) - direct dictionary access
- **vs. ML Models**: Faster than neural networks for this use case

#### Example Prediction:
```
Input:
  - Distance: 250 km
  - Hour: 14 (2 PM)
  - Day Type: weekday
  - Weather: rain
  - Vehicle: sedan (default)
  - Terrain: highway (default)

Processing:
  1. Nearest bin: 250 → use bin 250
  2. Base ETA from grid: 300 minutes
  3. Apply complexity factors:
     - Hour 14 (off-peak): 1.0x
     - Weekday: 1.0x
     - Rain weather: 1.25x
     - Highway: 1.0x
     - Sedan: 1.0x
     
  4. Interpolate: 300 × (250/250) = 300 minutes
  5. Final: ~5 hours for 250 km

With slowdown: ~375 minutes (6.25 hours) if weather factor applied
```

#### Where It's Used:
- **API Endpoint**: `/api/predict-eta` (POST)
- **Frontend**: Route tracker, trip planning
- **Trigger**: User calculates route between source and destination
- **Purpose**: Show arrival time estimates for trips

---

## 3️⃣ WHERE ML IS USED IN THE APPLICATION

### A. Budget Calculation Flow:

```
User Interface
    ↓
Dashboard.js (Frontend)
    ├─ Captures user input:
    │  ├─ Destination
    │  ├─ Trip dates
    │  ├─ Group size
    │  ├─ Travel style (Budget/Mid/Luxury)
    │  ├─ Food preference
    │  ├─ Stay type
    │  ├─ Family flag
    │  └─ Booking window
    ↓
POST /api/predict-budget
    ↓
app.py (Backend)
    ├─ Validates input
    ├─ Calls budget_model.predict()
    ↓
ml_budget.py
    ├─ Loads RandomForest pipeline
    ├─ Prepares DataFrame with features
    ├─ Makes prediction: Y = RF.predict(features)
    ├─ Applies destination multiplier
    ├─ Applies group/family discounts
    ├─ Applies stay type adjustments
    ↓
Returns JSON
    ├─ estimated_budget
    ├─ cost_per_person
    └─ stay_type detail
    ↓
Frontend
    └─ Displays budget estimate with breakdown
```

### B. ETA Calculation Flow:

```
Route Tracker
    ↓
Dashboard.js (Frontend)
    ├─ Gets user coordinates
    ├─ Gets destination coordinates
    ├─ Calculates distance
    ├─ Gets current time (hour)
    ├─ Detects current weather
    ↓
POST /api/predict-eta
    ↓
app.py (Backend)
    ├─ Validates authentication
    ├─ Extracts parameters
    ├─ Calls eta_model.predict()
    ↓
ml_eta.py
    ├─ Loads ETA grid from JSON
    ├─ Finds nearest distance bin
    ├─ O(1) dictionary lookup
    ├─ Interpolates for exact distance
    ├─ Applies complexity multipliers
    ↓
Returns JSON
    └─ duration_minutes
    ↓
Frontend
    └─ Displays ETA and arrival time
```

---

## 4️⃣ MODEL TRAINING PIPELINE

### Budget Model Training (`train_models.py`):

```
1. Load Base Cost Constants
   ├─ STAY_NIGHTLY_BASE: ₹200 - ₹11,000
   ├─ FOOD_DAILY_COST: ₹250 - ₹1,600
   └─ TRANSPORT_DAILY_PP: ₹350 - ₹2,500

2. Generate 50,000 Synthetic Samples
   ├─ days: 1-60 (randomint)
   ├─ group_size: 1-20 (randomint)
   ├─ travel_style: random choice
   ├─ food_type: random choice
   ├─ season: random choice
   ├─ booking: random choice
   ├─ stay_type: random choice
   └─ is_family: 30% True, 70% False

3. Generate Labels (Y values)
   For each sample:
   ├─ Calculate base costs × multipliers
   ├─ Apply group discounts (3+ people)
   ├─ Apply family discount (if is_family)
   ├─ Apply stay type discount
   └─ Add ±15% random noise

4. Create Scikit-Learn Pipeline
   ├─ ColumnTransformer: OneHotEncoder for categoricals
   ├─ RandomForestRegressor (30 trees, depth=15)
   └─ Pipeline combines preprocessing + model

5. Train & Save
   ├─ Fit pipeline on 50,000 samples
   ├─ Save to models/budget_rf.pkl
   └─ Training time: ~5 seconds
```

### ETA Model Training (Grid Generation):

```
1. Initialize empty grid dictionary

2. For each distance bin (0-5000 km):
   For each hour (0-23):
     For each day_type [weekday, weekend]:
       For each weather [clear, rain, fog, snow]:
         For each vehicle [sedan, suv, bike, bus]:
           For each terrain [highway, city, mountain, rural]:
             
             Calculate base speed:
               speed_kmh = 50 km/h (average)
             
             Apply multipliers:
               ├─ Hour multiplier (rush hour effects)
               ├─ Day multiplier (weekend effects)
               ├─ Weather slowdown
               ├─ Terrain roughness
               └─ Vehicle efficiency
             
             Final ETA = distance / (speed_kmh × multipliers)
             
             Store: grid[dist][hour][day][weather][vehicle][terrain] = eta_minutes

3. Save grid to models/eta_grid.json (~10 MB)
   Generation time: ~5 seconds
```

---

## 5️⃣ MODEL PERFORMANCE & CHARACTERISTICS

### Budget Model:

| Metric | Value |
|--------|-------|
| Algorithm | Random Forest Regressor |
| Number of Trees | 30 |
| Max Tree Depth | 15 |
| Training Samples | 50,000 |
| Input Features | 7 |
| Feature Types | 4 categorical, 3 numerical |
| Training Time | ~5 seconds |
| Prediction Time | <100ms |
| Model File Size | ~5 MB |

**Advantages:**
- ✅ Handles non-linear relationships
- ✅ Captures interaction effects (e.g., group size × season)
- ✅ Robust to outliers
- ✅ Fast predictions

**Limitations:**
- ⚠️ Can extrapolate beyond training range
- ⚠️ Doesn't capture real-time market fluctuations
- ⚠️ Requires periodic retraining with new data

### ETA Model:

| Metric | Value |
|--------|-------|
| Algorithm | Grid-based Lookup + Interpolation |
| Dimensions | 6D hypercube |
| Total Grid Points | ~1.5 million |
| Lookup Complexity | O(1) |
| Interpolation Method | Linear |
| File Size | ~8-10 MB |
| Generation Time | ~5 seconds |

**Advantages:**
- ✅ Perfect O(1) lookup
- ✅ Deterministic (same input = same output)
- ✅ Easy to visualize and debug
- ✅ No training overhead at runtime

**Limitations:**
- ⚠️ Fixed resolution (10km bins)
- ⚠️ Limited by pre-generated grid
- ⚠️ Doesn't adapt to real traffic
- ⚠️ Requires regeneration for new factors

---

## 6️⃣ API INTEGRATION

### Budget Prediction API:

```
POST /api/predict-budget

Request:
{
  "days": 3,
  "group_size": 4,
  "travel_style": "mid",
  "food_type": "dhaba",
  "season": "shoulder",
  "booking": "normal",
  "stay_type": "budget_hotel",
  "is_family": true,
  "destination": "Goa"
}

Response:
{
  "status": "success",
  "estimated_budget": 30464.25,
  "cost_per_person": 7616.06,
  "days": 3,
  "stay_type": "budget_hotel"
}
```

### ETA Prediction API:

```
POST /api/predict-eta

Request:
{
  "distance_km": 250,
  "hour_of_day": 14,
  "day_type": "weekday",
  "weather": "rain"
}

Response:
{
  "status": "success",
  "duration_minutes": 375
}
```

---

## 7️⃣ FILES & STRUCTURE

```
smart_budget_travel_planner/
├── ml_budget.py                 # Budget RF model
├── ml_eta.py                    # ETA grid model
├── train_models.py              # Model training scripts
├── app.py                       # API endpoints
├── static/js/dashboard.js       # Frontend integration
└── models/
    ├── budget_rf.pkl            # Trained RandomForest
    └── eta_grid.json            # Precomputed ETA grid
```

---

## 8️⃣ FUTURE IMPROVEMENTS

### Budget Model Enhancements:
- [ ] Collect real travel data for retraining
- [ ] Implement gradient boosting (XGBoost) for better accuracy
- [ ] Add real-time price feeds from booking sites
- [ ] Use time-series forecasting for seasonal trends
- [ ] Incorporate user reviews & ratings

### ETA Model Enhancements:
- [ ] Integrate real-time traffic APIs (Google Maps, Mapbox)
- [ ] Add deep learning (LSTM) for traffic pattern prediction
- [ ] Implement A/B testing for model accuracy
- [ ] Add vehicle-specific routing (highways for cars, shortcuts for bikes)
- [ ] Support international routes (not just India)

---

## Summary

**Two ML Systems in Action:**

| Component | Algorithm | Purpose | Location |
|-----------|-----------|---------|----------|
| **Budget Estimator** | Random Forest (30 trees) | Predict trip cost | `/api/predict-budget` |
| **Route ETA** | Grid-based Lookup | Predict travel time | `/api/predict-eta` |

**Data Flow:**
```
User Input → Frontend → API → ML Model → Prediction → JSON Response → Display
```

Both models work together to provide comprehensive trip planning, from budget estimation to travel time forecasting, enabling users to plan their Indian domestic trips effectively and affordably! 🇮🇳✈️

