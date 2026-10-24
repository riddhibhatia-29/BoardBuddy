import sqlite3

DB_NAME = "boardbuddy.db"


def get_connection():
    """Open the database. Call this whenever you need to read or write."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row            # lets you write row["email"]
    conn.execute("PRAGMA foreign_keys = ON")  # needed for ON DELETE CASCADE
    return conn


def init_db():
    """Create the tables if they don't exist yet. Safe to run many times."""
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id           INTEGER PRIMARY KEY
                              REFERENCES users(id) ON DELETE CASCADE,
            uses_wheelchair   INTEGER NOT NULL DEFAULT 0 CHECK (uses_wheelchair IN (0, 1)),
            uses_buggy        INTEGER NOT NULL DEFAULT 0 CHECK (uses_buggy IN (0, 1)),
            uses_mobility_aid INTEGER NOT NULL DEFAULT 0 CHECK (uses_mobility_aid IN (0, 1)),
            low_stamina       INTEGER NOT NULL DEFAULT 0 CHECK (low_stamina IN (0, 1)),
            visual_impairment INTEGER NOT NULL DEFAULT 0 CHECK (visual_impairment IN (0, 1)),
            prefer_not_to_say INTEGER NOT NULL DEFAULT 0 CHECK (prefer_not_to_say IN (0, 1)),
            preferred_mode    TEXT NOT NULL DEFAULT 'bus'
                              CHECK (preferred_mode IN ('bus', '', 'train')),
            updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database ready.")
