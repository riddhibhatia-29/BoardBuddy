import sqlite3
import bcrypt
from db import get_connection

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  


def clean_email(email):
    """Trim spaces and lowercase, so Me@x.com and me@x.com match."""
    return email.strip().lower()


def check_inputs(email, password):
    """Return an error message, or None if everything is fine."""
    domain = email.split("@")[-1]
    if "@" not in email or "." not in domain:
        return "Please enter a valid email address."
    if len(password) < MIN_PASSWORD_LENGTH:
        return "Password must be at least 8 characters."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "Password is too long."
    return None


def create_user(email, password):
    """Sign up. Returns (True, user_id) or (False, error message)."""
    email = clean_email(email)
    error = check_inputs(email, password)
    if error:
        return False, error

    hashed = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, hashed),
        )
        conn.commit()
        return True, cur.lastrowid
    except sqlite3.IntegrityError:
        return False, "That email is already registered."
    finally:
        conn.close()


def verify_login(email, password):
    """Log in. Returns (True, user_id) or (False, error message)."""
    email = clean_email(email)
    wrong = (False, "Incorrect email or password.")

    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return wrong

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return wrong

    matches = bcrypt.checkpw(
        password.encode("utf-8"),
        row["password_hash"].encode("utf-8"),
    )
    if matches:
        return True, row["id"]
    return wrong


if __name__ == "__main__":
    from db import init_db
    init_db()
    test = "test@example.com"

    print(create_user(test, "short"))
    print(create_user(test, "longenough1"))
    print(create_user(test, "longenough1"))
    print(verify_login(test, "longenough1"))
    print(verify_login(test, "wrongpass99"))
    print(verify_login("nobody@example.com", "whatever99"))

    conn = get_connection()
    conn.execute("DELETE FROM users WHERE email = ?", (test,))
    conn.commit()
    conn.close()
    print("Test user cleaned up.")
