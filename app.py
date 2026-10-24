import streamlit as st
from db import init_db
from auth import create_user, verify_login
from profiles import (
    NEED_FIELDS,
    MODES,
    has_profile,
    get_profile,
    save_profile,
)

st.set_page_config(page_title="Board Buddy", page_icon="🚌")
init_db()

NEED_LABELS = {
    "uses_wheelchair": "I use a wheelchair",
    "uses_buggy": "I travel with a buggy or pushchair",
    "uses_mobility_aid": "I use a cane, walker or crutches",
    "low_stamina": "I find it hard to stand for long",
    "visual_impairment": "I have a visual impairment",
    "prefer_not_to_say": "Prefer not to say",
}
CROWDING = {
    1: "Empty",
    2: "Seats available",
    3: "Standing room only",
    4: "Full",
}
BOARD_RANK = {"Likely": 0, "Uncertain": 1, "Unlikely": 2}

# Made-up data. Your teammates' model replaces this later.
DEMO_BUSES = [
]

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "editing" not in st.session_state:
    st.session_state.editing = False


def show_auth():
    st.title("Board Buddy")
    st.caption("Know before you go.")
    tab_in, tab_up = st.tabs(["Log in", "Sign up"])

    with tab_in:
        with st.form("login_form"):
            email = st.text_input("Email", key="li_email")
            pw = st.text_input(
                "Password", type="password", key="li_pw"
            )
            go = st.form_submit_button("Log in")
        if go:
            ok, result = verify_login(email, pw)
            if ok:
                st.session_state.user_id = result
                st.rerun()
            else:
                st.error(result)

    with tab_up:
        with st.form("signup_form"):
            email = st.text_input("Email", key="su_email")
            pw = st.text_input(
                "Password (8+ characters)",
                type="password",
                key="su_pw",
            )
            pw2 = st.text_input(
                "Confirm password",
                type="password",
                key="su_pw2",
            )
            go = st.form_submit_button("Create account")
        if go:
            if pw != pw2:
                st.error("Passwords do not match.")
            else:
                ok, result = create_user(email, pw)
                if ok:
                    st.session_state.user_id = result
                    st.rerun()
                else:
                    st.error(result)


def show_questionnaire(user_id):
    st.title("What would help you travel?")
    st.write("Tick only what you want to. Change it any time.")
    current = get_profile(user_id) or {}

    with st.form("needs_form"):
        picked = {}
        for field in NEED_FIELDS:
            picked[field] = st.checkbox(
                NEED_LABELS[field],
                value=bool(current.get(field, 0)),
            )
        mode = st.selectbox(
            "Preferred transport",
            MODES,
            index=MODES.index(current.get("preferred_mode", "bus")),
        )
        saved = st.form_submit_button("Save")

    if saved:
        ok, msg = save_profile(user_id, picked, mode)
        if ok:
            st.session_state.editing = False
            st.rerun()
        else:
            st.error(msg)

    if current and st.button("Cancel"):
        st.session_state.editing = False
        st.rerun()


def show_main(user_id):
    profile = get_profile(user_id)
    needs_ramp = bool(
        profile["uses_wheelchair"] or profile["uses_buggy"]
    )
    needs_seat = bool(
        profile["uses_mobility_aid"] or profile["low_stamina"]
    )

    with st.sidebar:
        st.write("You are signed in.")
        if st.button("Edit my needs"):
            st.session_state.editing = True
            st.rerun()
        if st.button("Log out"):
            st.session_state.user_id = None
            st.session_state.editing = False
            st.rerun()

    st.title("Board Buddy")
    mode = st.radio(
        "Transport",
        MODES,
        index=MODES.index(profile["preferred_mode"]),
        horizontal=True,
        format_func=str.capitalize,
    )
    if mode != profile["preferred_mode"]:
        needs = {f: profile[f] for f in NEED_FIELDS}
        save_profile(user_id, needs, mode)
    if mode != "bus":
        st.info(f"{mode.capitalize()} is coming soon.")
        return

    buses = list(DEMO_BUSES)
    if needs_ramp:
        buses.sort(
            key=lambda b: (BOARD_RANK[b["board"]], b["crowding"])
        )
        st.subheader("Next buses, easiest to board first")
    elif needs_seat:
        buses.sort(key=lambda b: b["crowding"])
        st.subheader("Next buses, most seats first")
    else:
        buses.sort(key=lambda b: b["time"])
        st.subheader("Next buses")
    st.caption("Demo data for now.")

    for bus in buses:
        with st.container(border=True):
            st.markdown(f"**{bus['route']}** at **{bus['time']}**")
            st.write(f"Crowding: {CROWDING[bus['crowding']]}")
            if needs_ramp:
                st.write(
                    f"Space to board: {bus['board']} "
                    f"(based on {bus['reports']} reports)"
                )
            if needs_seat:
                seat = "Yes" if bus["crowding"] <= 2 else "No"
                st.write(f"Seat likely: {seat}")


user_id = st.session_state.user_id
if user_id is None:
    show_auth()
elif st.session_state.editing or not has_profile(user_id):
    show_questionnaire(user_id)
else:
    show_main(user_id)
