import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import database  # Your enhanced database.py
import config    # Our new config file
from ml_budget import budget_model # Our new Pure-Python ML Budget Estimator

app = Flask(__name__)
# Load configuration from config.py
app.config.from_object('config.Config')

# Initialize DB and create admin seed
database.init_db()
app.secret_key = app.config.get('SECRET_KEY', 'super-secret-default-key')

# Automatically seed the admin user on boot
if not database.get_user_by_email("admin@admin.com"):
    hashed_admin_pass = generate_password_hash("admin123")
    database.add_user("Admin Master", "admin@admin.com", hashed_admin_pass)
database.make_user_admin("admin@admin.com")

@app.before_request
def log_activity_middleware():
    """Silently logs all incoming traffic and user actions."""
    # Don't log static files
    if request.path.startswith('/static') or request.path.startswith('/api'):
        return
        
    user_id = session.get('user_id')
    ip = request.remote_addr or '127.0.0.1'
    endpoint = request.path
    
    # Contextualize action
    action = 'PAGE_VISIT'
    if request.path == '/login' and request.method == 'POST':
        action = 'LOGIN_ATTEMPT'
    elif request.path == '/dashboard':
        action = 'VIEW_DASHBOARD'
    
    # We offload telemetry to DB
    database.log_activity(user_id, ip, endpoint, action)

# ------------------
# 1. PAGE ROUTES
# ------------------

@app.route('/')
def home():
    """Redirect home to the login page."""
    return redirect(url_for('login_page'))

@app.route('/login-page')
def login_page():
    """Serve the login page."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/signup-page')
def signup_page():
    """Serve the signup page."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    """Serve the main dashboard, protected by session."""
    if not session.get('user_id'):
        return redirect(url_for('login_page'))
    return render_template('dashboard.html', user_name=session.get('user_name'), is_admin=session.get('is_admin'))

@app.route('/admin')
def admin_panel():
    """Serve the secure Admin Dashboard."""
    if not session.get('is_admin'):
        database.log_activity(session.get('user_id'), request.remote_addr, '/admin', 'UNAUTHORIZED_ADMIN_ATTEMPT')
        return redirect(url_for('dashboard'))
    return render_template('admin.html')

@app.route('/api/admin-stats')
def admin_stats_api():
    """Returns live JSON metrics to fuel the admin chart."""
    if not session.get('is_admin'):
        return jsonify({"status": "error"}), 403
    return jsonify(database.get_admin_dashboard_metrics())


@app.route('/logout')
def logout():
    """Clear the session and log the user out."""
    session.clear()
    return redirect(url_for('login_page'))

# ------------------
# 2. AUTH API
# ------------------

@app.route('/signup', methods=['POST'])
def signup():
    """API endpoint for new user registration."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request: Must be JSON"}), 400
    
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"status": "error", "message": "All fields are required"})

    # SECURITY: Hash the password before storing
    hashed_password = generate_password_hash(password)

    if database.add_user(name, email, hashed_password):
        return jsonify({"status": "success", "redirect": "/login-page"})
    else:
        return jsonify({"status": "error", "message": "Email already exists"})

@app.route('/login', methods=['POST'])
def login():
    """API endpoint for user login."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request: Must be JSON"}), 400
        
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"status": "error", "message": "All fields are required"})

    # SECURITY: Fetch user by email, then check hash
    user = database.get_user_by_email(email)

    # user[0]=id, user[1]=name, user[2]=hashed_pass, user[3]=is_admin
    if user and check_password_hash(user[2], password):
        # Configure Remember Me
        remember = data.get('remember', False)
        if remember:
            session.permanent = True
            
        session['user_id'] = user[0]
        session['user_name'] = user[1]
        session['is_admin'] = bool(user[3])
        
        # Telemetry login
        database.log_activity(user[0], request.remote_addr, '/login', 'LOGIN_SUCCESS')
        
        redirect_url = '/admin' if session['is_admin'] else '/dashboard'
        return jsonify({"status": "success", "redirect": redirect_url})
    else:
        return jsonify({"status": "error", "message": "Invalid Credentials"})

# ------------------
# 3. TRIP API (CRUD)
# ------------------

@app.route('/add-trip', methods=['POST'])
def add_trip_api():
    """API to add a new trip for the logged-in user."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request: Must be JSON"}), 400

    data = request.get_json()
    try:
        trip_name = data.get("trip_name")
        destination = data.get("destination")
        budget = float(data.get("budget") or 0)
        latitude = float(data.get("latitude") or 0)
        longitude = float(data.get("longitude") or 0)

        if not trip_name or not destination or latitude == 0 or longitude == 0:
            return jsonify({"status": "error", "message": "Trip name, destination, and location are required"})

        success = database.add_trip(
            user_id=session["user_id"],
            trip_name=trip_name,
            destination=destination,
            start_date=data.get("start_date"), # Can be None
            end_date=data.get("end_date"),     # Can be None
            budget=budget,
            latitude=latitude,
            longitude=longitude
        )
        if success:
            return jsonify({"status": "success", "message": "Trip added successfully!"})
        else:
            return jsonify({"status": "error", "message": "Failed to add trip"})
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid numeric input for budget/location"})

@app.route('/get-trips', methods=['GET'])
def get_trips_api():
    """API to fetch all trips for the logged-in user."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    trips = database.get_user_trips(session["user_id"])
    trips_list = [
        {
            "id": t[0],
            "trip_name": t[2],
            "destination": t[3],
            "start_date": t[4],
            "end_date": t[5],
            "budget": t[6],
            "latitude": t[7],
            "longitude": t[8]
        } for t in trips
    ]
    return jsonify({"status": "success", "trips": trips_list})

# NEW: API to get a single trip's details for the live tracker
@app.route('/get-trip-details/<int:trip_id>', methods=['GET'])
def get_trip_details_api(trip_id):
    """API to get details for a single trip, for the live tracker."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    trip = database.get_trip(trip_id)
    if not trip:
        return jsonify({"status": "error", "message": "Trip not found"}), 404
    
    # SECURITY: Verify the user owns this trip
    if trip[1] != session["user_id"]:
        return jsonify({"status": "error", "message": "Not authorized"}), 403

    trip_data = {
        "id": trip[0],
        "trip_name": trip[2],
        "destination": trip[3],
        "latitude": trip[7],
        "longitude": trip[8]
    }
    return jsonify({"status": "success", "trip": trip_data})

@app.route('/update-trip', methods=['POST'])
def update_trip_api():
    """API to update an existing trip."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request: Must be JSON"}), 400

    data = request.get_json()
    trip_id = data.get("trip_id")
    if not trip_id:
        return jsonify({"status": "error", "message": "trip_id required"})

    # SECURITY: Check ownership before update
    trip = database.get_trip(trip_id)
    if not trip:
        return jsonify({"status": "error", "message": "Trip not found"}), 404
    if trip[1] != session["user_id"]:
        return jsonify({"status": "error", "message": "Not authorized"}), 403

    try:
        success = database.update_trip(
            trip_id=trip_id,
            trip_name=data.get("trip_name"),
            destination=data.get("destination"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            budget=None if data.get("budget") in (None, "") else float(data.get("budget")),
            latitude=None if data.get("latitude") in (None, "") else float(data.get("latitude")),
            longitude=None if data.get("longitude") in (None, "") else float(data.get("longitude"))
        )
        return jsonify({"status": "success" if success else "error", "message": "Updated" if success else "Update failed"})
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid numeric values"})

@app.route('/delete-trip', methods=['POST'])
def delete_trip_api():
    """API to delete a trip."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request: Must be JSON"}), 400

    data = request.get_json()
    trip_id = data.get('trip_id')
    if not trip_id:
        return jsonify({"status": "error", "message": "No trip id provided"})

    # SECURITY: The delete_trip function MUST also check user_id
    success = database.delete_trip(trip_id, session['user_id'])
    
    if success:
        return jsonify({"status": "success", "message": "Trip deleted successfully"})
    else:
        return jsonify({"status": "error", "message": "Trip not found or not authorized"})

# ------------------
# 4. BUDGET API (ENHANCED)
# ------------------

@app.route('/add-expense', methods=['POST'])
def add_expense_api():
    """API to add an expense to a specific trip."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request: Must be JSON"}), 400

    data = request.get_json()
    trip_id = data.get('trip_id')
    category = data.get('category')
    amount = data.get('amount')
    description = data.get('description')

    if not trip_id or not category or not amount:
        return jsonify({"status": "error", "message": "Trip, category, and amount are required"})

    # SECURITY: Check ownership
    trip = database.get_trip(trip_id)
    if not trip:
        return jsonify({"status": "error", "message": "Trip not found"}), 404
    if trip[1] != session["user_id"]:
        return jsonify({"status": "error", "message": "Not authorized"}), 403

    try:
        success = database.add_expense(
            trip_id=trip_id,
            category=category,
            amount=float(amount),
            description=description
        )
        if success:
            return jsonify({"status": "success", "message": "Expense added!"})
        else:
            return jsonify({"status": "error", "message": "Failed to add expense"})
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid amount"})

@app.route('/get-expenses/<int:trip_id>', methods=['GET'])
def get_expenses_api(trip_id):
    """API to get all expenses and total for a specific trip."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    # SECURITY: Check ownership
    trip = database.get_trip(trip_id)
    if not trip:
        return jsonify({"status": "error", "message": "Trip not found"}), 404
    if trip[1] != session["user_id"]:
        return jsonify({"status": "error", "message": "Not authorized"}), 403

    expenses = database.get_expenses(trip_id)
    total_spent = sum(e[3] for e in expenses) # e[3] is 'amount'
    
    # --- ENHANCEMENT: Return budget details ---
    # trip[6] is the 'budget' column from the 'trips' table
    trip_budget = float(trip[6]) if trip[6] is not None else 0.0  # FIX: guard against None
    remaining_budget = trip_budget - total_spent
    # --- END ENHANCEMENT ---

    return jsonify({
        "status": "success",
        "expenses": expenses,
        "total_spent": total_spent,
        "trip_budget": trip_budget,
        "remaining_budget": remaining_budget
    })

@app.route('/api/predict-budget', methods=['POST'])
def predict_budget_api():
    """API endpoint to predict budget using our custom ML Hypercube model."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request: Must be JSON"}), 400

    data = request.get_json()
    try:
        days = int(data.get('days', 1))
        group_size = int(data.get('group_size', 1))
        hotel_style = data.get('travel_style', 'mid') # 'budget', 'mid-range', 'luxury'
        food_type = data.get('food_type', 'casual')   # 'street', 'casual', 'fine'
        season = data.get('season', 'shoulder')       # 'peak', 'off-peak', 'shoulder'

        if days <= 0 or group_size <= 0:
            return jsonify({"status": "error", "message": "Days and group size must be positive"}), 400

        # Query the advanced Hypercube Budget engine
        total_budget = budget_model.predict(
            days=days,
            travel_style=hotel_style,
            food_type=food_type,
            group_size=group_size,
            season=season
        )

        return jsonify({
            "status": "success",
            "estimated_budget": total_budget,
            "cost_per_person": round(total_budget / group_size, 2) if group_size > 0 else total_budget,
            "days": days
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ------------------
# 6. RUN APP
# ------------------

from ml_eta import eta_model

@app.route('/api/predict-eta', methods=['POST'])
def predict_eta_api():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    try:
        data = request.json
        distance_km = float(data.get('distance_km', 0))
        hour_of_day = int(data.get('hour_of_day', 12))
        day_type = data.get('day_type', 'weekday')
        weather = data.get('weather', 'clear')
        
        duration_mins = eta_model.predict(
            distance_km=distance_km,
            hour_of_day=hour_of_day,
            day_type=day_type,
            weather=weather
        )
        
        return jsonify({
            "status": "success",
            "duration_minutes": duration_mins
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# ------------------
# 7. INTELLIGENT CHATBOT API
# ------------------

@app.route('/api/chat', methods=['POST'])
def chat_api():
    """
    Smart NLP-style chatbot backend.
    Processes user message, matches against intent engine, and returns
    a contextual travel response. Falls back to Wikipedia summary for
    unknown factual queries.
    """
    if not request.is_json:
        return jsonify({"reply": "Invalid request format."}), 400

    data = request.get_json()
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({"reply": "Please type something so I can help you!"}), 400

    # Log chat usage
    database.log_activity(session.get('user_id'), request.remote_addr, '/api/chat', 'CHATBOT_QUERY')

    reply = _process_chatbot(message)
    return jsonify({"reply": reply})


def _process_chatbot(message):
    """
    AI Travel Chatbot — NLP intent engine.
    Handles 60+ travel intents, auto-detects Indian place names,
    and uses Wikipedia live API for real-time information on any destination.
    """
    import re, urllib.request, urllib.parse as uparse, json as json_lib

    m = message.lower().strip()

    # ─── INDIAN PLACES DATABASE ────────────────────────────────────────────────
    # Comprehensive list of Indian states, union territories, cities, towns,
    # hill stations, tourist spots, beaches, forts, temples, national parks.
    # When any of these are detected in a message, we treat it as a place query
    # and look it up via Wikipedia automatically.
    INDIA_PLACES = {
        # States & Union Territories
        "states": [
            "andhra pradesh", "arunachal pradesh", "assam", "bihar",
            "chhattisgarh", "goa", "gujarat", "haryana", "himachal pradesh",
            "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra",
            "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab",
            "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura",
            "uttar pradesh", "uttarakhand", "west bengal",
            "andaman and nicobar", "chandigarh", "dadra and nagar haveli",
            "daman and diu", "delhi", "jammu and kashmir", "ladakh",
            "lakshadweep", "puducherry",
        ],
        # Major Cities & State Capitals
        "cities": [
            "mumbai", "delhi", "bangalore", "bengaluru", "hyderabad", "chennai",
            "kolkata", "pune", "ahmedabad", "jaipur", "surat", "lucknow",
            "kanpur", "nagpur", "indore", "thane", "bhopal", "visakhapatnam",
            "vizag", "patna", "vadodara", "ghaziabad", "ludhiana", "agra",
            "nashik", "faridabad", "meerut", "rajkot", "kalyan", "vasai",
            "varanasi", "srinagar", "aurangabad", "dhanbad", "amritsar",
            "navi mumbai", "allahabad", "prayagraj", "ranchi", "howrah",
            "coimbatore", "jabalpur", "gwalior", "vijayawada", "jodhpur",
            "madurai", "raipur", "kota", "guwahati", "chandigarh", "solapur",
            "hubballi", "dharwad", "bareilly", "moradabad", "mysuru", "mysore",
            "gurgaon", "gurugram", "aligarh", "jalandhar", "tiruchirappalli",
            "trichy", "bhubaneswar", "salem", "mira bhayandar", "thiruvananthapuram",
            "trivandrum", "warangal", "guntur", "bhiwandi", "saharanpur",
            "gorakhpur", "bikaner", "amravati", "noida", "jamshedpur",
            "bhilai", "cuttack", "firozabad", "kochi", "cochin", "bhavnagar",
            "dehradun", "durgapur", "asansol", "nanded", "kolhapur", "ajmer",
            "akola", "gulbarga", "kalaburagi", "jamnagar", "ujjain", "loni",
            "siliguri", "jhansi", "ulhasnagar", "mangalore", "mangaluru",
            "malegaon", "gaya", "tiruppur", "davanagere", "kozhikode",
            "calicut", "akbarpur", "kasaragod", "kurnool", "bokaro",
            "bellary", "ballari", "patiala", "gopalpur", "pasighat",
            "agartala", "imphal", "shillong", "aizawl", "kohima",
            "itanagar", "dispur", "gangtok", "silvassa", "daman", "diu",
            "kavaratti", "port blair", "panaji", "shimla", "jammu",
        ],
        # Famous Tourist Destinations, Hill Stations, Beaches, Heritage Sites
        "tourist": [
            # Hill Stations
            "manali", "shimla", "ooty", "udhagamandalam", "darjeeling",
            "mussoorie", "nainital", "kodakodai", "kodaikanal", "munnar",
            "coorg", "madikeri", "mahabaleshwar", "lonavala", "khandala",
            "matheran", "dalhousie", "kasauli", "chail", "mcleod ganj",
            "dharamshala", "kullu", "solang valley", "spiti", "lahaul",
            "lansdowne", "chakrata", "almora", "ranikhet", "mukteshwar",
            "auli", "chopta", "tungnath", "kedarnath", "badrinath",
            "gangotri", "yamunotri", "haridwar", "rishikesh",
            "chikmagalur", "wayanad", "valparai", "yercaud", "coonoor",
            "pelling", "ravangla", "namchi", "lachung", "lachen",
            "tawang", "ziro", "dirang", "bomdila",
            # Beaches
            "goa", "palolem", "baga", "anjuna", "calangute", "vagator",
            "varkala", "kovalam", "alappuzha", "alleppey", "muzhappilangad",
            "marina beach", "mahabalipuram", "mamallapuram", "pondicherry",
            "puducherry", "rameswaram", "kanyakumari", "digha", "puri",
            "konark", "gopalpur", "mandarmani", "tarkarli", "murud",
            "kashid", "alibaug", "ganpatipule", "sindhudurg",
            "dwarka", "somnath", "diu", "mandvi", "ahmedpur mandvi",
            "lakshadweep", "andaman", "havelock", "neil island",
            # Heritage & Historical
            "agra", "taj mahal", "fatehpur sikri", "khajuraho", "sanchi",
            "hampi", "pattadakal", "badami", "aihole", "belur", "halebidu",
            "hoysala", "lepakshi", "mahabalipuram", "thanjavur", "tanjore",
            "madurai", "rameswaram", "tirupati", "tiruvannamalai",
            "ajanta", "ellora", "elephanta", "mandu", "orchha", "gwalior",
            "jaisalmer", "jodhpur", "udaipur", "pushkar", "ranthambore",
            "chittorgarh", "amber fort", "mehrangarh", "hawa mahal",
            "india gate", "qutub minar", "red fort", "humayun's tomb",
            "golden temple", "amritsar", "wagah border",
            "varanasi", "sarnath", "bodhgaya", "nalanda", "bodh gaya",
            "vrindavan", "mathura", "haridwar", "rishikesh", "dwarka",
            "shirdi", "nashik", "trimbakeshwar", "pandharpur",
            "kolhapur", "solapur", "aurangabad",
            # Nature & Wildlife
            "kaziranga", "jim corbett", "corbett", "ranthambore",
            "kanha", "bandhavgarh", "pench", "tadoba", "nagzira",
            "sundarbans", "periyar", "nagarhole", "bandipur", "mudumalai",
            "sariska", "bharatpur", "keoladeo", "gir", "velavadar",
            "great rann of kutch", "rann of kutch", "kutch",
            "valley of flowers", "roopkund", "hemkund sahib",
            "dzukou valley", "keibul lamjao", "loktak",
            "lonar lake", "pangong lake", "tsomgo lake", "dal lake",
            "chilika lake", "wular lake",
            # Adventure & Spiritual
            "leh", "ladakh", "nubra valley", "pangong", "zanskar",
            "khardung la", "magnetic hill", "shanti stupa",
            "mcleodganj", "triund", "bhrigu lake", "hampta pass",
            "rohtang pass", "jalori pass", "chandrakhani pass",
            "har ki dun", "sandakphu", "goecha la", "dzongri",
            "majuli", "cherrapunji", "mawsynram", "dawki",
            "double decker root bridge", "nohkalikai falls",
            "athirappilly", "dudhsagar", "jog falls",
            "raja ampat gokarna", "gokarna", "murdeshwar",
        ]
    }

    # Build a flat set for fast lookup
    ALL_INDIA_PLACES = set()
    for category_places in INDIA_PLACES.values():
        for place in category_places:
            ALL_INDIA_PLACES.add(place)

    def _wiki_lookup(query, sentences=3):
        """
        Fetch Wikipedia summary by direct title.
        Returns (title, extract) or (None, None).
        """
        try:
            search_q = uparse.quote(query.title())
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{search_q}"
            req = urllib.request.Request(url, headers={"User-Agent": "TripWise/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json_lib.loads(resp.read().decode())
            extract = data.get("extract", "")
            title = data.get("title", query.title())
            wtype = data.get("type", "")
            if extract and len(extract) > 60 and wtype != "disambiguation":
                short = ". ".join(extract.split(". ")[:sentences]) + "."
                return title, short
        except Exception:
            pass
        return None, None

    def _wiki_search(query, sentences=3):
        """
        Search Wikipedia using the OpenSearch API — works for ANY place,
        including rural areas, villages, talukas, tehsils, districts.
        Returns (title, extract) or (None, None).
        """
        try:
            # Step 1: OpenSearch to find the best matching article title
            search_q = uparse.quote(query + " India")
            search_url = (f"https://en.wikipedia.org/w/api.php"
                          f"?action=opensearch&search={search_q}&limit=1&namespace=0&format=json")
            req = urllib.request.Request(search_url, headers={"User-Agent": "TripWise/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                results = json_lib.loads(resp.read().decode())
            # results = [query, [titles], [descriptions], [urls]]
            if results and len(results) > 1 and results[1]:
                found_title = results[1][0]
                # Step 2: Get the full summary of that article
                title, extract = _wiki_lookup(found_title, sentences)
                if title and extract:
                    return title, extract
        except Exception:
            pass
        # Fallback: try direct lookup without " India" appended
        return _wiki_lookup(query, sentences)

    def _format_wiki_response(title, extract, extra_tip=""):
        resp = f"🌐 <b>{title}</b><br><br>{extract}"
        if extra_tip:
            resp += f"<br><br>{extra_tip}"
        resp += "<br><br><i>Source: Wikipedia. Ask me anything else about this place!</i>"
        return resp

    m = message.lower().strip()

    # ─── INTENT: Greetings ───
    greet_words = ["hello", "hi", "hey", "good morning", "good evening", "good afternoon",
                   "namaste", "hola", "sup", "wassup", "howdy"]
    if any(m.startswith(w) or m == w for w in greet_words):
        import datetime
        hour = datetime.datetime.now().hour
        tod = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
        return (f"{tod}! I'm your AI Travel Assistant 🌍 — I can answer travel questions, "
                "give safety tips, find your location, suggest budgets, explain destinations, "
                "and much more. Just ask me anything!")

    # ─── INTENT: Emergency ───
    if any(w in m for w in ["emergency", "danger", "sos", "help me", "accident", "injured",
                             "bleeding", "fire", "flood", "earthquake", "stuck", "stranded"]):
        return ("⚠️ <b>Emergency Detected</b><br>Stay calm. Here are universal numbers:<br>"
                "<ul><li><b>India — Police:</b> 100 / 112</li>"
                "<li><b>India — Ambulance:</b> 108</li>"
                "<li><b>India — Fire:</b> 101</li>"
                "<li><b>International:</b> 911 or 999</li>"
                "<li><b>Women Helpline (India):</b> 1091</li></ul>"
                "Share your GPS location with emergency services immediately. "
                "If you are safe, use our Live Tracker to share your position with trusted contacts.")

    # ─── INTENT: My Location ───
    if any(w in m for w in ["where am i", "my location", "find me", "current location", "gps", "coordinates"]):
        return "CMD::LOCATE_ME"

    # ─── AUTO PLACE DETECTOR ───────────────────────────────────────────────────
    # If the message contains ANY known Indian place name, auto-fetch Wikipedia.
    # This handles queries like:
    #   "nashik"  |  "nashik tourism"  |  "visit nashik"  |  "nashik trip"
    #   "manali weather"  |  "leh ladakh"  |  "goa in december"
    # It checks for the LONGEST matching place name first to avoid partial matches.
    detected_place = None
    sorted_places = sorted(ALL_INDIA_PLACES, key=len, reverse=True)  # longest first
    for place in sorted_places:
        if place in m:
            # Make sure it's a standalone word/phrase, not inside another word
            # e.g. avoid matching "goa" inside "goalpara"
            idx = m.find(place)
            before_ok = (idx == 0 or not m[idx-1].isalpha())
            after_ok = (idx + len(place) >= len(m) or not m[idx + len(place)].isalpha())
            if before_ok and after_ok:
                detected_place = place
                break

    if detected_place:
        # Determine what the user wants to know about this place
        weather_words = ["weather", "season", "when", "best time", "climate",
                         "monsoon", "summer", "winter", "rain", "cold", "hot", "temperature"]
        safe_words = ["safe", "safety", "dangerous", "crime", "security"]
        food_words = ["food", "dish", "eat", "cuisine", "famous food", "local food", "specialty"]
        budget_words = ["budget", "cost", "cheap", "expensive", "money", "spend", "afford"]
        how_to_reach = ["reach", "get to", "go to", "travel to", "how far", "distance",
                        "flight", "train", "bus", "route", "from mumbai", "from delhi",
                        "from pune", "from bangalore", "from hyderabad"]
        things_to_do = ["things to do", "what to do", "activities", "places to see",
                        "places to visit", "attractions", "sightseeing", "tourism"]

        if any(w in m for w in weather_words):
            title, extract = _wiki_search(detected_place)
            tip = (f"☀️ <b>Best Season to Visit {detected_place.title()}:</b><br>"
                   "Oct–Mar: ideal for most of India — "
                   "Hill stations: May–Jun & Sep–Oct — "
                   "Beaches: Nov–Feb — "
                   "North-East: Oct–Apr. Always check the IMD forecast before travel.")
            if title and extract:
                return _format_wiki_response(title, extract, tip)
            return tip

        if any(w in m for w in safe_words):
            title, extract = _wiki_search(detected_place)
            tip = (f"🛡️ <b>{detected_place.title()} Safety:</b> Generally safe for tourists. "
                   "Always keep ID copies, use official transport, avoid isolated areas at night, "
                   "and share your live location with a trusted contact using our Live Tracker.")
            if title and extract:
                return _format_wiki_response(title, extract, tip)
            return tip

        if any(w in m for w in food_words):
            title, extract = _wiki_search(detected_place + " cuisine")
            if not title:
                title, extract = _wiki_search(detected_place)
            tip = f"🍛 Ask me 'find nearest restaurant' to get a Google Maps link for food in {detected_place.title()}!"
            if title and extract:
                return _format_wiki_response(title, extract, tip)
            return f"🍛 {detected_place.title()} has a rich food culture. Use 'Find nearest restaurant' to get directions!"

        if any(w in m for w in how_to_reach):
            title, extract = _wiki_search(detected_place)
            tip = (f"✈️ <b>How to reach {detected_place.title()}:</b><br>"
                   "Flights: Skyscanner / MakeMyTrip<br>"
                   "Train: Book on IRCTC (irctc.co.in)<br>"
                   "Bus: MSRTC / KSRTC / RedBus<br>"
                   "Cab: Ola / Uber from nearest major city")
            if title and extract:
                return _format_wiki_response(title, extract, tip)
            return tip

        if any(w in m for w in budget_words):
            title, extract = _wiki_search(detected_place)
            tip = (f"💰 <b>Budget for {detected_place.title()}:</b><br>"
                   "₹800–1,500/day (budget backpacker) | ₹2,500–5,000/day (mid-range) | ₹8,000+/day (luxury)<br>"
                   "Use the <b>Budget Tracker</b> card to track your expenses precisely.")
            if title and extract:
                return _format_wiki_response(title, extract, tip)
            return tip

        if any(w in m for w in things_to_do):
            title, extract = _wiki_search(detected_place + " tourism")
            if not title:
                title, extract = _wiki_search(detected_place)
            tip = (f"🏛️ Use the <b>Nearby Attractions</b> card or ask me to 'find attractions near me' "
                   f"to discover places around {detected_place.title()}!")
            if title and extract:
                return _format_wiki_response(title, extract, tip)
            return tip

        # Default: fetch Wikipedia summary via search
        title, extract = _wiki_search(detected_place)
        if title and extract:
            return _format_wiki_response(title, extract,
                f"💡 Ask me: weather, safety, food, budget, things to do, or how to reach {detected_place.title()}!")
        # Wikipedia search also failed
        return (f"🗺️ I recognise <b>{detected_place.title()}</b> as an Indian destination! "
                f"Live details unavailable right now.<br><br>"
                f"Try: <i>'best time to visit {detected_place}'</i> or <i>'how to reach {detected_place}'</i>")

    # ─── INTENT: Destination Info (Wikipedia) — runs BEFORE nearby to avoid conflicts ───
    # Catches: "best time to visit X", "tell me about X", "what is X", etc.
    destination_triggers = [
        "tell me about", "what is", "where is", "information on", "info on",
        "facts about", "describe", "history of", "capital of",
        "famous for", "known for", "should i visit", "is it worth",
        "best time to visit", "best time to go to", "when to visit",
        "when should i visit", "when is the best time",
        "what to see in", "things to do in", "places to see in",
        "how is the weather in", "is it safe to visit",
        "how to reach", "how to go to", "how far is",
        "is it good to visit", "worth visiting",
    ]
    for pattern in destination_triggers:
        if pattern in m:
            query = m.split(pattern, 1)[-1].strip()
            if not query:
                query = m
            if len(query) > 2:
                # Use _wiki_search so it works for ANY place, even rural/obscure ones
                title, extract = _wiki_search(query)
                if title and extract:
                    return _format_wiki_response(title, extract,
                        f"💡 Ask me about weather, safety, budget, food, or how to reach {query.title()}!")
            dest = query or "that destination"
            return (f"I couldn't find data on <b>{dest.title()}</b> right now.<br><br>"
                    "Try: <i>'weather', 'safety tips', 'budget', 'how to reach'</i> for this destination.")

    # ─── INTENT: Nearby Facility Search ───
    # Only fires when the user explicitly asks for something NEAR them
    proximity_words = ["find", "nearest", "near me", "nearby", "close to me",
                       "where is the", "around me", "around here", "find me a",
                       "looking for a", "i need a", "need a", "locate"]
    has_proximity = any(p in m for p in proximity_words)

    facility_words = {
        "atm": "ATM", "bank": "bank", "hospital": "hospital", "clinic": "clinic",
        "pharmacy": "pharmacy", "chemist": "pharmacy", "doctor": "doctor",
        "petrol": "fuel station", "fuel": "fuel station", "gas station": "fuel station",
        "cafe": "cafe", "coffee": "cafe",
        "police": "police station", "mechanic": "garage", "garage": "garage",
        "parking": "parking", "toilet": "public toilet",
        "bathroom": "public toilet", "temple": "temple", "church": "church",
        "mosque": "mosque", "airport": "airport",
        "bus stand": "bus station", "bus stop": "bus station", "railway station": "railway station"
    }
    # These trigger ONLY if user says find/nearest/nearby
    facility_proximity_words = {
        "restaurant": "restaurant", "food": "restaurant", "eat": "restaurant",
        "hotel": "hotel", "stay": "hotel", "school": "school",
    }
    for keyword, facility_name in facility_words.items():
        if keyword in m:
            return f"CMD::FIND_NEARBY::{facility_name}"
    if has_proximity:
        for keyword, facility_name in facility_proximity_words.items():
            if keyword in m:
                return f"CMD::FIND_NEARBY::{facility_name}"

    # Explicit nearby attractions (NOT triggered by "visit" alone)
    if any(w in m for w in ["nearby attraction", "near attraction", "famous places near",
                             "things to do nearby", "places near me", "what to see near"]):
        return "CMD::NEARBY_ATTRACTIONS"

    # ─── INTENT: Budget & Cost ───
    if any(w in m for w in ["budget", "cost", "expense", "money", "spend", "cheap", "expensive",
                             "affordable", "price", "rupee", "inr", "usd", "currency", "exchange"]):
        if "currency" in m or "exchange" in m or "usd" in m or "dollar" in m:
            return ("💱 <b>Currency Tips:</b><br>"
                    "<ul><li>Always exchange money at official banks or airport kiosks — avoid street exchanges.</li>"
                    "<li>Notify your bank before traveling internationally to avoid card blocks.</li>"
                    "<li>Use apps like <b>XE Currency</b> for live exchange rates.</li>"
                    "<li>Carry some local cash for areas without card acceptance.</li></ul>")
        return ("💰 Use the <b>Budget Tracker</b> card on your dashboard to plan expenses.<br><br>"
                "Quick Budget Guidelines for India:<br>"
                "<ul><li><b>Budget backpacker:</b> ₹800–1500/day</li>"
                "<li><b>Mid-range traveler:</b> ₹2000–5000/day</li>"
                "<li><b>Luxury traveler:</b> ₹8000+/day</li></ul>"
                "Costs include accommodation, food, transport and entry fees.")

    # ─── INTENT: Transport ───
    if any(w in m for w in ["transport", "travel by", "how to reach", "cab", "auto", "taxi",
                             "ola", "uber", "bus", "metro", "train", "flight", "airplane"]):
        if any(w in m for w in ["flight", "airplane", "fly"]):
            return ("✈️ <b>Flight Travel Tips:</b><br>"
                    "<ul><li>Book 6-8 weeks in advance for best prices.</li>"
                    "<li>Use <b>Google Flights</b> or <b>Skyscanner</b> to compare fares.</li>"
                    "<li>Always arrive 2 hours before domestic, 3 hours before international flights.</li>"
                    "<li>Keep digital copies of your boarding pass and ID.</li></ul>")
        if any(w in m for w in ["train", "railway"]):
            return ("🚆 <b>Train Travel in India:</b><br>"
                    "<ul><li>Book via <b>IRCTC</b> — the official railway booking site.</li>"
                    "<li>Rajdhani and Shatabdi are fastest intercity options.</li>"
                    "<li>Book at least 2-4 weeks before for confirmed seats.</li>"
                    "<li>Carry your booking ID and government ID for TTE verification.</li></ul>")
        return ("🚗 <b>Local Transport Guide:</b><br>"
                "<ul><li><b>App Cabs:</b> Ola, Uber, Rapido — always safer than unmetered autos.</li>"
                "<li><b>Metro:</b> Available in Mumbai, Delhi, Bangalore, Hyderabad, Chennai.</li>"
                "<li><b>Auto-rickshaw:</b> Insist on meter or fix price before boarding.</li>"
                "<li><b>Bus:</b> KSRTC/MSRTC for interstate — very affordable.</li></ul>")

    # ─── INTENT: Safety ───
    if any(w in m for w in ["safe", "safety", "secure", "scam", "fraud", "theft", "pickpocket",
                             "unsafe", "crime", "danger zone", "precaution"]):
        return ("🛡️ <b>Travel Safety Checklist:</b><br>"
                "<ul><li>Keep digital copies of passport/visa on cloud storage.</li>"
                "<li>Share your live location with a trusted contact.</li>"
                "<li>Use our <b>Live Tracker</b> to stay connected.</li>"
                "<li>Avoid displaying expensive items or large amounts of cash.</li>"
                "<li>Use a VPN on public Wi-Fi — airports, cafes, hotels.</li>"
                "<li>Research local scams at your destination before arriving.</li>"
                "<li>Trust your gut — if something feels wrong, leave.</li></ul>")

    # ─── INTENT: Packing / Luggage ───
    if any(w in m for w in ["pack", "packing", "luggage", "bag", "carry", "essentials", "what to bring"]):
        return ("🧳 <b>Smart Packing List:</b><br>"
                "<ul><li>📄 ID proof + passport + visa (digital + physical copy)</li>"
                "<li>💊 Personal medications + basic first aid kit</li>"
                "<li>🔌 Universal power adapter</li>"
                "<li>💦 Reusable water bottle</li>"
                "<li>🧴 Sunscreen + insect repellent</li>"
                "<li>📱 Power bank (min. 10,000 mAh)</li>"
                "<li>🧥 Light jacket/layer (even for hot destinations)</li>"
                "<li>💳 Multiple payment methods (cash + 2 cards)</li></ul>")

    # ─── INTENT: Visa / Documentation ───
    if any(w in m for w in ["visa", "passport", "document", "id proof", "permit"]):
        return ("📋 <b>Travel Document Checklist:</b><br>"
                "<ul><li>Valid passport (6+ months validity required for most countries).</li>"
                "<li>Check visa requirements at your destination's embassy website.</li>"
                "<li>India offers <b>e-Visa</b> for 150+ countries at <b>indianvisaonline.gov.in</b></li>"
                "<li>Carry 4 passport-size photos for emergency use.</li>"
                "<li>Keep scanned copies on email/cloud: passport, visa, tickets, insurance.</li></ul>")

    # ─── INTENT: Weather ───
    if any(w in m for w in ["weather", "rain", "monsoon", "summer", "winter", "temperature",
                             "climate", "season", "umbrella", "hot", "cold"]):
        return ("🌤️ <b>Weather & Season Tips:</b><br>"
                "<ul><li>India has 3 main seasons: Summer (Mar–Jun), Monsoon (Jul–Sep), Winter (Oct–Feb).</li>"
                "<li>Best time to visit most hill stations: <b>May–June</b> and <b>October–November</b>.</li>"
                "<li>Rajasthan is best Oct–Feb. Kerala / Goa is best Nov–Feb.</li>"
                "<li>Always check the <b>IMD (India Meteorological Department)</b> forecast before trekking.</li>"
                "<li>Pack a light rain cover for your backpack during monsoon travel.</li></ul>")

    # ─── INTENT: Food & Cuisine ───
    if any(w in m for w in ["food", "eat", "cuisine", "restaurant", "street food", "vegetarian",
                             "vegan", "halal", "local dish", "hungry"]):
        return ("🍛 <b>Eating Well on the Road:</b><br>"
                "<ul><li>Street food is delicious but choose busy stalls — high turnover = fresh food.</li>"
                "<li>South India: Must try <b>dosa, idli, filter coffee</b>.</li>"
                "<li>North India: <b>butter chicken, aloo paratha, lassi</b>.</li>"
                "<li>West India: <b>vada pav, pav bhaji, dhokla</b>.</li>"
                "<li>Use <b>Zomato</b> or <b>Swiggy</b> apps for delivery or nearby restaurant ratings.</li>"
                "<li>Carry oral rehydration salts (ORS) in case of food sensitivity.</li></ul>")

    # ─── INTENT: Accommodation ───
    if any(w in m for w in ["hotel", "hostel", "stay", "accommodation", "airbnb", "lodge", "resort",
                             "guesthouse", "room", "bnb", "book room"]):
        return ("🏨 <b>Smart Accommodation Booking:</b><br>"
                "<ul><li>Book via <b>Booking.com</b>, <b>Agoda</b>, or <b>MakeMyTrip</b> for verified stays.</li>"
                "<li>Read <b>recent reviews</b> (last 3 months) — not just the overall score.</li>"
                "<li>For budget options, try <b>OYO</b> or local guesthouses.</li>"
                "<li>Always confirm check-in/check-out times and cancellation policy.</li>"
                "<li>Use our <b>Budget Tracker</b> to allocate accommodation costs accurately.</li></ul>")

    # ─── INTENT: Health / Medical ───
    if any(w in m for w in ["sick", "ill", "medicine", "doctor", "health", "fever", "food poisoning",
                             "insurance", "medical", "first aid", "vaccine", "vaccination"]):
        return ("🏥 <b>Travel Health Guide:</b><br>"
                "<ul><li>Get travel insurance before any international trip — it covers medical emergencies.</li>"
                "<li>Carry a basic first-aid kit: bandages, antiseptic, antacids, ORS, paracetamol.</li>"
                "<li>Check recommended vaccines for your destination via <b>WHO Travel Advice</b> portal.</li>"
                "<li>Drink only sealed packaged water in unfamiliar regions.</li>"
                "<li>India Ambulance: <b>108</b> | Tourist Helpline: <b>1800-111-363</b></li></ul>")

    # ─── INTENT: Internet / SIM ───
    if any(w in m for w in ["sim", "internet", "data", "wifi", "network", "roaming", "4g", "5g", "connect"]):
        return ("📡 <b>Staying Connected While Traveling:</b><br>"
                "<ul><li>Buy a local prepaid SIM at the airport — much cheaper than roaming.</li>"
                "<li>In India, <b>Jio</b> and <b>Airtel</b> offer the best nationwide coverage.</li>"
                "<li>For international travel, consider an <b>eSIM</b> from Airalo or Google Fi.</li>"
                "<li>Always use a <b>VPN</b> on public Wi-Fi to protect passwords and data.</li></ul>")

    # ─── INTENT: Destination Info (Wikipedia Fallback) — FINAL CATCH ───
    # This catches anything left with explicit destination patterns like "tell me about X"
    # (The primary destination check is earlier in the function)
    pass  # Already handled above


    # ─── INTENT: Trip Planner ───
    if any(w in m for w in ["plan trip", "plan a trip", "trip plan", "itinerary", "travel plan",
                             "where should i go", "destination suggest"]):
        return ("🗺️ To create your personalized travel plan, click the <b>Plan Trip</b> card on your dashboard!<br><br>"
                "Our AI will calculate:<br>"
                "<ul><li>Estimated total budget based on distance + duration</li>"
                "<li>Best transport modes for your journey</li>"
                "<li>Day-wise cost breakdown</li></ul>"
                "Or tell me your destination and I'll give you a quick overview!")

    # ─── INTENT: Live Tracker ───
    if any(w in m for w in ["live track", "track me", "live location", "share location", "route", "navigation"]):
        return ("📍 Click the <b>Live Tracker</b> card on your dashboard to activate real-time GPS tracking.<br><br>"
                "Features include:<br>"
                "<ul><li>Real-time position on an interactive map</li>"
                "<li>ML-powered ETA calculation based on traffic patterns</li>"
                "<li>Route deviation alerts</li></ul>")

    # ─── INTENT: What can you do / Help ───
    if any(w in m for w in ["help", "what can you", "what do you", "features", "menu", "commands", "capability"]):
        return ("🤖 <b>I can answer questions on:</b><br>"
                "<ul><li>📍 <b>Your location</b> — 'where am I?'</li>"
                "<li>🏥 <b>Nearby places</b> — 'find nearest hospital'</li>"
                "<li>⚠️ <b>Emergencies</b> — 'I need help'</li>"
                "<li>🛡️ <b>Safety tips</b></li>"
                "<li>💰 <b>Budget & costs</b></li>"
                "<li>🚗 <b>Transport options</b></li>"
                "<li>🌤️ <b>Weather & seasons</b></li>"
                "<li>🍛 <b>Food recommendations</b></li>"
                "<li>🏨 <b>Accommodation tips</b></li>"
                "<li>📋 <b>Visa & documents</b></li>"
                "<li>🧳 <b>Packing lists</b></li>"
                "<li>🌐 <b>Info on any destination</b> — 'tell me about Goa'</li></ul>"
                "Just ask me anything travel-related!")

    # ─── INTENT: Appreciation ───
    if any(w in m for w in ["thanks", "thank you", "thx", "nice", "good", "great", "awesome",
                             "excellent", "perfect", "cool", "helpful", "love it"]):
        return "You're very welcome! Happy travels! 🌍✈️ Ask me anything else anytime."

    if any(w in m for w in ["bye", "goodbye", "cya", "see you", "later", "exit", "close"]):
        return "Safe travels! Come back whenever you need travel help. Bon voyage! ✈️🌟"

    # ─── FALLBACK: Universal Wikipedia Search ──────────────────────────────────
    # This is the LAST resort — catches any place, topic, or question
    # that wasn't handled by any intent above.
    # _wiki_search uses OpenSearch so it works for:
    #   - Rural areas / villages / talukas / tehsils
    #   - Uncommon spellings  
    #   - Monuments, rivers, lakes, temples not in static list
    #   - Any factual travel question
    query_clean = m.strip()[:80]  # limit length
    title, extract = _wiki_search(query_clean, sentences=2)
    if title and extract:
        return (f"🌐 <b>{title}</b><br><br>{extract}<br><br>"
                "<i>Source: Wikipedia. Ask me about weather, budget, safety or how to reach any Indian destination!</i>")

    # Absolute final fallback — nothing matched at all
    return ("I'm your <b>AI Travel Assistant</b> — ask me anything about India! For example:<br>"
            "<ul><li>'Tell me about Igatpuri'</li>"
            "<li>'Best time to visit Trimbakeshwar'</li>"
            "<li>'Find nearest hospital'</li>"
            "<li>'Budget tips for Goa'</li>"
            "<li>'Is Nashik safe?'</li></ul>"
            "I can look up <b>any place in India</b> instantly!")


if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'])