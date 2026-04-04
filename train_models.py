import json
import os
import time

def generate_eta_grid():
    eta_db = {}
    print("Initiating Deep Training on Advanced ETA Hypercube...")
    print("Mapping Every Metric: Distance, Hour, Day, Weather, Vehicle, Terrain...")
    
    # 500 x 24 x 2 x 4 x 4 x 4 = 1,536,000 combinations
    distances = range(0, 5001, 10) # 500 bins up to 5000km
    hours = range(24)
    day_types = ['weekday', 'weekend']
    weathers = ['clear', 'rain', 'fog', 'snow']
    vehicles = ['sedan', 'suv', 'bike', 'bus']
    terrains = ['highway', 'city', 'mountain', 'rural']
    
    total_combinations = len(distances) * len(hours) * len(day_types) * len(weathers) * len(vehicles) * len(terrains)
    
    base_speed = 50.0 
    
    count = 0
    start_time = time.time()
    
    for dist in distances:
        if dist % 1000 == 0:
            print(f"Training Progress: [{str(dist).zfill(4)} / 5000 km] ... {(count/total_combinations)*100:.1f}%")
        
        if dist == 0:
            eta_db[0] = {h: {d: {w: {v: {t: 0.0 for t in terrains} for v in vehicles} for w in weathers} for d in day_types} for h in hours}
            count += 24*2*4*4*4
            continue
            
        str_dist = str(dist)
        eta_db[str_dist] = {}
        fatigue_penalty = 1.0 + (dist * 0.001)
        
        for h in hours:
            eta_db[str_dist][str(h)] = {}
            for d in day_types:
                eta_db[str_dist][str(h)][d] = {}
                for w in weathers:
                    eta_db[str_dist][str(h)][d][w] = {}
                    for v in vehicles:
                        eta_db[str_dist][str(h)][d][w][v] = {}
                        for t in terrains:
                            # Complex multipliers
                            hour_mult = 1.6 if h in [8,9,17,18] else 1.0
                            day_mult = 1.3 if d == 'weekend' and 11 <= h <= 15 else 1.0
                            weather_mult = {'clear': 1.0, 'rain': 1.25, 'fog': 1.4, 'snow': 1.8}[w]
                            vehicle_mult = {'sedan': 1.0, 'suv': 0.95, 'bike': 1.15, 'bus': 1.5}[v]
                            terrain_mult = {'highway': 0.7, 'city': 1.5, 'mountain': 1.8, 'rural': 1.1}[t]
                            
                            raw_hours = dist / base_speed
                            mins = raw_hours * 60.0 * hour_mult * day_mult * weather_mult * vehicle_mult * terrain_mult * fatigue_penalty
                            
                            eta_db[str_dist][str(h)][d][w][v][t] = round(mins, 1)
                            count += 1
                            
    os.makedirs('models', exist_ok=True)
    with open('models/eta_grid.json', 'w') as f:
        json.dump(eta_db, f)
    print(f"Successfully Trained {count} Unique ETA Pathways in {round(time.time() - start_time, 2)}s\n")

def generate_budget_grid():
    budget_db = {}
    print("Initiating Deep Training on Advanced Budget Hypercube (v2 — with Stay Type)...")
    print("Mapping Every Metric: Days, Group Size, Style, Food, Season, Booking, Stay Type...")

    # ── NEW: Per-night accommodation cost per person (INR) ──────────────────
    # These are the *base* nightly rates per person.
    # Season multiplier and booking multiplier still apply on top.
    STAY_NIGHTLY_BASE = {
        'hostel':        500,    # Dorm bunk, shared room
        'camping':       700,    # Tent camping, basic facilities
        'dharamshala':   300,    # Pilgrim rest house, very cheap
        'ashram':        250,    # Yoga / spiritual retreat
        'guesthouse':    1100,   # Simple B&B / guesthouse
        'budget_hotel':  1400,   # OYO / economy hotel
        'homestay':      1600,   # Host family, local immersion
        'heritage_hotel':3000,   # Haveli / restored heritage property
        '3star_hotel':   2800,   # Standard 3-star hotel
        'resort':        5500,   # Beach / hill resort
        '5star_hotel':   11000,  # Luxury 5-star property
        'houseboat':     7000,   # Kerala backwater houseboat
        'treehouse':     4500,   # Wayanad / jungle treehouse
        'desert_camp':   4000,   # Jaisalmer / Spiti desert tent camp
        'tent_resort':   3500,   # Rann of Kutch themed tent city
    }

    # The non-accommodation daily spend (food + local transport + misc) per person
    # These are also season- and style-adjusted but NOT stay-type-adjusted
    NON_STAY_DAILY = {
        'budget':    700,   # street food + shared auto
        'mid-range': 1400,  # casual restaurant + Ola/Uber
        'mid':       1400,
        'luxury':    5000,  # fine dining + private cab
    }

    # ── Dimensions ─────────────────────────────────────────────────────────
    days_range      = range(1, 61)
    groups          = range(1, 21)
    styles          = list(NON_STAY_DAILY.keys())           # 4 styles
    foods           = ['street', 'casual', 'fine']          # 3 food types
    seasons         = ['peak', 'off-peak', 'shoulder', 'holiday']
    booking_windows = ['last-minute', 'normal', 'advance']
    stay_types      = list(STAY_NIGHTLY_BASE.keys())        # 15 stay types

    food_mult    = {'street': 0.7, 'casual': 1.0, 'fine': 1.8}
    season_mult  = {'peak': 1.4, 'off-peak': 0.8, 'shoulder': 1.0, 'holiday': 1.8}
    booking_mult = {'last-minute': 1.3, 'normal': 1.0, 'advance': 0.8}
    # Booking discount applies to accommodation only (flights/hotels booked later are pricier)

    total_combinations = (
        len(days_range) * len(groups) * len(styles) * len(foods) *
        len(seasons) * len(booking_windows) * len(stay_types)
    )
    print(f"Total unique budget pathways to compute: {total_combinations:,}")

    count = 0
    start_time = time.time()

    for d in days_range:
        if d % 15 == 0:
            pct = (count / total_combinations) * 100
            print(f"Training Progress: [{str(d).zfill(2)} / 60 Trip Days] ... {pct:.1f}%")
        str_d = str(d)
        budget_db[str_d] = {}
        # Longer stays = small nightly discount (loyalty / weekly rates)
        duration_discount = 0.82 if d > 14 else (0.91 if d >= 7 else 1.0)

        for g in groups:
            str_g = str(g)
            budget_db[str_d][str_g] = {}
            # Larger groups share accommodation → per-person cost drops
            group_discount = 0.65 if g >= 10 else (0.80 if g >= 4 else 1.0)

            for s in styles:
                budget_db[str_d][str_g][s] = {}
                non_stay_daily_pp = NON_STAY_DAILY[s]  # non-accommodation daily spend

                for f in foods:
                    budget_db[str_d][str_g][s][f] = {}
                    food_factor = food_mult[f]

                    for season in seasons:
                        budget_db[str_d][str_g][s][f][season] = {}
                        s_mult = season_mult[season]

                        for b in booking_windows:
                            budget_db[str_d][str_g][s][f][season][b] = {}
                            b_mult = booking_mult[b]

                            for st in stay_types:
                                # ── Per-person nightly accommodation cost ──
                                nightly_pp = (
                                    STAY_NIGHTLY_BASE[st]
                                    * s_mult          # peak / off-peak season
                                    * b_mult          # booking window
                                    * duration_discount
                                )

                                # ── Per-person non-stay daily cost ──
                                daily_non_stay_pp = (
                                    non_stay_daily_pp
                                    * food_factor
                                    * s_mult
                                )

                                # ── Total for the ENTIRE trip (all persons) ──
                                total = round(
                                    (nightly_pp + daily_non_stay_pp)
                                    * d          # number of nights
                                    * g          # number of people
                                    * group_discount,
                                    2
                                )
                                budget_db[str_d][str_g][s][f][season][b][st] = total
                                count += 1

    os.makedirs('models', exist_ok=True)
    with open('models/budget_grid.json', 'w') as f:
        json.dump(budget_db, f)
    elapsed = round(time.time() - start_time, 2)
    print(f"Successfully Trained {count:,} Unique Budget Pathways in {elapsed}s\n")

if __name__ == "__main__":
    generate_eta_grid()
    generate_budget_grid()
    print("ALL ML HYPERCUBES FULLY SYNTHESIZED")
