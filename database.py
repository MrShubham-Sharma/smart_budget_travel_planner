import os

DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Render gives URLs starting with "postgres://" — psycopg2 needs "postgresql://"
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# ── Decide backend ────────────────────────────────────────────────────────────
USE_SQLITE_FALLBACK = not bool(DATABASE_URL)

if USE_SQLITE_FALLBACK:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')
    print("[DB] Local development mode: using SQLite database.")
else:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        print("[DB] PostgreSQL DATABASE_URL detected.")
    except ImportError:
        # psycopg2 not installed — fall back to SQLite
        import sqlite3
        DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')
        USE_SQLITE_FALLBACK = True
        print("[DB] psycopg2 not installed - falling back to SQLite.")


def get_conn():
    """Returns a live database connection (PostgreSQL or SQLite fallback)."""
    if USE_SQLITE_FALLBACK:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'
    else:
        conn = psycopg2.connect(DATABASE_URL)
        return conn, 'pg'


def _ph(backend):
    """Returns the correct placeholder for the backend (%s for PG, ? for SQLite)."""
    return '%s' if backend == 'pg' else '?'


# ─────────────────────────────────────────────────────────────────────────────
# INIT DB — Creates all tables if they don't exist
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables (users, trips, expenses, activity_logs)."""
    conn, backend = get_conn()
    cur = conn.cursor()

    if backend == 'pg':
        # PostgreSQL uses SERIAL instead of AUTOINCREMENT
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id       SERIAL PRIMARY KEY,
                name     TEXT NOT NULL,
                email    TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS trips (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                trip_name   TEXT NOT NULL,
                destination TEXT NOT NULL,
                start_date  TEXT,
                end_date    TEXT,
                budget      REAL,
                latitude    REAL,
                longitude   REAL,
                stay_type   TEXT DEFAULT 'budget_hotel'
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id          SERIAL PRIMARY KEY,
                trip_id     INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                category    TEXT,
                amount      REAL,
                description TEXT
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER,
                ip_address  TEXT,
                endpoint    TEXT,
                action      TEXT NOT NULL,
                timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    else:
        # SQLite fallback (local dev)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT NOT NULL,
                email    TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS trips (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                trip_name   TEXT NOT NULL,
                destination TEXT NOT NULL,
                start_date  TEXT,
                end_date    TEXT,
                budget      REAL,
                latitude    REAL,
                longitude   REAL,
                stay_type   TEXT DEFAULT 'budget_hotel',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id     INTEGER NOT NULL,
                category    TEXT,
                amount      REAL,
                description TEXT,
                FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                ip_address TEXT,
                endpoint   TEXT,
                action     TEXT NOT NULL,
                timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # SQLite migrations (safe to run every time)
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if 'is_admin' not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")

        cur.execute("PRAGMA table_info(trips)")
        trip_cols = [r[1] for r in cur.fetchall()]
        if 'stay_type' not in trip_cols:
            cur.execute("ALTER TABLE trips ADD COLUMN stay_type TEXT DEFAULT 'budget_hotel'")

    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTH FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def add_user(name, email, hashed_password):
    """Add a new user. Returns True if added, False on duplicate email."""
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    try:
        cur.execute(
            f"INSERT INTO users (name, email, password) VALUES ({ph}, {ph}, {ph})",
            (name, email, hashed_password)
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def get_user_by_email(email):
    """Fetches a user by email. Returns (id, name, hashed_password, is_admin)."""
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    try:
        cur.execute(
            f"SELECT id, name, password, is_admin FROM users WHERE email = {ph}",
            (email,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        # Normalise: both backends return indexable rows
        return (row[0], row[1], row[2], row[3])
    except Exception as e:
        print(f"get_user_by_email error: {e}")
        return None
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2. TRIP FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def add_trip(user_id, trip_name, destination, start_date=None, end_date=None,
             budget=None, latitude=None, longitude=None, stay_type=None):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    try:
        cur.execute(f'''
            INSERT INTO trips
              (user_id, trip_name, destination, start_date, end_date,
               budget, latitude, longitude, stay_type)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
        ''', (user_id, trip_name, destination, start_date, end_date,
              budget, latitude, longitude, stay_type or 'budget_hotel'))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding trip: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def get_user_trips(user_id):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    cur.execute(f"SELECT * FROM trips WHERE user_id = {ph}", (user_id,))
    trips = cur.fetchall()
    cur.close()
    conn.close()
    return [tuple(t) for t in trips]


def get_trip(trip_id):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    cur.execute(f"SELECT * FROM trips WHERE id = {ph}", (trip_id,))
    trip = cur.fetchone()
    cur.close()
    conn.close()
    return tuple(trip) if trip else None


def update_trip(trip_id, trip_name, destination, start_date, end_date,
                budget, latitude, longitude, stay_type=None):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)

    fields, params = [], []
    if trip_name    is not None: fields.append(f"trip_name   = {ph}"); params.append(trip_name)
    if destination  is not None: fields.append(f"destination = {ph}"); params.append(destination)
    if start_date   is not None: fields.append(f"start_date  = {ph}"); params.append(start_date)
    if end_date     is not None: fields.append(f"end_date    = {ph}"); params.append(end_date)
    if budget       is not None: fields.append(f"budget      = {ph}"); params.append(budget)
    if latitude     is not None: fields.append(f"latitude    = {ph}"); params.append(latitude)
    if longitude    is not None: fields.append(f"longitude   = {ph}"); params.append(longitude)
    if stay_type    is not None: fields.append(f"stay_type   = {ph}"); params.append(stay_type)

    if not fields:
        cur.close(); conn.close()
        return True

    try:
        params.append(trip_id)
        cur.execute(f"UPDATE trips SET {', '.join(fields)} WHERE id = {ph}", tuple(params))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating trip: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def delete_trip(trip_id, user_id):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    try:
        cur.execute(f"DELETE FROM trips WHERE id={ph} AND user_id={ph}", (trip_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"Error deleting trip: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 3. EXPENSE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def add_expense(trip_id, category, amount, description):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    try:
        cur.execute(
            f"INSERT INTO expenses (trip_id, category, amount, description) VALUES ({ph},{ph},{ph},{ph})",
            (trip_id, category, amount, description)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding expense: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def get_expenses(trip_id):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    cur.execute(f"SELECT * FROM expenses WHERE trip_id={ph}", (trip_id,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return [tuple(r) for r in data]


# ─────────────────────────────────────────────────────────────────────────────
# 4. ADMIN & ANALYTICS FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def log_activity(user_id, ip_address, endpoint, action):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    try:
        cur.execute(
            f"INSERT INTO activity_logs (user_id, ip_address, endpoint, action) VALUES ({ph},{ph},{ph},{ph})",
            (user_id, ip_address, endpoint, action)
        )
        conn.commit()
    except Exception as e:
        print(f"Failed to log activity: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def get_admin_dashboard_metrics():
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)

    metrics = {"total_users": 0, "total_trips": 0, "recent_logs": [], "today_traffic": 0}
    try:
        cur.execute("SELECT COUNT(id) FROM users")
        metrics["total_users"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(id) FROM trips")
        metrics["total_trips"] = cur.fetchone()[0]

        if backend == 'pg':
            cur.execute("SELECT COUNT(id) FROM activity_logs WHERE timestamp >= CURRENT_DATE")
        else:
            cur.execute("SELECT COUNT(id) FROM activity_logs WHERE timestamp >= date('now')")
        metrics["today_traffic"] = cur.fetchone()[0]

        cur.execute('''
            SELECT a.id, u.name, u.email, a.ip_address, a.endpoint, a.action, a.timestamp
            FROM activity_logs a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.timestamp DESC
            LIMIT 50
        ''')
        metrics["recent_logs"] = [tuple(r) for r in cur.fetchall()]

    except Exception as e:
        print(f"Error fetching metrics: {e}")
    finally:
        cur.close()
        conn.close()

    return metrics


def make_user_admin(email):
    conn, backend = get_conn()
    cur = conn.cursor()
    ph = _ph(backend)
    cur.execute(f"UPDATE users SET is_admin = TRUE WHERE email = {ph}", (email,))
    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 5. AUTO-INIT on import
# ─────────────────────────────────────────────────────────────────────────────
init_db()