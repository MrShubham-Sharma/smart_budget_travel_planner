from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import database  # Your updated database.py
from geopy.geocoders import Nominatim

app = Flask(__name__)
app.secret_key = 'supersecretkey123'  # Required for sessions

# Initialize DB
database.init_db()

geolocator = Nominatim(user_agent="smart_travel_app")

# ------------------ ROUTES ------------------

@app.route('/')
def home():
    return redirect(url_for('login_page'))

@app.route('/login-page')
def login_page():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/signup-page')
def signup_page():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login_page'))
    return render_template('dashboard.html', user_name=session.get('user_name'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ------------------ AUTH API ------------------

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json(force=True)
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"status": "error", "message": "All fields are required"})

    if database.add_user(name, email, password):
        return jsonify({"status": "success", "redirect": "/login-page"})
    else:
        return jsonify({"status": "error", "message": "Email already exists"})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(force=True)
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"status": "error", "message": "All fields are required"})

    user = database.validate_user(email, password)
    if user:
        session['user_id'] = user[0]
        session['user_name'] = user[1]
        return jsonify({"status": "success", "redirect": "/dashboard"})
    else:
        return jsonify({"status": "error", "message": "Invalid Credentials"})

# ------------------ TRIP API ------------------

@app.route('/add-trip', methods=['POST'])
def add_trip_api():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"})

    data = request.get_json(force=True)
    try:
        trip_name = data.get("trip_name")
        destination = data.get("destination")
        start_date = data.get("start_date") or None
        end_date = data.get("end_date") or None
        budget = float(data.get("budget") or 0)
        latitude = float(data.get("latitude") or 0)
        longitude = float(data.get("longitude") or 0)

        if not trip_name or not destination or latitude == 0 or longitude == 0:
            return jsonify({"status": "error", "message": "Trip name, destination, and location are required"})

        success = database.add_trip(
            user_id=session["user_id"],
            trip_name=trip_name,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            latitude=latitude,
            longitude=longitude
        )
        if success:
            return jsonify({"status": "success", "message": "Trip added successfully!"})
        else:
            return jsonify({"status": "error", "message": "Failed to add trip"})

    except ValueError:
        return jsonify({"status": "error", "message": "Invalid numeric input"})

@app.route('/get-trips', methods=['GET'])
def get_trips_api():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"})
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

# ------------------ LOCATION API ------------------

@app.route("/api/locations", methods=["GET"])
def get_locations():
    query = request.args.get("q", "")
    if not query:
        return jsonify({"status": "error", "message": "Query is required", "locations": []})

    try:
        results = geolocator.geocode(query, exactly_one=False, limit=5, addressdetails=True)
        locations = []
        if results:
            for r in results:
                locations.append({
                    "name": r.address,
                    "latitude": r.latitude,
                    "longitude": r.longitude
                })
        return jsonify({"status": "success", "locations": locations})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "locations": []})

# ------------------ TRIP MANAGEMENT (Update/Delete) ------------------

@app.route('/delete-trip', methods=['POST'])
def delete_trip():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"})

    data = request.get_json(force=True)
    trip_id = data.get('trip_id')
    if not trip_id:
        return jsonify({"status": "error", "message": "No trip id provided"})

    # Call database.py function to delete
    success = database.delete_trip(trip_id, session['user_id'])
    if success:
        return jsonify({"status": "success", "message": "Trip deleted successfully"})
    else:
        return jsonify({"status": "error", "message": "Trip not found or not authorized"})

@app.route('/update-trip', methods=['POST'])
def update_trip_api():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Not logged in"})
    data = request.get_json(force=True)
    trip_id = data.get("trip_id")
    if not trip_id:
        return jsonify({"status": "error", "message": "trip_id required"})

    trip = database.get_trip(trip_id)
    if not trip:
        return jsonify({"status": "error", "message": "Trip not found"})
    if trip[1] != session["user_id"]:
        return jsonify({"status": "error", "message": "Not authorized"})

    try:
        trip_name = data.get("trip_name")
        destination = data.get("destination")
        start_date = data.get("start_date") or None
        end_date = data.get("end_date") or None
        budget = None if data.get("budget") in (None, "") else float(data.get("budget"))
        latitude = None if data.get("latitude") in (None, "") else float(data.get("latitude"))
        longitude = None if data.get("longitude") in (None, "") else float(data.get("longitude"))
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid numeric values"})

    success = database.update_trip(
        trip_id,
        trip_name=trip_name,
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        latitude=latitude,
        longitude=longitude
    )
    return jsonify({"status": "success" if success else "error", "message": "Updated" if success else "Update failed"})

# ------------------ RUN APP ------------------

if __name__ == "__main__":
    app.run(debug=True)
