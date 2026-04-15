# 📊 ML System Architecture Diagram

## Application Flow with ML Integration

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SMART BUDGET TRAVEL PLANNER                          │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      FRONTEND (Dashboard)                        │  │
│  │                                                                  │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │ Trip Planning Module                                   │  │  │
│  │  │ ├─ Destination Input         [TEXT INPUT]              │  │  │
│  │  │ ├─ Travel Dates              [DATE PICKER]             │  │  │
│  │  │ ├─ Group Size                [NUMBER INPUT]            │  │  │
│  │  │ ├─ Travel Style              [RADIO: Budget/Mid/Lux]   │  │  │
│  │  │ ├─ Food Preference           [RADIO OPTIONS]           │  │  │
│  │  │ ├─ Stay Type                 [RADIO: Hotel/Home/etc]   │  │  │
│  │  │ ├─ Family Travel             [CHECKBOX]                │  │  │
│  │  │ └─ [CALCULATE BUTTON] ──────────────────────┐          │  │  │
│  │  └─────────────────────────────────────────────┼──────────┘  │  │
│  │                                                │              │  │
│  │  ┌─────────────────────────────────────────────┼────────────┐ │  │
│  │  │ Route Tracker Module                        │            │ │  │
│  │  │ ├─ Pick Start Location                      │            │ │  │
│  │  │ ├─ Pick End Location                        │            │ │  │
│  │  │ ├─ Map Integration (Get Coordinates)        │            │ │  │
│  │  │ └─ [CALCULATE ROUTE] ─────────────────┐    │            │ │  │
│  │  └──────────────────────────────────────┼─────┼────────────┘ │  │
│  │                                          │     │              │  │
│  └──────────────────────────────────────────┼─────┼──────────────┘  │
│                                              │     │                  │
└──────────────────────────────────────────────┼─────┼──────────────────┘
                                               │     │
                ┌─────────────────────────────┘     └──────────────────┐
                │                                                       │
                ▼                                                       ▼
        ┌──────────────────┐                                  ┌──────────────────┐
        │ POST /api/       │                                  │ POST /api/       │
        │ predict-budget   │                                  │ predict-eta      │
        │                  │                                  │                  │
        │ {                │                                  │ {                │
        │  days: 3         │                                  │  distance: 250   │
        │  group_size: 4   │◄─────── API LAYER ────────────●  │  hour: 14        │
        │  travel_style...│                                  │  day_type: ...   │
        │  destination...   │                                  │ }                │
        │ }                │                                  │                  │
        └──────────────────┘                                  └──────────────────┘
                │                                                       │
                │                                                       │
                ▼                                                       ▼
        ┌──────────────────────────────┐                      ┌──────────────────────────────┐
        │    BACKEND (app.py)          │                      │    BACKEND (app.py)          │
        │                              │                      │                              │
        │ predict_budget_api()         │                      │ predict_eta_api()            │
        │ ├─ Parse JSON                │                      │ ├─ Check authentication      │
        │ ├─ Validate inputs           │                      │ ├─ Parse parameters          │
        │ ├─ Sanitize parameters       │                      │ ├─ Extract distance, hour    │
        │ └─ Call budget_model.predict()│                      │ └─ Call eta_model.predict()  │
        └──────────────────────────────┘                      └──────────────────────────────┘
                │                                                       │
                │                                                       │
                ▼                                                       ▼
        ╔══════════════════════════════╗                      ╔══════════════════════════════╗
        ║   ML MODEL 1: BUDGET         ║                      ║   ML MODEL 2: ETA            ║
        ║                              ║                      ║                              ║
        ║ RandomForest Regressor       ║                      ║ Grid-Based Lookup            ║
        ║ ───────────────────          ║                      ║ ─────────────────            ║
        ║                              ║                      ║                              ║
        ║ Input Features (7):          ║                      ║ Input Parameters:            ║
        ║ 1. days                      ║                      ║ • distance_km                ║
        ║ 2. group_size                ║                      ║ • hour_of_day                ║
        ║ 3. travel_style              ║                      ║ • day_type                   ║
        ║ 4. food_type                 ║                      ║ • weather                    ║
        ║ 5. season                    ║                      ║                              ║
        ║ 6. booking                   ║                      ║ Lookup Process:              ║
        ║ 7. stay_type                 ║                      ║ 1. Find nearest distance bin │
        ║                              ║                      ║ 2. O(1) grid access         │
        ║ Processing:                  ║                      ║ 3. Interpolate residual     ║
        ║ 1. OneHotEncode features     ║                      ║ 4. Return ETA in minutes    ║
        ║ 2. Pass through 30 trees     ║                      ║                              ║
        ║ 3. Average predictions       ║                      ║ Grid Dimensions:             ║
        ║ 4. Apply destination mult.   ║                      ║ 500×24×2×4×4×4              ║
        ║ 5. Apply group discount      ║                      ║ = 1.5M entries               ║
        ║ 6. Apply family discount     ║                      ║                              ║
        ║ 7. Apply stay discount       ║                      ║                              ║
        ║                              ║                      ║                              ║
        ║ Output:                      ║                      ║ Output:                      ║
        ║ Total Budget (₹)             ║                      ║ Duration (minutes)           ║
        ╚══════════════════════════════╝                      ╚══════════════════════════════╝
                │                                                       │
                │                                                       │
                ▼                                                       ▼
        ┌──────────────────────────────┐                      ┌──────────────────────────────┐
        │   RESPONSE JSON              │                      │   RESPONSE JSON              │
        │                              │                      │                              │
        │ {                            │                      │ {                            │
        │   status: "success"          │                      │   status: "success"          │
        │   estimated_budget: 30464.25 │                      │   duration_minutes: 375      │
        │   cost_per_person: 7616.06   │                      │ }                            │
        │   days: 3                    │                      │                              │
        │   stay_type: "budget_hotel"  │                      │ Conversion:                  │
        │ }                            │                      │ 375 mins = 6 hrs 15 mins     │
        └──────────────────────────────┘                      │ Arrival: 8:15 PM             │
                │                                              └──────────────────────────────┘
                │                                                       │
                │                         ┌─────────────────────────────┘
                │                         │
                └─────────────┬───────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │   FRONTEND (Display) │
                    │                      │
                    │ ┌──────────────────┐ │
                    │ │ BUDGET DISPLAY   │ │
                    │ ├────────────────┐ │ │
                    │ │ Total: ₹30,464 │ │ │
                    │ │ Per Person:     │ │ │
                    │ │ ₹7,616          │ │ │
                    │ │ Duration: 3 days│ │ │
                    │ └────────────────┘ │ │
                    │                    │ │
                    │ ┌──────────────────┐ │
                    │ │ ROUTE DISPLAY    │ │
                    │ ├────────────────┐ │ │
                    │ │ Distance: 250km│ │ │
                    │ │ Duration: 6h   │ │ │
                    │ │ Arrival: 8:15PM│ │ │
                    │ └────────────────┘ │ │
                    │                      │
                    └──────────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │    USER SEES:        │
                    │ ✓ Budget Estimate    │
                    │ ✓ Cost Breakdown     │
                    │ ✓ Travel Duration    │
                    │ ✓ Arrival Time       │
                    └──────────────────────┘
```

---

## Model Training Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MODEL TRAINING PROCESS                          │
│                                                                         │
│  BATCH JOB: python train_models.py                                      │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ Step 1: Generate Synthetic Training Data                         │ │
│  │                                                                   │ │
│  │ BASE CONSTANTS (Real Indian Prices):                             │ │
│  │ ├─ Hostels: ₹400/night                                           │ │
│  │ ├─ Budget Hotels: ₹1,200/night                                   │ │
│  │ ├─ 5-Star Hotels: ₹11,000/night                                  │ │
│  │ ├─ Dhaba Food: ₹250/day                                          │ │
│  │ ├─ Restaurant: ₹900/day                                          │ │
│  │ ├─ Budget Transport: ₹350/person/day                             │ │
│  │ └─ Luxury Transport: ₹2,500/person/day                           │ │
│  │                                                                   │ │
│  │ SYNTHETIC DATA GENERATION (50,000 samples):                       │ │
│  │ ├─ Random days: 1-60 range                                       │ │
│  │ ├─ Random group size: 1-20 people                                │ │
│  │ ├─ Random travel_style: budget/mid/luxury                        │ │
│  │ ├─ Random food_type: 6 options                                   │ │
│  │ ├─ Random season: 4 options                                      │ │
│  │ ├─ Random booking: 3 options                                     │ │
│  │ ├─ Random stay_type: 18 options                                  │ │
│  │ └─ Random is_family: 30% True, 70% False                         │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ Step 2: Calculate Labels (Budget for Each Sample)                │ │
│  │                                                                   │ │
│  │ FOR EACH SAMPLE:                                                  │ │
│  │                                                                   │ │
│  │ base_budget = (nightly_cost + food_cost + transport_cost)         │ │
│  │            × days × group_size                                    │ │
│  │            × season_multiplier                                    │ │
│  │            × booking_multiplier                                   │ │
│  │                                                                   │ │
│  │ APPLY DISCOUNTS:                                                  │ │
│  │ if group_size >= 3:                                               │ │
│  │    discount = min(30%, 5% + 2.5% × group_size)                   │ │
│  │    base_budget = base_budget × (1 - discount)                    │ │
│  │                                                                   │ │
│  │ if is_family:                                                     │ │
│  │    base_budget = base_budget × 0.8  (20% off)                    │ │
│  │                                                                   │ │
│  │ if stay_type in [friend_house, home, family_stay]:                │ │
│  │    base_budget = base_budget × 0.2  (80% off)                    │ │
│  │                                                                   │ │
│  │ ADD NOISE:                                                         │ │
│  │ final_budget = base_budget × (1 + gaussian_noise(-15%, +15%))    │ │
│  │                                                                   │ │
│  │ RESULT: 50,000 realistic budget values                            │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ Step 3: Create Scikit-Learn Pipeline                             │ │
│  │                                                                   │ │
│  │ PIPELINE ARCHITECTURE:                                            │ │
│  │                                                                   │ │
│  │ Input DataFrame (50K rows × 7 columns):                           │ │
│  │   days | group_size | travel_style | food_type | ... | budget    │ │
│  │                              │                                    │ │
│  │                              ▼                                    │ │
│  │         ┌──────────────────────────────┐                          │ │
│  │         │ ColumnTransformer            │                          │ │
│  │         │ ─────────────────────        │                          │ │
│  │         │ OneHotEncoder for:           │                          │ │
│  │         │ • travel_style (3→3)         │                          │ │
│  │         │ • food_type (6→6)            │                          │ │
│  │         │ • season (4→4)               │                          │ │
│  │         │ • booking (3→3)              │                          │ │
│  │         │ • stay_type (18→18)          │                          │ │
│  │         │ Passthrough: days, group_sz │                          │ │
│  │         │                              │                          │ │
│  │         │ Output: 50,000 × 41 features│                          │ │
│  │         └──────────────────────────────┘                          │ │
│  │                      │                                            │ │
│  │                      ▼                                            │ │
│  │         ┌──────────────────────────────┐                          │ │
│  │         │ RandomForestRegressor        │                          │ │
│  │         │ ─────────────────────        │                          │ │
│  │         │ • n_estimators=30            │                          │ │
│  │         │ • max_depth=15               │                          │ │
│  │         │ • random_state=42            │                          │ │
│  │         │ • n_jobs=-1 (parallel)       │                          │ │
│  │         │                              │                          │ │
│  │         │ Trains 30 Decision Trees:    │                          │ │
│  │         │ Each sees random 80% of data │                          │ │
│  │         │ and learns budget patterns   │                          │ │
│  │         │                              │                          │ │
│  │         │ Output: Average prediction   │                          │ │
│  │         │ from all 30 trees            │                          │ │
│  │         └──────────────────────────────┘                          │ │
│  │         Training Time: ~5 seconds                                 │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ Step 4: Save Trained Model                                       │ │
│  │                                                                   │ │
│  │ models/budget_rf.pkl (5 MB)                                       │ │
│  │ ├─ Encoder state                                                  │ │
│  │ ├─ 30 Decision Trees (trained weights)                            │ │
│  │ └─ Model metadata                                                 │ │
│  │                                                                   │ │
│  │ Ready for production inference! ✓                                 │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  SIMILAR PROCESS FOR ETA MODEL:                                         │
│  1. Initialize 6D grid cache                                            │ │
│  2. For 1.5M combinations: calculate travel times                       │ │
│  3. Apply complexity factors (weather, terrain, vehicle)                │ │
│  4. Save to models/eta_grid.json (8-10 MB)                              │ │
│  5. Generation time: ~5 seconds                                         │ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Importance (Budget Model)

```
Random Forest learns these feature relationships:

┌─────────────────────────────────────────────────┐
│ How Each Feature Affects Budget Prediction      │
├─────────────────────────────────────────────────┤
│                                                 │
│ STAY_TYPE: ████████████░░░░ (40% importance)   │
│ └─ Most expensive component                     │
│ └─ Hotel choice dominates budget                │
│                                                 │
│ GROUP_SIZE: ██████░░░░░░░░░ (20% importance)   │
│ └─ Affects accommodation & group discounts      │
│                                                 │
│ TRAVEL_STYLE: ██████░░░░░░░░░ (18% importance) │
│ └─ Transport costs vary significantly           │
│                                                 │
│ SEASON: █████░░░░░░░░░░░░░ (12% importance)    │
│ └─ Peak season increases multiplier             │
│                                                 │
│ FOOD_TYPE: ████░░░░░░░░░░░░░░ (5% importance)  │
│ └─ Varies but smaller impact overall            │
│                                                 │
│ DAYS: ███░░░░░░░░░░░░░░░░░░░░ (3% importance)  │
│ └─ Linear relationship (longer = more)          │
│                                                 │
│ BOOKING: ██░░░░░░░░░░░░░░░░░░░░░░ (2% importance)│
│ └─ Small advantage for advance booking          │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Data Flow Summary

```
USER INPUT
    ↓
VALIDATION & SANITIZATION
    ↓
FEATURE ENGINEERING
    ├─ Categorical: travel_style, food_type, season, booking, stay_type
    ├─ Numerical: days, group_size
    └─ Derived: destination (city name extraction)
    ↓
ML MODEL INFERENCE
    ├─ RandomForest: Base prediction
    └─ Post-processing: Multipliers & discounts
    ↓
JSON RESPONSE
    ↓
FRONTEND RENDERING
    ├─ Breakdown table
    ├─ Visual charts
    └─ Summary display
    ↓
USER DECISION
    └─ Accept budget estimate and save trip
```

This architecture ensures **fast, accurate, and reliable** budget estimates and ETA predictions for Indian travelers! 🎯

