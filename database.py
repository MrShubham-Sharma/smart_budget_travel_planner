import sqlite3
import os

# Database file placed next to this module
DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')

def init_db():
    """Create all tables (users, trips, expenses) if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Trips table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            trip_name TEXT NOT NULL,
            destination TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            budget REAL,
            latitude REAL,
            longitude REAL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Added expenses table creation here
    cur.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            category TEXT,
            amount REAL,
            description TEXT,
            FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

# ------------------
# 1. AUTH FUNCTIONS
# ------------------

# CHANGED: Now accepts a hashed password
def add_user(name, email, hashed_password):
    """Add a new user. Returns True if added, False on duplicate email."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, hashed_password) # Store the hash, not the plain password
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Email already exists (unique constraint)
        return False
    finally:
        conn.close()

# NEW: Replaces validate_user for security
def get_user_by_email(email):
    """Fetches a user by email to allow for password hash checking.
       Returns (id, name, hashed_password)"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, password FROM users WHERE email = ?",
        (email,)
    )
    user = cur.fetchone()
    conn.close()
    return user

# ------------------
# 2. TRIP FUNCTIONS
# ------------------

def add_trip(user_id, trip_name, destination, start_date=None, end_date=None, budget=None, latitude=None, longitude=None):
    """Insert a trip for a user. Returns True on success."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO trips (user_id, trip_name, destination, start_date, end_date, budget, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, trip_name, destination, start_date, end_date, budget, latitude, longitude))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding trip: {e}")
        return False
    finally:
        conn.close()

def get_user_trips(user_id):
    """Return list of trip rows for the given user_id (list of tuples)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM trips WHERE user_id = ?", (user_id,))
    trips = cur.fetchall()
    conn.close()
    return trips

# NEW: Required by app.py to check ownership before update/delete
def get_trip(trip_id):
    """Gets a single trip by its ID."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    trip = cur.fetchone()
    conn.close()
    return trip

# NEW: Required by app.py to handle trip updates
def update_trip(trip_id, trip_name, destination, start_date, end_date, budget, latitude, longitude):
    """Dynamically updates fields for a given trip.
       Only updates fields that are not None."""
       
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    fields_to_update = []
    params = []
    
    # Build the query dynamically
    if trip_name is not None:
        fields_to_update.append("trip_name = ?")
        params.append(trip_name)
    if destination is not None:
        fields_to_update.append("destination = ?")
        params.append(destination)
    if start_date is not None:
        fields_to_update.append("start_date = ?")
        params.append(start_date)
    if end_date is not None:
        fields_to_update.append("end_date = ?")
        params.append(end_date)
    if budget is not None:
        fields_to_update.append("budget = ?")
        params.append(budget)
    if latitude is not None:
        fields_to_update.append("latitude = ?")
        params.append(latitude)
    if longitude is not None:
        fields_to_update.append("longitude = ?")
        params.append(longitude)

    if not fields_to_update:
        return True # Nothing to update

    try:
        query = f"UPDATE trips SET {', '.join(fields_to_update)} WHERE id = ?"
        params.append(trip_id)
        
        cur.execute(query, tuple(params))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating trip: {e}")
        return False
    finally:
        conn.close()

# CHANGED: Kept the single, correct version of delete_trip
def delete_trip(trip_id, user_id):
    """Deletes a trip only if the user_id matches."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM trips WHERE id=? AND user_id=?", (trip_id, user_id))
        conn.commit()
        success = cur.rowcount > 0
        return success
    except Exception as e:
        print(f"Error deleting trip: {e}")
        return False
    finally:
        conn.close()

# ------------------
# 3. EXPENSE FUNCTIONS
# ------------------

def add_expense(trip_id, category, amount, description):
    """Adds a new expense to the expenses table."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO expenses (trip_id, category, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (trip_id, category, amount, description))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding expense: {e}")
        return False
    finally:
        conn.close()

def get_expenses(trip_id):
    """Gets all expenses for a given trip_id."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM expenses WHERE trip_id=?", (trip_id,))
    data = cur.fetchall()
    conn.close()
    return data

# ------------------
# 4. INITIALIZATION
# ------------------

# Run init_db() once when this module is imported.
# This creates all 3 tables automatically.
init_db()