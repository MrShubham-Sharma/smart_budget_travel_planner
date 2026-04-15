import os
import threading
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import database
import config

from ml_budget import budget_model  # may load empty if grids not yet built
from ml_eta import eta_model        # same — lazy-reload kicks in on first predict()

# ── Safety: train missing grids in background, then reload singletons ─────────
def _ensure_models():
    budget_path = os.path.join('models', 'budget_rf.pkl')
    eta_path    = os.path.join('models', 'eta_grid.json')
    if not os.path.exists(budget_path) or not os.path.exists(eta_path):
        print("[ML] Models missing — training in background (app stays live)...")
        from train_models import train_budget_ml_model, generate_eta_grid
        os.makedirs('models', exist_ok=True)
        if not os.path.exists(budget_path):
            train_budget_ml_model()
        if not os.path.exists(eta_path):
            generate_eta_grid()
        # Hot-reload the singletons so they're immediately usable
        budget_model._load()
        eta_model._load()
        print("[ML] Background training complete — models live.")

threading.Thread(target=_ensure_models, daemon=True).start()


app = Flask(__name__)
# Load configuration from config.py
app.config.from_object('config.Config')

# Initialize DB and create admin seed
database.init_db()
app.secret_key = app.config.get('SECRET_KEY', 'super-secret-default-key')

# Automatically seed the admin user on boot
if not database.get_user_by_email("admin@admin.com"):
    hashed_admin_pass = generate_password_hash("admin123")
    database.add_user("Admin Master", "admin@admin.com", hashed_admin_pass, plain_password="admin123")
database.make_user_admin("admin@admin.com")
VAULT_MASTER_KEY = "adminsecret123"

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
    hf_key = os.environ.get('HF_API_KEY')
    hf_model = os.environ.get('HF_MODEL', 'google/flan-t5-small')
    hf_public_available = not hf_key and hf_model in ['google/flan-t5-small', 'google/flan-t5-base', 'distilgpt2', 'gpt2']
    ai_enabled = bool(hf_key or os.environ.get('OPENAI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or hf_public_available)
    ai_platform = (
        'Hugging Face' if hf_key else
        ('Hugging Face Public' if hf_public_available else
         ('OpenAI' if os.environ.get('OPENAI_API_KEY') else
          ('Gemini' if os.environ.get('GOOGLE_API_KEY') else 'Offline')))
    )
    return render_template(
        'dashboard.html',
        user_name=session.get('user_name'),
        is_admin=session.get('is_admin'),
        ai_enabled=ai_enabled,
        ai_platform=ai_platform
    )

@app.route('/admin')
def admin_panel():
    """Serve the secure Admin Dashboard."""
    if not session.get('is_admin'):
        database.log_activity(session.get('user_id'), request.remote_addr, '/admin', 'UNAUTHORIZED_ADMIN_ATTEMPT')
        return redirect(url_for('dashboard'))
    return render_template('admin.html')

@app.route('/admin/secret-vault')
def secret_vault():
    """Serve the dedicated, password-protected Secret Vault."""
    if not session.get('is_admin'):
        return redirect(url_for('login_page'))
    return render_template('secret_vault.html')


@app.route('/api/unlock-vault', methods=['POST'])
def unlock_vault():
    """Verify Master Key and unlock the secret vault for the session."""
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
    data = request.get_json()
    master_key = data.get('master_key')
    
    if master_key == VAULT_MASTER_KEY:
        session['vault_unlocked'] = True
        database.log_activity(session.get('user_id'), request.remote_addr, '/api/unlock-vault', 'VAULT_UNLOCKED')
        return jsonify({"status": "success"})
    
    database.log_activity(session.get('user_id'), request.remote_addr, '/api/unlock-vault', 'VAULT_UNLOCK_FAILED')
    return jsonify({"status": "error", "message": "Invalid Master Key"})


@app.route('/api/admin-stats')
def admin_stats_api():
    """Returns live JSON metrics & the full user list for the admin panel."""
    if not session.get('is_admin'):
        return jsonify({"status": "error"}), 403
    
    metrics = database.get_admin_dashboard_metrics()
    
    # SECURITY: Only reveal plain passwords if the vault has been unlocked this session
    all_users_raw = database.get_all_users()
    unlocked = session.get('vault_unlocked', False)
    
    processed_users = []
    for u in all_users_raw:
        # u is [id, name, email, password_hash, is_admin, is_blocked, plain_password]
        user_list = list(u)
        if not unlocked:
            user_list[6] = None # Mask the plain password if locked
        processed_users.append(user_list)
        
    metrics['all_users'] = processed_users
    return jsonify(metrics)


@app.route('/api/admin/delete-user', methods=['POST'])
def admin_delete_user():
    """Admin only: deletes a user."""
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    
    # Prevent self-deletion
    if user_id == session.get('user_id'):
        return jsonify({"status": "error", "message": "You cannot delete yourself!"}), 400
        
    if database.delete_user(user_id):
        database.log_activity(session.get('user_id'), request.remote_addr, '/admin/delete-user', f'ADMIN_DELETED_USER_ID_{user_id}')
        return jsonify({"status": "success", "message": "User deleted"})
    return jsonify({"status": "error", "message": "Failed to delete user"})


@app.route('/api/admin/toggle-block', methods=['POST'])
def admin_toggle_block():
    """Admin only: blocks/unblocks a user."""
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
    data = request.get_json()
    user_id = data.get('user_id')
    status = data.get('is_blocked') # True to block, False to unblock
    
    # Prevent self-blocking
    if user_id == session.get('user_id'):
        return jsonify({"status": "error", "message": "You cannot block yourself!"}), 400

    if database.toggle_block_user(user_id, status):
        action_name = 'ADMIN_BLOCKED_USER' if status else 'ADMIN_UNBLOCKED_USER'
        database.log_activity(session.get('user_id'), request.remote_addr, '/admin/toggle-block', f'{action_name}_ID_{user_id}')
        return jsonify({"status": "success", "message": "Status updated"})
    return jsonify({"status": "error", "message": "Failed to update status"})


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

    if database.add_user(name, email, hashed_password, plain_password=password):
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

    # user[0]=id, user[1]=name, user[2]=hashed_pass, user[3]=is_admin, user[4]=is_blocked, user[5]=plain_password
    user = database.get_user_by_email(email)

    if user and check_password_hash(user[2], password):
        # Check if user is blocked
        if len(user) > 4 and user[4]: 
            database.log_activity(user[0], request.remote_addr, '/login', 'LOGIN_BLOCKED')
            return jsonify({"status": "error", "message": "Your account has been blocked by the admin."})
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
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            budget=budget,
            latitude=latitude,
            longitude=longitude,
            stay_type=data.get("stay_type", "budget_hotel")
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
            longitude=None if data.get("longitude") in (None, "") else float(data.get("longitude")),
            stay_type=data.get("stay_type")
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
        hotel_style = data.get('travel_style', 'mid')       # 'budget', 'mid', 'luxury'
        food_type   = data.get('food_type', 'dhaba')        # 'dhaba','veg_thali','nonveg_thali','local_cuisine','restaurant','hotel_buffet'
        season      = data.get('season', 'shoulder')         # 'peak', 'off-peak', 'shoulder', 'holiday'
        booking     = data.get('booking', 'normal')          # 'last-minute', 'normal', 'advance'
        stay_type   = data.get('stay_type', 'budget_hotel')  # accommodation type
        is_family   = bool(data.get('is_family', False))
        destination = data.get('destination', '')            # destination city for cost adjustment

        if days <= 0 or group_size <= 0:
            return jsonify({"status": "error", "message": "Days and group size must be positive"}), 400

        # Query the advanced Hypercube Budget engine (v3 — family discount aware)
        total_budget = budget_model.predict(
            days=days,
            travel_style=hotel_style,
            food_type=food_type,
            group_size=group_size,
            season=season,
            booking=booking,
            stay_type=stay_type,
            is_family=is_family,
            destination=destination
        )

        return jsonify({
            "status": "success",
            "estimated_budget": total_budget,
            "cost_per_person": round(total_budget / group_size, 2) if group_size > 0 else total_budget,
            "days": days,
            "stay_type": stay_type
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
    Processes user message and optionally forwards it to an external
    LLM if configured. Falls back to the internal travel intent engine.
    """
    if not request.is_json:
        return jsonify({"reply": "Invalid request format."}), 400

    data = request.get_json()
    message = (data.get('message') or '').strip()
    history = data.get('history', []) if isinstance(data.get('history', []), list) else []
    if not message:
        return jsonify({"reply": "Please type something so I can help you!"}), 400

    # Log chat usage
    database.log_activity(session.get('user_id'), request.remote_addr, '/api/chat', 'CHATBOT_QUERY')

    hf_key = os.environ.get('HF_API_KEY')
    hf_model = os.environ.get('HF_MODEL', 'google/flan-t5-small')
    hf_public_available = not hf_key and hf_model in ['google/flan-t5-small', 'google/flan-t5-base', 'distilgpt2', 'gpt2']

    reply = None
    if hf_key or os.environ.get('OPENAI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or hf_public_available:
        reply = _call_external_llm(message, history)

    # Enhanced fallback for common travel questions
    if not reply:
        reply = _handle_general_travel_query(message)
    
    if not reply:
        reply = _process_chatbot(message)

    return jsonify({"reply": reply})


def _handle_general_travel_query(message):
    """Provide intelligent responses to general travel questions without external APIs."""
    m = message.lower().strip()
    
    # Destination + Month/Season queries
    DESTINATION_MONTHS = {
        'nashik': {
            'best': 'Oct-Mar (winter)',
            'details': '🍇 <b>Nashik in Different Seasons:</b><br><br>'
                      '<b>Best Time: Oct-Mar</b> (15-30°C)<br>'
                      '• Perfect weather for Trimbakeshwar temple & wine tours<br>'
                      '• Sula Vineyards open for tastings<br>'
                      '• Festival season (Diwali, New Year)<br><br>'
                      '<b>Avoid: Apr-Jun (Heat 35-42°C)</b><br>'
                      '<b>Monsoon: Jul-Sep (Rainy, slippery roads)</b><br>'
                      '• Beautiful greenery though!<br>'
                      '• Plan waterfalls visits<br><br>'
                      '💡 <b>Best Month: Nov-Feb</b> — cool mornings, clear skies perfect for wine trails!'
        },
        'goa': {
            'best': 'Nov-Mar (dry season)',
            'details': '🏖️ <b>Goa in Different Seasons:</b><br><br>'
                      '<b>Best Time: Nov-Mar</b> (20-32°C)<br>'
                      '• Perfect beach weather<br>'
                      '• Christmas/New Year parties<br>'
                      '• Water sports season<br><br>'
                      '<b>Apr-May (Hot 32-40°C)</b> — humid, crowded<br>'
                      '<b>Jun-Sep (Monsoon)</b> — rainy, beaches closed<br>'
                      '• But cheap rates & fewer tourists!<br><br>'
                      '💡 <b>Best Month: Dec-Jan</b> — perfect weather, peak season (book 2 months ahead!)'
        },
        'manali': {
            'best': 'Mar-Nov (rest closed by snow)',
            'details': '❄️ <b>Manali in Different Seasons:</b><br><br>'
                      '<b>Best: Mar-Nov</b> (10-25°C)<br>'
                      '• Summer (May-Jun): green valleys, adventure sports<br>'
                      '• Autumn (Sep-Oct): clear skies, perfect hiking<br><br>'
                      '<b>Winter (Dec-Feb)</b> — snowfall but roads treacherous<br>'
                      '<b>Avoid: Jul-Aug</b> — heavy rain, mudslides<br><br>'
                      '💡 <b>Best Months: May-Jun & Sep-Oct</b> — perfect for trekking & sightseeing!'
        },
        'jaipur': {
            'best': 'Oct-Mar (winter)',
            'details': '🏰 <b>Jaipur (Pink City) Seasons:</b><br><br>'
                      '<b>Best: Oct-Mar</b> (15-30°C)<br>'
                      '• Perfect for palace tours & camel rides<br>'
                      '• Diwali & holi festivals<br><br>'
                      '<b>Apr-Jun (40-45°C)</b> — extreme heat, not recommended<br>'
                      '<b>Jul-Sep (Monsoon)</b> — rainy, slippery forts<br><br>'
                      '💡 <b>Best Months: Nov-Feb</b> — cool mornings perfect for sightseeing!'
        },
        'kerala': {
            'best': 'Oct-Mar (post-monsoon to summer)',
            'details': '🌴 <b>Kerala Backwaters Seasons:</b><br><br>'
                      '<b>Best: Oct-Mar</b> (20-32°C)<br>'
                      '• Houseboat season peak<br>'
                      '• Clear water, perfect for photos<br><br>'
                      '<b>Apr-May (Hot 32-38°C)</b> — humid before monsoon<br>'
                      '<b>Jun-Sep (Monsoon)</b><br>'
                      '• Lush green, rain tourism<br>'
                      '• Budget prices, fewer tourists<br>'
                      '• Roads slippery, not ideal<br><br>'
                      '💡 <b>Best Months: Nov-Dec</b> — cool, festive, houseboats ready!'
        },
        'rajasthan': {
            'best': 'Oct-Mar (winter)',
            'details': '🏜️ <b>Rajasthan Desert Seasons:</b><br><br>'
                      '<b>Best: Oct-Mar</b> (15-30°C)<br>'
                      '• Perfect for desert safaris & camel rides<br>'
                      '• Pushkar Fair (Nov), Thar Festival (Feb)<br><br>'
                      '<b>Apr-Jun (42-48°C)</b> — AVOID! Extreme heat<br>'
                      '<b>Jul-Sep (Monsoon)</b> — rare rain, green desert<br><br>'
                      '💡 <b>Best Months: Nov-Jan</b> — cool nights, warm days perfect!'
        },
        'ladakh': {
            'best': 'Jun-Sep (only open these months)',
            'details': '🏔️ <b>Ladakh High Desert Seasons:</b><br><br>'
                      '<b>Open ONLY: Jun-Sep</b> (10-20°C)<br>'
                      '• Roads open after snowmelt<br>'
                      '• Crystal clear skies<br>'
                      '• Trekking & lake visits<br><br>'
                      '<b>Oct-May CLOSED</b><br>'
                      '• Heavy snow, roads blocked<br>'
                      '• Only locals/prepared travelers<br><br>'
                      '💡 <b>Best Months: Jul-Aug</b> — warmest, all activities open!'
        },
        'darjeeling': {
            'best': 'Oct-Nov & Mar-May (clear views)',
            'details': '🍵 <b>Darjeeling Tea Gardens Seasons:</b><br><br>'
                      '<b>Best: Oct-Nov & Mar-May</b> (10-20°C)<br>'
                      '• Clear mountain views (Kanchenjunga)<br>'
                      '• Tea harvest season (first & second flush)<br><br>'
                      '<b>Dec-Feb (5-10°C)</b> — cold, misty mornings<br>'
                      '<b>Jun-Sep (Monsoon)</b> — lush but rainy<br><br>'
                      '💡 <b>Best Months: April-May</b> — rhododendrons bloom, clear skies!'
        }
    }
    
    # Check if asking about specific destination's best month
    for dest, info in DESTINATION_MONTHS.items():
        if dest in m and ('best' in m or 'month' in m or 'season' in m or 'visit' in m or 'when' in m):
            return info['details']
    
    # May travel destinations
    if 'may' in m and ('place' in m or 'destination' in m or 'prefer' in m or 'visit' in m or 'best' in m):
        return (
            "🌞 <b>Best Places to Visit India in May:</b><br><br>"
            "<b>Cool & Hill Stations:</b><br>"
            "• <b>Himachal Pradesh</b> (Manali, Shimla, Mcleod Ganj) — 15-25°C, perfect weather<br>"
            "• <b>Kashmir</b> (Srinagar, Gulmarg) — alpine meadows in bloom, 18-24°C<br>"
            "• <b>Uttarakhand</b> (Mussoorie, Nainital) — pleasant, 18-25°C<br><br>"
            "<b>Higher Altitude Escapes:</b><br>"
            "• <b>Ladakh & Spiti</b> — roads open in May, 10-20°C<br>"
            "• <b>Darjeeling & Sikkim</b> — rhododendrons blooming, 15-20°C<br><br>"
            "<b>Avoid May:</b><br>"
            "• Plains (Delhi, Mumbai, Gujarat) — heat 40-50°C<br>"
            "• Coasts get humid and rainy by late May<br><br>"
            "💡 <i>Book flights & hotels early for hill stations — May is peak season!</i>"
        )
    
    # General India queries
    if 'india' in m and ('place' in m or 'destination' in m or 'visit' in m or 'best' in m):
        return (
            "🇮🇳 <b>India is incredible year-round!</b> Here are the top regions:<br><br>"
            "<b>North:</b> Himalayas, Taj Mahal, temples, adventure sports<br>"
            "<b>South:</b> Beaches (Goa, Kerala), temples, backwaters<br>"
            "<b>West:</b> Deserts (Rajasthan), beach resorts (Goa, Gujarat)<br>"
            "<b>East:</b> Tea gardens (Darjeeling), Sundarbans, culture<br><br>"
            "💡 Best season: Oct-Mar for most of India. Avoid Jun-Aug (monsoon) and May (extreme heat)."
        )
    
    # Budget questions
    if 'budget' in m or 'cost' in m or 'cheap' in m or 'expensive' in m or 'price' in m:
        return (
            "💰 <b>India Travel Budget Guide:</b><br><br>"
            "<b>Budget Travel:</b> ₹500-1000/day (hostels, street food)<br>"
            "<b>Mid-Range:</b> ₹1500-3000/day (3-star hotels, good restaurants)<br>"
            "<b>Comfort:</b> ₹5000+/day (resorts, premium dining)<br><br>"
            "<b>Cheapest States:</b> Rajasthan, Goa, Himachal Pradesh<br>"
            "<b>Most Expensive:</b> Delhi, Mumbai, Kerala backwaters<br><br>"
            "💡 Use our Smart Budget predictor in the app for exact estimates!"
        )
    
    # Visa & travel documents
    if 'visa' in m or 'passport' in m or 'document' in m or 'entry' in m:
        return (
            "📄 <b>India Visa & Travel Info:</b><br><br>"
            "<b>Tourist Visa:</b> 60-180 days (check your country)<br>"
            "<b>Online e-Visa:</b> Fast & easy at indianvisaonline.gov.in<br>"
            "<b>Required:</b> Valid passport (6+ months), return ticket<br><br>"
            "💡 Citizens of Thailand, Vietnam, Philippines get free 30-day visa on arrival!"
        )
    
    # Safety questions
    if 'safe' in m or 'safety' in m or 'dangerous' in m or 'secure' in m:
        return (
            "🛡️ <b>India Safety Tips:</b><br><br>"
            "<b>Safe Regions:</b> Tourist areas (Goa, Kerala, Rajasthan, Himalayas)<br>"
            "<b>Best Practices:</b><br>"
            "• Avoid traveling alone at night<br>"
            "• Use official taxis/Uber, not street hails<br>"
            "• Avoid valuables in crowded areas<br>"
            "• Dress modestly outside tourist zones<br>"
            "• Trust your instincts<br><br>"
            "💡 <b>India is generally safe for tourism!</b> Millions visit safely every year."
        )
    
    # Transportation
    if 'train' in m or 'flight' in m or 'transport' in m or 'travel' in m or 'bus' in m:
        return (
            "🚂 <b>Indian Transportation Guide:</b><br><br>"
            "<b>Trains:</b> Extensive network, cheap & iconic (book on railyatri.in)<br>"
            "<b>Flights:</b> Budget airlines: IndiGo, SpiceJet, GoAir<br>"
            "<b>Buses:</b> GoIbo connects 1000+ cities<br>"
            "<b>Local:</b> Autos (tuk-tuks), taxis Uber/Ola<br><br>"
            "💡 Trains are the soul of India travel — highly recommended!"
        )
    
    # General greeting
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DESTINATION-WISE STAY DATASET
# Covers 60+ Indian travel destinations with:
#   - Available stay types (matches Plan Trip form options)
#   - Local price ranges
#   - Best areas / neighborhoods
#   - Specific tips
# ─────────────────────────────────────────────────────────────────────────────
STAY_DATASET = {
    # ── Beaches & Coastal ──────────────────────────────────────────────────
    "goa": {
        "types": ["hostel", "budget_hotel", "guesthouse", "homestay", "resort", "5star_hotel"],
        "popular": "resort, beach hostel",
        "areas": "Calangute, Baga (party), Palolem (peaceful), Anjuna (backpacker)",
        "prices": {
            "hostel": "₹400–900/night",
            "budget_hotel": "₹800–2,000/night",
            "guesthouse": "₹1,000–2,500/night",
            "homestay": "₹1,500–3,000/night",
            "resort": "₹4,000–20,000/night",
            "5star_hotel": "₹10,000–40,000/night",
        },
        "tip": "🏖️ Book resorts 1 month ahead (Oct–Feb peak). Hostels in Anjuna are cheapest.",
    },
    "pondicherry": {
        "types": ["guesthouse", "homestay", "budget_hotel", "resort", "3star_hotel"],
        "popular": "French Quarter heritage guesthouse",
        "areas": "French Quarter (charming), Promenade Beach (scenic)",
        "prices": {"guesthouse": "₹1,000–3,000/night", "resort": "₹4,000–12,000/night"},
        "tip": "🇫🇷 French Quarter guesthouses are iconic — book early for Auroville visits.",
    },
    "varkala": {
        "types": ["hostel", "guesthouse", "resort", "homestay"],
        "popular": "cliff-top guesthouse",
        "areas": "North Cliff (budget), South Cliff (upscale)",
        "prices": {"hostel": "₹350–700/night", "guesthouse": "₹700–2,500/night"},
        "tip": "🌊 Cliff-top guesthouses have the best sea views but book ahead in Dec–Jan.",
    },
    "kovalam": {
        "types": ["resort", "budget_hotel", "guesthouse", "3star_hotel"],
        "popular": "beach resort",
        "areas": "Lighthouse Beach, Hawah Beach, Samudra Beach",
        "prices": {"budget_hotel": "₹800–2,000/night", "resort": "₹3,500–15,000/night"},
        "tip": "🏝️ Stay near Lighthouse Beach for best access to restaurants and surf.",
    },
    "andaman": {
        "types": ["resort", "guesthouse", "budget_hotel", "camping", "homestay"],
        "popular": "beach resort, eco-resort",
        "areas": "Port Blair (base), Havelock (beach), Neil Island (quiet)",
        "prices": {"guesthouse": "₹1,000–2,500/night", "resort": "₹4,000–18,000/night"},
        "tip": "🌴 Havelock resorts sell out fast — book at least 4 weeks in advance.",
    },

    # ── Hill Stations / Mountains ──────────────────────────────────────────
    "manali": {
        "types": ["camping", "hostel", "guesthouse", "budget_hotel", "resort", "homestay"],
        "popular": "camping, guesthouse",
        "areas": "Old Manali (backpacker), Mall Road (central), Vashisht (peaceful)",
        "prices": {
            "hostel": "₹400–900/night",
            "camping": "₹600–2,500/night",
            "guesthouse": "₹700–2,000/night",
            "resort": "₹3,000–12,000/night",
        },
        "tip": "❄️ Old Manali has cheap dorms. Book any stay before Sep–Oct snowfall.",
    },
    "shimla": {
        "types": ["budget_hotel", "guesthouse", "3star_hotel", "homestay", "resort"],
        "popular": "colonial heritage hotel",
        "areas": "Mall Road (central), Jakhu (temple), Kufri (scenic)",
        "prices": {"guesthouse": "₹800–2,000/night", "3star_hotel": "₹2,000–5,000/night"},
        "tip": "🏔️ Heritage hotels on Mall Road are pricey but iconic. Book Mar–Jun early.",
    },
    "darjeeling": {
        "types": ["guesthouse", "homestay", "budget_hotel", "resort", "camping"],
        "popular": "tea estate bungalow, guesthouse",
        "areas": "Chowrasta Mall (central), Batasia Loop (scenic)",
        "prices": {"guesthouse": "₹700–1,800/night", "resort": "₹3,000–10,000/night"},
        "tip": "🍵 Tea estate stays are unique — Glenburn, Happy Valley estates available.",
    },
    "ooty": {
        "types": ["resort", "guesthouse", "budget_hotel", "homestay", "camping"],
        "popular": "colonial resort, plantation stay",
        "areas": "Ooty Lake (central), Dodabetta (highest point), Kotagiri (quieter)",
        "prices": {"budget_hotel": "₹700–1,800/night", "resort": "₹3,000–12,000/night"},
        "tip": "🌿 Fernhills Royal Palace hotel for heritage stay. Apr–Jun very crowded.",
    },
    "munnar": {
        "types": ["resort", "homestay", "guesthouse", "camping", "3star_hotel"],
        "popular": "tea estate resort, plantation homestay",
        "areas": "Munnar Town (budget), Devikulam (scenic), Vagamon (quiet)",
        "prices": {"homestay": "₹1,200–3,000/night", "resort": "₹3,500–15,000/night"},
        "tip": "☁️ Plantation homestays offer tea-making experiences. Sep–Mar best season.",
    },
    "coorg": {
        "types": ["homestay", "resort", "guesthouse", "camping"],
        "popular": "coffee plantation homestay",
        "areas": "Madikeri (town), Virajpet, Abbey Falls area",
        "prices": {"homestay": "₹1,500–4,000/night", "resort": "₹4,000–18,000/night"},
        "tip": "☕ Coffee plantation homestays are Coorg's signature experience.",
    },
    "kodaikanal": {
        "types": ["guesthouse", "resort", "budget_hotel", "homestay", "camping"],
        "popular": "lake-view resort",
        "areas": "Kodai Lake (central), Bryant Park, Coaker's Walk",
        "prices": {"guesthouse": "₹700–2,000/night", "resort": "₹2,500–10,000/night"},
        "tip": "🌲 Lake-view rooms are most popular — book for April (summer rush).",
    },
    "mussoorie": {
        "types": ["budget_hotel", "guesthouse", "resort", "homestay", "3star_hotel"],
        "popular": "hotel near Mall Road",
        "areas": "Mall Road (central), Landour (quiet), Happy Valley",
        "prices": {"budget_hotel": "₹800–2,500/night", "resort": "₹3,000–10,000/night"},
        "tip": "⛰️ Landour is quieter and cheaper than Mall Road. Avoid May–Jun crowds.",
    },
    "ladakh": {
        "types": ["camping", "guesthouse", "homestay", "budget_hotel", "resort"],
        "popular": "camping, village homestay",
        "areas": "Leh (base), Nubra Valley (desert camp), Pangong (lakeside camp)",
        "prices": {
            "camping": "₹800–3,500/night",
            "guesthouse": "₹700–2,000/night",
            "homestay": "₹600–1,500/night",
        },
        "tip": "🏔️ Pangong lake camps are iconic but remote — book packages. Jun–Sep only.",
    },
    "spiti": {
        "types": ["camping", "homestay", "guesthouse"],
        "popular": "village homestay",
        "areas": "Kaza (base), Key Monastery, Chandratal Lake",
        "prices": {"camping": "₹500–1,500/night", "homestay": "₹400–1,000/night"},
        "tip": "🗻 Spiti homestays are very affordable — local families host travelers (<₹1,000).",
    },
    "rishikesh": {
        "types": ["camping", "hostel", "ashram", "guesthouse", "resort"],
        "popular": "yoga ashram, riverside camp",
        "areas": "Lakshman Jhula (backpacker), Tapovan (yoga), Ram Jhula",
        "prices": {
            "hostel": "₹300–700/night",
            "camping": "₹700–2,500/night",
            "guesthouse": "₹600–2,000/night",
        },
        "tip": "🕉️ Ashram stays (Parmarth, Sivananda) start at ₹200/night with yogic meals.",
    },
    "haridwar": {
        "types": ["ashram", "guesthouse", "budget_hotel", "dharamshala", "3star_hotel"],
        "popular": "dharamshala, guesthouse near Ganga",
        "areas": "Har Ki Pauri (central), Upper Road (quieter)",
        "prices": {"guesthouse": "₹400–1,500/night", "budget_hotel": "₹600–2,000/night"},
        "tip": "🙏 ISKCON and Saptrishi Ashram offer free/very cheap stays for pilgrims.",
    },
    "nainital": {
        "types": ["guesthouse", "resort", "budget_hotel", "homestay", "3star_hotel"],
        "popular": "lake-view hotel",
        "areas": "Mall Road (central), Ayarpatta (quieter), Bhimtal (less crowded)",
        "prices": {"guesthouse": "₹700–2,000/night", "3star_hotel": "₹2,000–6,000/night"},
        "tip": "🏞️ Lake-view rooms at Nainital are premium — check for shoulder season deals.",
    },
    "mcleod ganj": {
        "types": ["hostel", "guesthouse", "budget_hotel", "homestay"],
        "popular": "Tibetan guesthouse",
        "areas": "McLeod Ganj (central), Bhagsu (peaceful), Dharamkot (trekkers)",
        "prices": {"hostel": "₹250–600/night", "guesthouse": "₹500–1,500/night"},
        "tip": "🏔️ Dharamkot has cheap stays close to trekking trails. Very backpacker friendly.",
    },

    # ── Rajasthan Heritage ──────────────────────────────────────────────────
    "jaipur": {
        "types": ["heritage_hotel", "guesthouse", "budget_hotel", "5star_hotel", "homestay"],
        "popular": "heritage haveli, boutique hotel",
        "areas": "Walled City (heritage), C-Scheme (modern), Amer Road (scenic)",
        "prices": {
            "budget_hotel": "₹700–2,000/night",
            "guesthouse": "₹1,000–3,000/night",
            "5star_hotel": "₹8,000–35,000/night",
        },
        "tip": "🏰 Haveli stays in the Pink City are iconic. Nahargarh, Bissau Palace area best.",
    },
    "jodhpur": {
        "types": ["heritage_hotel", "guesthouse", "budget_hotel", "3star_hotel"],
        "popular": "heritage haveli near Mehrangarh",
        "areas": "Old City (blue houses, backpacker), Ratanada (quieter)",
        "prices": {"guesthouse": "₹700–2,500/night", "heritage_hotel": "₹2,000–10,000/night"},
        "tip": "💙 Blue City rooftop guesthouses have breathtaking Mehrangarh Fort views.",
    },
    "jaisalmer": {
        "types": ["desert_camp", "guesthouse", "heritage_hotel", "budget_hotel"],
        "popular": "desert camp, sandstone haveli",
        "areas": "Inside Fort (heritage), Gadisar Lake, Sam Sand Dunes (camps)",
        "prices": {
            "guesthouse": "₹600–2,000/night",
            "desert_camp": "₹2,000–8,000/night (with dinner, camel ride)",
        },
        "tip": "🐪 Sam Dunes overnight camp with camel safari is must-do. Book Oct–Feb.",
    },
    "udaipur": {
        "types": ["heritage_hotel", "guesthouse", "budget_hotel", "resort", "5star_hotel"],
        "popular": "lake-view heritage hotel",
        "areas": "Lake Pichola (romantic), Hanuman Ghat (budget), Fateh Sagar (quiet)",
        "prices": {
            "guesthouse": "₹800–2,500/night",
            "heritage_hotel": "₹3,000–15,000/night",
            "5star_hotel": "₹12,000–60,000/night",
        },
        "tip": "🛶 Lake Palace hotel is world-famous but ₹50K+/night. Budget: stay at Lake Pichola ghats.",
    },
    "pushkar": {
        "types": ["guesthouse", "budget_hotel", "ashram", "camping"],
        "popular": "lakeside guesthouse",
        "areas": "Pushkar Lake (center), Sadar Bazaar",
        "prices": {"guesthouse": "₹400–1,500/night", "budget_hotel": "₹600–2,000/night"},
        "tip": "🐘 Pushkar Camel Fair (Nov) — book months ahead as all stays fill completely.",
    },
    "bikaner": {
        "types": ["heritage_hotel", "guesthouse", "budget_hotel"],
        "popular": "heritage haveli",
        "areas": "Old City (heritage), Lalgarh Palace area",
        "prices": {"guesthouse": "₹500–1,500/night", "heritage_hotel": "₹1,500–6,000/night"},
        "tip": "🏰 Gajner Palace hotel is spectacular. Visit during cooler months (Oct–Mar).",
    },

    # ── Cultural / Spiritual ────────────────────────────────────────────────
    "varanasi": {
        "types": ["guesthouse", "budget_hotel", "ashram", "dharamshala", "3star_hotel", "boutique"],
        "popular": "Ganga-view guesthouse, dharamshala",
        "areas": "Assi Ghat (backpacker), Dashashwamedh Ghat (central), Godaulia",
        "prices": {
            "hostel": "₹300–700/night",
            "guesthouse": "₹500–2,000/night",
            "3star_hotel": "₹2,000–5,000/night",
        },
        "tip": "🕯️ Ghat-view guesthouses at Assi are budget-friendly. Book early for Diwali.",
    },
    "agra": {
        "types": ["budget_hotel", "guesthouse", "3star_hotel", "5star_hotel", "resort"],
        "popular": "Taj-view hotel",
        "areas": "Taj Ganj (budget, walking distance to Taj), Sadar Bazaar, MG Road",
        "prices": {
            "guesthouse": "₹600–2,000/night",
            "3star_hotel": "₹2,500–7,000/night",
            "5star_hotel": "₹12,000–50,000/night (Taj view rooms)",
        },
        "tip": "🕌 Oberoi Amarvilas has most iconic Taj view but is ₹35K+. Taj Ganj has cheap dorms.",
    },
    "amritsar": {
        "types": ["guesthouse", "budget_hotel", "dharamshala", "3star_hotel"],
        "popular": "dharamshala near Golden Temple",
        "areas": "Golden Temple area (free SGPC accommodation), Hall Bazaar",
        "prices": {"guesthouse": "₹500–1,500/night", "budget_hotel": "₹700–2,000/night"},
        "tip": "🙏 SGPC offers FREE accommodation in the Golden Temple complex for pilgrims!",
    },
    "hampi": {
        "types": ["guesthouse", "camping", "hostel", "budget_hotel"],
        "popular": "Boulder guesthouse, riverside camp",
        "areas": "Hampi Bazaar (main), Virupapur Gadde (hippie island, riverside)",
        "prices": {"hostel": "₹300–600/night", "guesthouse": "₹500–1,500/night"},
        "tip": "🗿 Cross the river to Virupapur Gadde for the cheapest stays and peaceful vibe.",
    },
    "khajuraho": {
        "types": ["budget_hotel", "guesthouse", "3star_hotel", "resort"],
        "popular": "hotel near western temple complex",
        "areas": "Western Temple area (most convenient), Jhansi Road",
        "prices": {"guesthouse": "₹600–1,500/night", "3star_hotel": "₹2,000–5,000/night"},
        "tip": "💫 Small, quiet destination — most mid-range hotels are fine. Visit Nov–Mar.",
    },
    "mysore": {
        "types": ["heritage_hotel", "guesthouse", "budget_hotel", "3star_hotel", "resort"],
        "popular": "heritage hotel, guesthouse",
        "areas": "Palace area (central), Chamundi Hills (scenic), Brindavan Gardens",
        "prices": {"guesthouse": "₹600–1,800/night", "3star_hotel": "₹2,000–5,000/night"},
        "tip": "👑 Stay near the Palace for Dasara festival. Book 3–4 months ahead for Oct.",
    },

    # ── Metro Cities ────────────────────────────────────────────────────────
    "mumbai": {
        "types": ["hostel", "budget_hotel", "guesthouse", "3star_hotel", "5star_hotel"],
        "popular": "beach hotel (Juhu), budget hotel (Colaba)",
        "areas": "Colaba (tourist), Bandra (trendy), Juhu (beach), Andheri (airport)",
        "prices": {
            "hostel": "₹400–900/night",
            "budget_hotel": "₹1,200–3,000/night",
            "3star_hotel": "₹3,500–8,000/night",
            "5star_hotel": "₹10,000–50,000/night",
        },
        "tip": "🌆 Colaba area hostels (near Gateway of India) are cheapest for backpackers.",
    },
    "delhi": {
        "types": ["hostel", "budget_hotel", "guesthouse", "3star_hotel", "5star_hotel"],
        "popular": "hotel in Connaught Place, boutique in Hauz Khas",
        "areas": "Paharganj (budget), Connaught Place (central), Hauz Khas (trendy)",
        "prices": {
            "hostel": "₹350–800/night",
            "budget_hotel": "₹900–2,500/night",
            "5star_hotel": "₹8,000–40,000/night",
        },
        "tip": "🏙️ Paharganj near New Delhi station is classic backpacker hub. Safe and cheap.",
    },
    "bangalore": {
        "types": ["hostel", "budget_hotel", "guesthouse", "3star_hotel", "5star_hotel"],
        "popular": "hotel near MG Road, hostel in Indiranagar",
        "areas": "MG Road (central), Koramangala (hip), Indiranagar (restaurants)",
        "prices": {"hostel": "₹400–900/night", "budget_hotel": "₹1,000–2,500/night"},
        "tip": "🌃 Koramangala & Indiranagar have best nightlife. Book on business-trip dates carefully.",
    },
    "hyderabad": {
        "types": ["budget_hotel", "guesthouse", "3star_hotel", "5star_hotel"],
        "popular": "hotel near Charminar, luxury near HITEC City",
        "areas": "Charminar (Old City, heritage), Banjara Hills (upscale), HITEC City (IT hub)",
        "prices": {"budget_hotel": "₹800–2,000/night", "5star_hotel": "₹7,000–30,000/night"},
        "tip": "🕌 Stay in Charminar area for biryani and bazaars. HITEC City for business stays.",
    },
    "chennai": {
        "types": ["hostel", "budget_hotel", "guesthouse", "3star_hotel", "resort"],
        "popular": "hotel near Marina Beach, business hotel",
        "areas": "Marina Beach (scenic), T. Nagar (shopping), OMR (IT corridor)",
        "prices": {"budget_hotel": "₹800–2,000/night", "3star_hotel": "₹2,500–6,000/night"},
        "tip": "🌊 Marina Beach area hotels have sea views. OMR is best for business travelers.",
    },
    "kolkata": {
        "types": ["hostel", "guesthouse", "budget_hotel", "3star_hotel", "5star_hotel"],
        "popular": "heritage hotel, backpacker hostel",
        "areas": "Park Street (central), Sudder Street (backpacker), Salt Lake (modern)",
        "prices": {"hostel": "₹350–700/night", "budget_hotel": "₹700–2,000/night"},
        "tip": "🎨 Sudder Street has the most hostels and budget hotels for solo travelers.",
    },
    "pune": {
        "types": ["hostel", "budget_hotel", "guesthouse", "3star_hotel", "resort"],
        "popular": "hotel near Shivajinagar, hostel in Koregaon Park",
        "areas": "Koregaon Park (Osho, trendy), Shivajinagar (central), Hinjewadi (IT)",
        "prices": {"hostel": "₹400–900/night", "budget_hotel": "₹900–2,500/night"},
        "tip": "🌆 Koregaon Park is the most happening area — best cafes and co-working spaces.",
    },

    # ── Northeast India ─────────────────────────────────────────────────────
    "shillong": {
        "types": ["guesthouse", "budget_hotel", "homestay", "resort", "camping"],
        "popular": "homestay, guesthouse",
        "areas": "Police Bazaar (central), Laitumkhrah (local), Umiam Lake (scenic)",
        "prices": {"guesthouse": "₹600–1,800/night", "homestay": "₹500–1,500/night"},
        "tip": "🌧️ Scotland of the East — homestays in villages near Cherrapunji are amazing.",
    },
    "kaziranga": {
        "types": ["resort", "guesthouse", "camping", "budget_hotel"],
        "popular": "wildlife resort, jungle lodge",
        "areas": "Kohora (central), Bagori, Agoratoli (near park gates)",
        "prices": {"guesthouse": "₹800–2,000/night", "resort": "₹3,000–12,000/night"},
        "tip": "🦏 Wildlife resorts with elephant safaris included are the best value option.",
    },
    "gangtok": {
        "types": ["guesthouse", "budget_hotel", "homestay", "resort", "3star_hotel"],
        "popular": "MG Marg hotel, mountain-view resort",
        "areas": "MG Marg (central), Tadong (local), Ranipool (quieter)",
        "prices": {"guesthouse": "₹700–2,000/night", "resort": "₹3,000–10,000/night"},
        "tip": "🏔️ Mountain-facing rooms give Kanchenjunga views. Book Oct–Nov for clear skies.",
    },
    "tawang": {
        "types": ["guesthouse", "budget_hotel", "camping", "homestay"],
        "popular": "guesthouse near monastery",
        "areas": "Tawang Town, Jung Village (serene)",
        "prices": {"guesthouse": "₹500–1,500/night", "budget_hotel": "₹700–2,000/night"},
        "tip": "🛕 Very remote — carry cash, limited ATMs. Book ahead for Oct–Apr peak season.",
    },

    # ── Kerala's Backwaters ─────────────────────────────────────────────────
    "alleppey": {
        "types": ["houseboat", "resort", "guesthouse", "homestay", "budget_hotel"],
        "popular": "houseboat, backwater resort",
        "areas": "Backwaters, Alleppey Beach, Kumarakom (nearby)",
        "prices": {
            "houseboat": "₹5,000–20,000/night (ac, meals included)",
            "guesthouse": "₹700–2,000/night",
            "resort": "₹4,000–15,000/night",
        },
        "tip": "🚢 Overnight houseboat is THE Alleppey experience. Book standard AC boat (₹6K) for value.",
    },
    "wayanad": {
        "types": ["resort", "homestay", "treehouse", "camping", "guesthouse"],
        "popular": "treehouse, plantation resort",
        "areas": "Kalpetta (town), Vythiri (resorts), Meppadi (plantation)",
        "prices": {"homestay": "₹1,200–3,500/night", "resort": "₹3,000–15,000/night"},
        "tip": "🌿 Treehouse stays are unique to Wayanad — book Vythiri Resort for premium version.",
    },

    # ── Madhya Pradesh / Central ─────────────────────────────────────────────
    "bhopal": {
        "types": ["budget_hotel", "guesthouse", "3star_hotel", "resort"],
        "popular": "hotel near lakes",
        "areas": "New Bhopal (modern), Old Bhopal (heritage), VIP Road (upscale)",
        "prices": {"budget_hotel": "₹700–1,800/night", "3star_hotel": "₹2,000–5,000/night"},
        "tip": "🏛️ Upper Lake area hotels offer great views. Visit Sanchi Stupa (45min away).",
    },
    "pachmarhi": {
        "types": ["resort", "guesthouse", "camping", "mp_tourism"],
        "popular": "MP Tourism resort",
        "areas": "Pachmarhi Town, Bee Falls area",
        "prices": {"guesthouse": "₹700–2,000/night", "resort": "₹2,500–10,000/night"},
        "tip": "🌲 MP State Tourism offers affordable resorts (₹2–3K) with forest views.",
    },
    "orchha": {
        "types": ["heritage_hotel", "guesthouse", "budget_hotel", "camping"],
        "popular": "heritage hotel near fort/palace",
        "areas": "Orchha Fort complex, Betwa River area",
        "prices": {"guesthouse": "₹500–1,500/night", "heritage_hotel": "₹2,000–8,000/night"},
        "tip": "🏯 Sheesh Mahal (inside Orchha Fort) is an MP Tourism heritage hotel — unique stay.",
    },

    # ── Tamil Nadu / South ───────────────────────────────────────────────────
    "madurai": {
        "types": ["guesthouse", "budget_hotel", "3star_hotel", "heritage_hotel"],
        "popular": "hotel near Meenakshi Temple",
        "areas": "Temple area (budget), Town Hall Road (central)",
        "prices": {"guesthouse": "₹500–1,500/night", "3star_hotel": "₹2,000–5,000/night"},
        "tip": "🛕 Temple Town guesthouses are cheapest. Avoid huge groups in festival months.",
    },
    "kodaikanal": {
        "types": ["guesthouse", "resort", "homestay", "budget_hotel"],
        "popular": "lake-view stay",
        "areas": "Kodai Lake (center), Coaker Walk, Bear Shola Falls area",
        "prices": {"guesthouse": "₹700–2,000/night", "resort": "₹2,500–10,000/night"},
        "tip": "🌲 Kodai's colonial bungalows (YWCA, Carlton) offer unique stays.",
    },
    "rameshwaram": {
        "types": ["dharamshala", "guesthouse", "budget_hotel"],
        "popular": "dharamshala near temple",
        "areas": "Temple area, Agni Teertham Beach",
        "prices": {"guesthouse": "₹400–1,000/night", "budget_hole": "₹600–1,800/night"},
        "tip": "🙏 HRCE-run dharamshalas offer very affordable rooms near the temple.",
    },

    # ── Gujarat ──────────────────────────────────────────────────────────────
    "rann of kutch": {
        "types": ["tent_resort", "guesthouse", "budget_hotel"],
        "popular": "Rann Utsav tent city",
        "areas": "Dhordo Village (Rann Utsav), Bhuj (base city)",
        "prices": {"guesthouse": "₹800–2,000/night", "tent_resort": "₹3,000–15,000/night"},
        "tip": "🌕 Rann Utsav tent city (Nov–Feb) is government-run and fully booked fast!",
    },
    "ahmedabad": {
        "types": ["heritage_hotel", "budget_hotel", "guesthouse", "3star_hotel"],
        "popular": "Heritage Walk area guesthouse, Pol houses",
        "areas": "Old City/Pol (heritage), CG Road (upscale), Navrangpura",
        "prices": {"budget_hotel": "₹700–2,000/night", "heritage_hotel": "₹2,000–8,000/night"},
        "tip": "🏛️ Staying in a restored Pol-house is the most authentic Ahmedabad experience.",
    },
    "dwarka": {
        "types": ["dharamshala", "guesthouse", "budget_hotel"],
        "popular": "dharamshala, guesthouse near temple",
        "areas": "Temple area, Dwarkadhish, Beyt Dwarka",
        "prices": {"guesthouse": "₹400–1,200/night", "budget_hotel": "₹600–1,800/night"},
        "tip": "🙏 Dwarka Dheesh Temple trust dharamshalas are free / very cheap for pilgrims.",
    },

    # ── Uttarakhand / Himalayas ───────────────────────────────────────────────
    "auli": {
        "types": ["resort", "guesthouse", "camping", "budget_hotel"],
        "popular": "ski resort",
        "areas": "Auli Ski Area, Gorson Bugyal Meadow",
        "prices": {"resort": "₹3,000–12,000/night", "guesthouse": "₹700–2,500/night"},
        "tip": "⛷️ GMVN resort is government-run, affordable. Best Jan–Mar for snow skiing.",
    },
    "chopta": {
        "types": ["camping", "guesthouse", "budget_hotel"],
        "popular": "camping, forest resthouse",
        "areas": "Chopta Meadow (trek base), Tungnath route",
        "prices": {"camping": "₹400–1,200/night", "guesthouse": "₹500–1,500/night"},
        "tip": "🌸 Mini Switzerland of India — bugyal meadow camping is breathtaking in May.",
    },
    "kedarnath": {
        "types": ["dharamshala", "tent", "guesthouse"],
        "popular": "dharamshala, GMVN tent",
        "areas": "Kedarnath Town (shrine), Gaurikund (base), Sonprayag",
        "prices": {"dharamshala": "₹150–500/night", "tent": "₹300–800/night"},
        "tip": "⛰️ GMVN camps near temple are best option. Book months ahead for Jul–Oct season.",
    },
    "char dham": {
        "types": ["dharamshala", "guesthouse", "budget_hotel", "camping"],
        "popular": "dharamshala at each dham",
        "areas": "Yamunotri · Gangotri · Kedarnath · Badrinath",
        "prices": {"dharamshala": "₹100–400/night", "guesthouse": "₹400–1,200/night"},
        "tip": "🙏 Register on IRCTC for Char Dham Yatra packages that include stay + transport.",
    },

    # ── Popular Weekend Getaways ──────────────────────────────────────────────
    "lonavala": {
        "types": ["resort", "budget_hotel", "guesthouse", "camping", "homestay"],
        "popular": "monsoon resort",
        "areas": "Lonavala Lake, Bhushi Dam, Khandala (twin hill station)",
        "prices": {"budget_hotel": "₹1,000–2,500/night", "resort": "₹3,000–12,000/night"},
        "tip": "🌧️ Monsoon is best season! Book resorts with valley-view. Very busy on weekends.",
    },
    "mahabaleshwar": {
        "types": ["resort", "guesthouse", "budget_hotel", "homestay"],
        "popular": "strawberry valley resort",
        "areas": "Mahabaleshwar Town, Panchgani (nearby), Venna Lake",
        "prices": {"guesthouse": "₹800–2,000/night", "resort": "₹3,000–15,000/night"},
        "tip": "🍓 Strawberry season (Feb–May) is peak — book 3 weeks ahead for weekends.",
    },
    "nashik": {
        "types": ["budget_hotel", "guesthouse", "homestay", "resort", "3star_hotel"],
        "popular": "wine resort, Kumbh Mela dharamshala",
        "areas": "Gangapur Road (wineries), Trimbak Road (temple), Devlali (peaceful)",
        "prices": {"budget_hotel": "₹700–1,800/night", "resort": "₹2,500–8,000/night"},
        "tip": "🍷 Sula Vineyards offers resort stay with wine tours — very unique experience!",
    },
    "aurangabad": {
        "types": ["budget_hotel", "guesthouse", "3star_hotel", "resort"],
        "popular": "hotel near Ajanta/Ellora caves",
        "areas": "CIDCO (new), City center, Near MIDC",
        "prices": {"guesthouse": "₹600–1,500/night", "3star_hotel": "₹2,000–5,500/night"},
        "tip": "🏺 Stay in Aurangabad as base for Ajanta (2hr) and Ellora (30min). Book Mar ahead.",
    },
}

def _get_stay_info(place_key):
    """Return formatted stay guide for a specific destination, or None if not in dataset."""
    info = STAY_DATASET.get(place_key.lower().strip())
    if not info:
        # Try partial match
        for key in STAY_DATASET:
            if key in place_key.lower() or place_key.lower() in key:
                info = STAY_DATASET[key]
                place_key = key
                break
    if not info:
        return None

    lines = [f"🏨 <b>Stay Options in {place_key.title()}:</b><br>"]
    lines.append(f"📍 <b>Best Areas:</b> {info['areas']}<br>")
    lines.append(f"⭐ <b>Most Popular:</b> {info['popular']}<br><br>")

    # Price breakdown
    if info.get("prices"):
        lines.append("<b>💰 Price Ranges:</b><br>")
        STAY_LABELS = {
            "hostel": "🛏️ Hostel",
            "budget_hotel": "🏩 Budget Hotel",
            "guesthouse": "🏡 Guesthouse",
            "homestay": "🏘️ Homestay",
            "3star_hotel": "⭐ 3-Star Hotel",
            "5star_hotel": "⭐⭐ 5-Star Hotel",
            "resort": "🏖️ Resort",
            "camping": "⛺ Camping",
            "heritage_hotel": "🏰 Heritage Hotel",
            "ashram": "🕉️ Ashram",
            "dharamshala": "🙏 Dharamshala",
            "houseboat": "🚢 Houseboat",
            "treehouse": "🌳 Treehouse",
            "tent_resort": "🏕️ Tent Resort",
            "desert_camp": "🐪 Desert Camp",
        }
        for stype, price in info["prices"].items():
            label = STAY_LABELS.get(stype, stype.replace("_", " ").title())
            lines.append(f"{label} — {price}<br>")

    lines.append(f"<br>💡 <b>Tip:</b> {info['tip']}<br>")
    lines.append("📱 <b>Book on:</b> MakeMyTrip · OYO · Booking.com · Airbnb · Agoda")
    return "".join(lines)


def _call_external_llm(message, history):
    """Try to answer the chat message with an external LLM if configured."""
    hf_key = os.environ.get('HF_API_KEY')
    hf_model = os.environ.get('HF_MODEL', 'google/flan-t5-small')
    openai_key = os.environ.get('OPENAI_API_KEY')
    google_key = os.environ.get('GOOGLE_API_KEY')
    openai_model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

    system_prompt = (
        "You are a helpful travel assistant with special knowledge of Indian travel, "
        "but you can also answer general questions. Keep responses safe, factual and concise. "
        "If the user asks about travel, prioritize practical travel advice."
    )

    def _query_hf_model(model_name, auth_header=None):
        prompt = system_prompt + "\n\n" + "Conversation history:\n"
        for item in history[-6:]:
            role = 'User' if item.get('role') == 'user' else 'Assistant'
            prompt += f"{role}: {item.get('text')}\n"
        prompt += f"User: {message}\nAssistant:"

        headers = {'Content-Type': 'application/json'}
        if auth_header:
            headers['Authorization'] = auth_header

        payload = {
            'inputs': prompt,
            'parameters': {
                'max_new_tokens': 200,
                'temperature': 0.7,
                'top_p': 0.9,
                'return_full_text': False
            }
        }
        url = f'https://api-inference.huggingface.co/models/{model_name}'
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.ok:
            data = response.json()
            if isinstance(data, dict) and 'error' not in data:
                if isinstance(data.get('generated_text'), str):
                    return data['generated_text'].strip()
                if isinstance(data, list) and len(data) and isinstance(data[0], dict):
                    return data[0].get('generated_text', '').strip()
        return None

    try:
        if hf_key:
            result = _query_hf_model(hf_model, auth_header=f'Bearer {hf_key}')
            if result:
                return result

        if not hf_key:
            # Try a public HF model without an API key.
            result = _query_hf_model(hf_model)
            if result:
                return result

            # Fallback to a small open model if the first public model is blocked.
            fallback_model = 'gpt2'
            result = _query_hf_model(fallback_model)
            if result:
                return result

        if openai_key:
            payload = {
                "model": openai_model,
                "messages": [
                    {"role": "system", "content": system_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 450,
                "top_p": 0.9
            }
            for item in history[-6:]:
                if item.get('role') in ['user', 'bot'] and item.get('text'):
                    payload['messages'].append({
                        'role': item['role'],
                        'content': item['text']
                    })
            payload['messages'].append({"role": "user", "content": message})

            headers = {
                'Authorization': f'Bearer {openai_key}',
                'Content-Type': 'application/json'
            }
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=15
            )
            if response.ok:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()

        if google_key:
            gemini_url = os.environ.get('GOOGLE_GEMINI_URL')
            if gemini_url:
                headers = {
                    'Authorization': f'Bearer {google_key}',
                    'Content-Type': 'application/json'
                }
                response = requests.post(
                    gemini_url,
                    headers=headers,
                    json={
                        'prompt': message,
                        'history': history[-6:],
                        'max_output_tokens': 500
                    },
                    timeout=15
                )
                if response.ok:
                    data = response.json()
                    return data.get('output_text') or data.get('response')
    except Exception:
        pass

    return None


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
        stay_words   = ["stay", "hotel", "hostel", "resort", "guesthouse", "lodge", "oyo",
                        "accommodation", "where to stay", "room", "airbnb", "homestay",
                        "dharamshala", "camping", "tent", "booking", "check in"]

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

        if any(w in m for w in stay_words):
            # Try destination-specific dataset first
            ds_info = _get_stay_info(detected_place)
            if ds_info:
                title, extract = _wiki_search(detected_place)
                if title and extract:
                    return _format_wiki_response(title, extract, ds_info)
                return ds_info
            # Fallback: generic stay guide with place name
            stay_guide = (
                f"🏨 <b>Where to Stay in {detected_place.title()}:</b><br>"
                "🛏️ <b>Hostel</b> — ₹300–800/night (solo backpackers)<br>"
                "🏩 <b>Budget Hotel / OYO</b> — ₹600–1,500/night<br>"
                "🏡 <b>Guesthouse</b> — ₹800–2,000/night<br>"
                "🏘️ <b>Homestay / Airbnb</b> — ₹1,200–3,000/night<br>"
                "⭐ <b>3-Star Hotel</b> — ₹2,500–5,000/night<br>"
                "⭐⭐ <b>5-Star Hotel</b> — ₹6,000–20,000/night<br>"
                "🏖️ <b>Resort</b> — ₹5,000–25,000/night<br>"
                "⛺ <b>Camping</b> — ₹500–3,000/night<br><br>"
                "📱 <b>Book on:</b> MakeMyTrip · Booking.com · OYO · Airbnb · Agoda · Goibibo<br>"
                "💡 <b>Tip:</b> Book at least 7–14 days ahead for weekends and holiday season!"
            )
            title, extract = _wiki_search(detected_place + " tourism")
            if title and extract:
                return _format_wiki_response(title, extract, stay_guide)
            return stay_guide

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

    # ─── INTENT: Stay / Accommodation (global — no specific place needed) ───
    global_stay_triggers = [
        "where to stay", "types of stay", "which hotel", "best hotel", "cheap hotel",
        "luxury hotel", "budget stay", "hostel vs hotel", "oyo rooms", "airbnb india",
        "hotel booking", "resort booking", "accommodation type", "stay type",
        "guesthouse", "dharamshala", "lodging", "room booking",
        "camping india", "glamping", "homestay india", "5 star hotel", "3 star hotel"
    ]
    if any(t in m for t in global_stay_triggers):
        return (
            "🏨 <b>Stay Types for Indian Travel:</b><br>"
            "🛏️ <b>Hostel / Dorm</b> — ₹300–800/night · Best: solo backpackers<br>"
            "🏩 <b>Budget Hotel / OYO</b> — ₹600–1,500/night · Best: short stays<br>"
            "🏡 <b>Guesthouse / B&B</b> — ₹800–2,000/night · Best: families<br>"
            "🏘️ <b>Homestay / Airbnb</b> — ₹1,200–3,000/night · Best: local experience<br>"
            "⭐ <b>3-Star Hotel</b> — ₹2,500–5,000/night · Best: comfort travel<br>"
            "⭐⭐ <b>5-Star Hotel</b> — ₹6,000–20,000/night · Best: luxury trips<br>"
            "🏖️ <b>Resort</b> — ₹5,000–25,000/night · Best: beach / hill getaways<br>"
            "⛺ <b>Camping / Glamping</b> — ₹500–3,000/night · Best: adventure travel<br><br>"
            "📱 <b>Best booking apps:</b> MakeMyTrip · OYO · Booking.com · Airbnb · Agoda<br>"
            "💡 <b>Pro tip:</b> You can select your Stay Type right in the <b>Plan Trip</b> form!"
        )

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
            return ("💱 <b>Currency Tips for India Travel:</b><br>"
                    "<ul><li>For domestic travel, you only need Indian Rupees (₹) — no currency exchange needed!</li>"
                    "<li>ATMs are widely available — use HDFC, SBI, or ICICI for best rates.</li>"
                    "<li>Inform your bank about your travel plans to avoid card blocks.</li>"
                    "<li>Carry a mix of cash and cards — UPI apps like GPay/PhonePe are widely accepted.</li>"
                    "<li>Avoid exchanging money at airports; they have the worst rates.</li></ul>")
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
            return ("✈️ <b>Domestic Flight Travel Tips (India):</b><br>"
                    "<ul><li>Book 4-6 weeks in advance for best fares on Indigo, Air India, SpiceJet.</li>"
                    "<li>Use <b>Google Flights</b>, <b>MakeMyTrip</b>, or <b>Goibibo</b> to compare fares.</li>"
                    "<li>Always arrive 2 hours before domestic flights (Indian airports can be crowded).</li>"
                    "<li>Keep digital copies of your boarding pass and Aadhaar card.</li>"
                    "<li>Check-in online 24 hours before to avoid queues.</li>"
                    "<li>Carry only cabin baggage if possible — domestic flights have strict weight limits.</li></ul>")
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
        return ("🛡️ <b>Travel Safety Checklist (India):</b><br>"
                "<ul><li>Carry your <b>Aadhaar card / Voter ID</b> — required for hotel check-ins and trains in India.</li>"
                "<li>Share your live location with a trusted contact using WhatsApp or Google Maps.</li>"
                "<li>Use our <b>Live Tracker</b> to stay connected with family.</li>"
                "<li>Avoid displaying expensive items or large amounts of cash in public.</li>"
                "<li>Use a VPN on public Wi-Fi — airports, cafes, hotels are common spots.</li>"
                "<li>Research local safety concerns at your destination before arriving.</li>"
                "<li>Trust your gut — if something feels wrong, leave the area immediately.</li>"
                "<li>Save emergency numbers: Police (100), Ambulance (108), Fire (101).</li></ul>")

    # ─── INTENT: Packing / Luggage ───
    if any(w in m for w in ["pack", "packing", "luggage", "bag", "carry", "essentials", "what to bring"]):
        return ("🧳 <b>Smart Packing List for India Travel:</b><br>"
                "<ul><li>📄 <b>Aadhaar Card / Voter ID / PAN Card</b> — mandatory for hotel check-in & train travel in India</li>"
                "<li>💊 Personal medications + basic first aid kit (ORS packets for dehydration)</li>"
                "<li>🔌 Universal power adapter (Type D/M plugs used in India)</li>"
                "<li>💦 Reusable water bottle + water purification tablets</li>"
                "<li>🧴 Sunscreen + mosquito repellent (essential for Indian climate)</li>"
                "<li>📱 Power bank (min. 10,000 mAh — power cuts are common)</li>"
                "<li>🧥 Light jacket/layer (AC in trains/hotels can be freezing!)</li>"
                "<li>💳 Multiple payment methods (cash + UPI apps like GPay/PhonePe/Paytm)</li>"
                "<li>👕 Modest clothing for temple visits (shoulders and knees covered)</li></ul>")

    # ─── INTENT: ID / Documentation (Domestic India vs International) ───
    if any(w in m for w in ["visa", "passport", "document", "id proof", "permit", "id card", "aadhaar"]):
        # Check if the user is asking about international travel (visa) or domestic India travel
        is_international = any(w in m for w in ["visa", "abroad", "international", "foreign", "outside india",
                                                 "overseas", "uk", "usa", "europe", "passport", "embassy"])
        if is_international:
            return ("📋 <b>International Travel Document Checklist:</b><br>"
                    "<ul><li>✅ Valid passport (6+ months validity required for most countries).</li>"
                    "<li>✅ Check visa requirements at your destination's official embassy website.</li>"
                    "<li>✅ India offers <b>e-Visa</b> for 150+ countries at <b>indianvisaonline.gov.in</b></li>"
                    "<li>✅ Carry 4 passport-size photos for emergency use.</li>"
                    "<li>✅ Keep scanned copies on email/cloud: passport, visa, tickets, travel insurance.</li>"
                    "<li>✅ Buy <b>travel insurance</b> — mandatory for Schengen, UK, USA visas.</li></ul>")
        else:
            return ("📋 <b>Documents for Domestic India Travel:</b><br>"
                    "<ul><li>🪪 <b>No visa or passport needed</b> — you're travelling within India!</li>"
                    "<li>✅ Carry <b>Aadhaar Card</b> — accepted at all hotels, trains, flights.</li>"
                    "<li>✅ <b>Voter ID / Driving License / PAN Card</b> also accepted as valid ID.</li>"
                    "<li>✅ For flights: any government photo ID is sufficient.</li>"
                    "<li>✅ For trains: Aadhaar or any photo ID verified against your PNR.</li>"
                    "<li>✅ Keep digital copies of your ID on DigiLocker (India's official app).</li>"
                    "<li>ℹ️ <i>Planning to go outside India? Ask me about 'international travel documents'.</i></li></ul>")

    # ─── INTENT: Best destination by season ───
    if any(w in m for w in ["best place", "best destination", "best spot", "where should i go", "where to go", "best city", "best hill station"]) and any(s in m for s in ["summer", "monsoon", "winter", "spring", "autumn", "fall"]):
        if "summer" in m:
            return ("☀️ <b>Best places to visit in summer:</b><br>"
                    "<ul>"
                    "<li><b>Ladakh / Nubra Valley</b> — cool alpine deserts, dramatic mountain roads.</li>"
                    "<li><b>Spiti Valley</b> — remote high-altitude summer escape with clear skies.</li>"
                    "<li><b>Auli</b> or <b>Manali</b> — great for mountain views and pleasant temperatures.</li>"
                    "<li><b>North Sikkim</b> / <b>Darjeeling</b> — green hill stations with cooler weather.</li>"
                    "<li><b>Shimla</b> and <b>Nainital</b> — classic summer hill station favourites.</li>"
                    "</ul>"
                    "<br>For a more relaxing summer trip, tell me your preferred region or budget.")
        if "monsoon" in m or "rain" in m:
            return ("🌧️ <b>Best places to visit in monsoon:</b><br>"
                    "<ul>"
                    "<li><b>Munnar</b> / <b>Coorg</b> — lush tea gardens and misty hills.</li>"
                    "<li><b>Lonavala</b> / <b>Khandala</b> — quick monsoon getaways near Mumbai.</li>"
                    "<li><b>Cherrapunji</b> / <b>Mawsynram</b> — dramatic waterfalls and rain forests.</li>"
                    "<li><b>Goa</b> (south coast) — quieter beaches with green scenery.</li>"
                    "</ul>"
                    "<br>Monsoon travel is beautiful if you choose hill stations and backwaters.")
        if "winter" in m:
            return ("❄️ <b>Best places to visit in winter:</b><br>"
                    "<ul>"
                    "<li><b>Rajasthan</b> — Jaipur, Udaipur, Jaisalmer, and Jodhpur are at their best.</li>"
                    "<li><b>Goa</b> — beach weather is perfect and the coast is festive.</li>"
                    "<li><b>Kerala</b> — backwaters, beaches, and hill stations are very pleasant.</li>"
                    "<li><b>Andaman</b> — warm beach weather with excellent snorkeling.</li>"
                    "</ul>"
                    "<br>Let me know if you want a suggestion by region, budget, or travel style.")
        if "spring" in m or "autumn" in m or "fall" in m:
            return ("🍂 <b>Best places for spring/autumn travel:</b><br>"
                    "<ul>"
                    "<li><b>Darjeeling</b> / <b>Gangtok</b> — crisp skies and flowering valleys.</li>"
                    "<li><b>Coorg</b> — coffee plantations and mild weather.</li>"
                    "<li><b>Ooty</b> / <b>Kodaikanal</b> — scenic hill stations in south India.</li>"
                    "</ul>"
                    "<br>Tell me your travel dates and I can refine the recommendation.")

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
        return ("🏥 <b>Travel Health Guide for India:</b><br>"
                "<ul><li>Consider travel insurance for medical emergencies and trip cancellations.</li>"
                "<li>Carry a basic first-aid kit: bandages, antiseptic, antacids, ORS packets, paracetamol.</li>"
                "<li>Stay hydrated and avoid street food if you have a sensitive stomach.</li>"
                "<li>Drink only bottled or filtered water in unfamiliar areas.</li>"
                "<li>India Ambulance: <b>108</b> | Tourist Helpline: <b>1800-111-363</b></li>"
                "<li>Carry mosquito repellent for monsoon season and forested areas.</li></ul>")

    # ─── INTENT: Internet / SIM ───
    if any(w in m for w in ["sim", "internet", "data", "wifi", "network", "roaming", "4g", "5g", "connect"]):
        return ("📡 <b>Staying Connected in India:</b><br>"
                "<ul><li>Get a local prepaid SIM from <b>Jio</b> or <b>Airtel</b> — excellent nationwide coverage.</li>"
                "<li>Available at airports, railway stations, or any mobile store.</li>"
                "<li>Most hotels and cafes offer free Wi-Fi, but use a VPN for security.</li>"
                "<li>Download offline maps and keep physical maps as backup.</li>"
                "<li>UPI apps like GPay/PhonePe work without internet for payments.</li></ul>")

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
                "<li>🛡️ <b>Safety tips for India</b></li>"
                "<li>💰 <b>Budget & costs</b></li>"
                "<li>🚗 <b>Transport in India</b> — trains, flights, buses</li>"
                "<li>🌤️ <b>Weather & best seasons</b></li>"
                "<li>🍛 <b>Food recommendations</b></li>"
                "<li>🏨 <b>Accommodation tips</b></li>"
                "<li>🪪 <b>Documents</b> — Aadhaar, ID proof for Indian travel</li>"
                "<li>🧳 <b>Packing for Indian climate</b></li>"
                "<li>🌐 <b>Info on any Indian destination</b> — 'tell me about Goa'</li></ul>"
                "Just ask me anything about traveling in India!")

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


# ---------------------------------
# ITINERARY GENERATOR API
# ---------------------------------
@app.route('/api/itinerary-generator', methods=['GET'])
def get_itinerary_generator():
    """Generates an itinerary using Wikipedia Geosearch based on Lat/Lon"""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    days = request.args.get('days', 3)
    
    if not lat or not lon:
        return jsonify({"status": "error", "message": "Missing coordinates"})
        
    try:
        days = int(days)
        # 1. Fetch nearby Wikipedia articles (Radius 10km, max 15 places)
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=geosearch&gscoord={lat}|{lon}&gsradius=10000&gslimit=15&format=json"
        
        headers = {'User-Agent': 'SmartTravelPlanner/1.0'}
        geo_res = requests.get(search_url, headers=headers, timeout=5).json()
        places = geo_res.get('query', {}).get('geosearch', [])
        
        import re
        blacklist_pattern = re.compile(
            r'colony|residential|society|apartment|phase\s*\d|sector\s*\d|layout|cross|taluka|tehsil|mandal|district|'
            r'school|college|institute|university|academy', 
            re.IGNORECASE
        )
        
        filtered_places = [p for p in places if not blacklist_pattern.search(p.get('title', ''))]
        
        if not filtered_places:
            return jsonify({"status": "error", "message": "No famous activities found in Wikipedia around this location."})
            
        page_ids = [str(p['pageid']) for p in filtered_places]
        places_data = []
        
        # 2. Fetch extracts & thumbnails efficiently in one batch query
        detail_url = f"https://en.wikipedia.org/w/api.php?action=query&pageids={'|'.join(page_ids)}&prop=extracts|pageimages&exintro=1&explaintext=1&exchars=200&pithumbsize=400&format=json"
        detail_res = requests.get(detail_url, headers=headers, timeout=5).json()
        pages = detail_res.get('query', {}).get('pages', {})
        
        for k, v in pages.items():
            places_data.append({
                "title": v.get("title"),
                "summary": v.get("extract", "A famous local landmark worth visiting."),
                "image": v.get("thumbnail", {}).get("source", None),
                "lat": next((p["lat"] for p in places if str(p["pageid"]) == str(k)), lat),
                "lon": next((p["lon"] for p in places if str(p["pageid"]) == str(k)), lon)
            })
            
        # 3. Mathematically chunk the places by the number of days!
        import math
        chunk_size = math.ceil(len(places_data) / days) if days > 0 else len(places_data)
        itinerary = []
        
        for i in range(days):
            day_activities = places_data[i * chunk_size : (i + 1) * chunk_size]
            if day_activities:
                itinerary.append({
                    "day": i + 1,
                    "activities": day_activities
                })
                
        return jsonify({
            "status": "success", 
            "itinerary": itinerary,
            "total_places": len(places_data)
        })

    except Exception as e:
        print("Itinerary Error:", e)
        return jsonify({"status": "error", "message": "Failed to generate itinerary. " + str(e)})

if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'])