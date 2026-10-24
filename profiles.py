from db import get_connection

NEED_FIELDS = [
    "uses_wheelchair",
    "uses_buggy",
    "uses_mobility_aid",
    "low_stamina",
    "visual_impairment",
    "prefer_not_to_say",
]
MODES = ["bus", "tram", "train"]


def has_profile(user_id):
    """True if this user has finished the questionnaire."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    return row is not None


def get_profile(user_id):
    """Return the profile as a dict, or None if there isn't one."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return dict(row)


def save_profile(user_id, needs, preferred_mode="bus"):
    """Create or update a profile. Returns (True, None) or (False, msg).

    needs is a dict like {"uses_wheelchair": True}.
    Missing keys count as False.
    """
    if preferred_mode not in MODES:
        return False, "Please choose bus, tram or train."

    values = {f: 1 if needs.get(f) else 0 for f in NEED_FIELDS}
    if values["prefer_not_to_say"]:
        values = {f: 0 for f in NEED_FIELDS}
        values["prefer_not_to_say"] = 1

    columns = ", ".join(NEED_FIELDS)
    marks = ", ".join("?" for _ in NEED_FIELDS)
    updates = ", ".join(f"{f} = excluded.{f}" for f in NEED_FIELDS)
    sql = (
        f"INSERT INTO profiles (user_id, {columns}, preferred_mode) "
        f"VALUES (?, {marks}, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        f"{updates}, "
        "preferred_mode = excluded.preferred_mode, "
        "updated_at = CURRENT_TIMESTAMP"
    )
    params = [user_id]
    params += [values[f] for f in NEED_FIELDS]
    params.append(preferred_mode)

    conn = get_connection()
    try:
        conn.execute(sql, params)
        conn.commit()
        return True, None
    except Exception:
        return False, "Could not save your profile."
    finally:
        conn.close()


if __name__ == "__main__":
    from db import init_db
    from auth import create_user

    init_db()
    test = "profiletest@example.com"

    def remove_test_user():
        conn = get_connection()
        conn.execute("DELETE FROM users WHERE email = ?", (test,))
        conn.commit()
        conn.close()

    remove_test_user()
    ok, uid = create_user(test, "longenough1")
    print("1.", ok, uid)
    print("2.", has_profile(uid), get_profile(uid))
    print("3.", save_profile(uid, {"uses_wheelchair": True}))
    print("4.", has_profile(uid), get_profile(uid))
    print("5.", save_profile(uid, {"uses_buggy": True}, "tram"))
    print("6.", get_profile(uid))
    print("7.", save_profile(uid, {}, "plane"))
    both = {"prefer_not_to_say": True, "low_stamina": True}
    print("8.", save_profile(uid, both))
    print("9.", get_profile(uid))
    print("10.", save_profile(99999, {}))
    remove_test_user()
    print("11.", has_profile(uid))
