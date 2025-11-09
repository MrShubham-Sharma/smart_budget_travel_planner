# database.py
import sqlite3
import os

# Database file placed next to this module
DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')

def init_db():
    """Create the users and trips tables if they don't exist."""
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
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()


def add_user(name, email, password):
    """Add a new user. Returns True if added, False on duplicate email."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Email already exists (unique constraint)
        return False
    finally:
        conn.close()


def validate_user(email, password):
    """Return the user row if email/password match, otherwise None.
       Returns a tuple (id, name, email, password) when found."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (email, password)
    )
    user = cur.fetchone()
    conn.close()
    return user


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
        # For debugging you can uncomment:
        # print("add_trip error:", e)
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


# Initialize DB when module is imported (safe to call multiple times)
if __name__ != "__main__":
    # Only initialize when imported by your app — optional but convenient.
    init_db()
def delete_trip(trip_id, user_id):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    # Only delete if the trip belongs to the user
    cur.execute("DELETE FROM trips WHERE id=? AND user_id=?", (trip_id, user_id))
    conn.commit()
    success = cur.rowcount > 0
    conn.close()
    return success
def delete_trip(trip_id, user_id):
    conn = sqlite3.connect(DB_PATH)  # Use same DB_PATH
    cur = conn.cursor()
    # Only delete if the trip belongs to the user
    cur.execute("DELETE FROM trips WHERE id=? AND user_id=?", (trip_id, user_id))
    conn.commit()
    success = cur.rowcount > 0
    conn.close()
    return success
