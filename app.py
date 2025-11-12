import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import database  # Your enhanced database.py
import config    # Our new config file

app = Flask(__name__)
# Load configuration from config.py
app.config.from_object('config.Config')

# Initialize DB
database.init_db()

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
    return render_template('dashboard.html', user_name=session.get('user_name'))

# NEW: Dedicated route for the live tracker page
@app.route('/live-tracker-page')
def live_tracker_page():
    """Serve the dedicated live tracking map."""
    if not session.get('user_id'):
        return redirect(url_for('login_page'))
    return render_template('live.html', user_name=session.get('user_name'))

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

    # user[0]=id, user[1]=name, user[2]=hashed_password
    if user and check_password_hash(user[2], password):
        session['user_id'] = user[0]
        session['user_name'] = user[1]
        return jsonify({"status": "success", "redirect": "/dashboard"})
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
    trip_budget = trip[6] if trip[6] else 0.0
    remaining_budget = trip_budget - total_spent
    # --- END ENHANCEMENT ---

    return jsonify({
        "status": "success",
        "expenses": expenses,
        "total_spent": total_spent,
        "trip_budget": trip_budget,
        "remaining_budget": remaining_budget
    })

# ------------------
# 5. PLACEHOLDER PAGES
# ------------------
# (You will need to create these .html files in your 'templates' folder)

@app.route('/live-tracker')
def live_tracker():
    if not session.get('user_id'): return redirect(url_for('login_page'))
    return render_template('live_tracker.html', user_name=session.get('user_name'))

@app.route('/budget-planner')
def budget_planner():
    if not session.get('user_id'): return redirect(url_for('login_page'))
    return render_template('budget_planner.html', user_name=session.get('user_name'))
    
@app.route('/budget-tracker')
def budget_tracker():
    if not session.get('user_id'): return redirect(url_for('login_page'))
    return render_template('budget_tracker.html', user_name=session.get('user_name'))

@app.route('/nearby-attractions')
def nearby_attractions():
    if not session.get('user_id'): return redirect(url_for('login_page'))
    return render_template('nearby_attractions.html', user_name=session.get('user_name'))

@app.route('/travel-tips')
def travel_tips():
    if not session.get('user_id'): return redirect(url_for('login_page'))
    return render_template('travel_tips.html', user_name=session.get('user_name'))

@app.route('/chatbot')
def chatbot():
    if not session.get('user_id'): return redirect(url_for('login_page'))
    return render_template('chatbot.html', user_name=session.get('user_name'))


# ------------------
# 6. RUN APP
# ------------------

if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'])