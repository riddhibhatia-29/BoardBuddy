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

GREEN = "#1F5B4B"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp, button, input, select {{
    font-family: 'Plus Jakarta Sans', system-ui, sans-serif !important;
}}

/* Background: cream with soft mint glows */
.stApp {{
    background:
        radial-gradient(circle at 0% 0%, #BFE0CF 0%, rgba(191,224,207,0) 55%),
        radial-gradient(circle at 100% 100%, #A9D3C0 0%, rgba(169,211,192,0) 55%),
        radial-gradient(circle at 100% 12%, #D3EADF 0%, rgba(211,234,223,0) 40%),
        #F4F7F1;
    color: #14352C;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
footer, #MainMenu {{ visibility: hidden; }}

/* Narrow, phone-like column */
.block-container {{
    max-width: 440px;
    padding-top: 3rem;
    padding-bottom: 3rem;
}}

/* Hero */
.bb-hero {{ display: flex; align-items: center; gap: 14px; }}
.bb-icon {{
    width: 64px; height: 64px; border-radius: 50%;
    background: #D9E8E0; display: flex;
    align-items: center; justify-content: center; flex: none;
}}
.bb-title {{
    margin: 0; padding: 0; font-size: 38px; line-height: 1; font-weight: 800;
    letter-spacing: -0.03em; color: {GREEN};
}}
.bb-tag {{ margin: 22px 0 0 0; font-size: 18px; font-weight: 700; }}
.bb-sub {{
    margin: 8px 0 24px 0; font-size: 15px; line-height: 1.55; color: #5C6B64;
}}
.bb-h2 {{
    margin: 18px 0 6px 0; padding: 0; font-size: 30px; line-height: 1.12;
    font-weight: 800; letter-spacing: -0.03em; color: {GREEN};
}}

/* Tabs as a pill switch */
[data-baseweb="tab-list"] {{
    background: #E9EBE3; border-radius: 999px; padding: 4px; gap: 0;
}}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{ display: none; }}
button[role="tab"] {{
    flex: 1; border-radius: 999px; height: 44px;
    color: #3F5F55; font-weight: 600; justify-content: center;
}}
button[role="tab"][aria-selected="true"] {{
    background: {GREEN}; color: #FFFFFF; font-weight: 700;
}}
button[role="tab"][aria-selected="true"] p {{ color: #FFFFFF; }}

/* Forms: no box */
[data-testid="stForm"] {{
    border: none; padding: 0; background: transparent;
}}

/* Inputs */
div[data-baseweb="input"], div[data-baseweb="select"] > div {{
    background: #FBFBF8; border: 1px solid #D7DBD1;
    border-radius: 16px; min-height: 52px;
}}
div[data-baseweb="input"] input {{ background: transparent; font-size: 16px; }}
div[data-baseweb="input"] > div {{ background: transparent; }}
label p {{ font-weight: 700; font-size: 14px; }}

/* Checkboxes as rounded rows, green when ticked */
[data-testid="stCheckbox"] label {{
    background: #FBFBF8; border: 1px solid #D7DBD1; border-radius: 16px;
    padding: 14px 16px; width: 100%; align-items: center;
}}
[data-testid="stCheckbox"] label p {{ font-weight: 500; font-size: 16px; }}
label[data-baseweb="checkbox"]:has(input:checked) > span:first-child {{
    background-color: {GREEN} !important;
    border-color: {GREEN} !important;
}}

/* Buttons */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {{
    background: {GREEN}; color: #FFFFFF; border: 0;
    border-radius: 999px; height: 56px; width: 100%;
    font-size: 17px; font-weight: 700;
}}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {{
    background: #174A3C; color: #FFFFFF; border: 0;
}}
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondaryFormSubmit"] {{
    background: #FBFBF8; color: #14352C; border: 1px solid #D7DBD1;
    border-radius: 999px; height: 56px; width: 100%;
    font-size: 16px; font-weight: 600;
}}
[data-testid="stBaseButton-secondary"]:hover {{
    border-color: {GREEN}; color: {GREEN};
}}
</style>
"""

BUS_ICON = (
    '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" '
    f'stroke="{GREEN}" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round"><rect x="4" y="3" width="16" height="14" rx="3"/>'
    '<path d="M4 11h16"/><path d="M7 20v-3M17 20v-3"/></svg>'
)

st.markdown(CSS, unsafe_allow_html=True)

NEED_LABELS = {
    "uses_wheelchair": "I use a wheelchair",
    "uses_buggy": "I travel with a buggy or pushchair",
    "uses_mobility_aid": "I use a cane, walker or crutches",
    "low_stamina": "I find it hard to stand for long",
    "visual_impairment": "I have a visual impairment",
    "prefer_not_to_say": "Prefer not to say",
}

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "editing" not in st.session_state:
    st.session_state.editing = False


def hero():
    st.markdown(
        f"""
        <div class="bb-hero">
          <div class="bb-icon">{BUS_ICON}</div>
          <h1 class="bb-title">Board Buddy</h1>
        </div>
        <p class="bb-tag">Know before you go.</p>
        <p class="bb-sub">Real-time information on crowding and accessible
        space, so you can plan your journey with confidence.</p>
        """,
        unsafe_allow_html=True,
    )


def heading(text):
    st.markdown(
        f'<div class="bb-icon" style="width:56px;height:56px">{BUS_ICON}</div>'
        f'<h2 class="bb-h2">{text}</h2>',
        unsafe_allow_html=True,
    )


def show_auth():
    hero()
    tab_in, tab_up = st.tabs(["Log in", "Sign up"])

    with tab_in:
        with st.form("login_form"):
            email = st.text_input(
                "Email address", placeholder="you@example.com", key="li_email"
            )
            pw = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="li_pw",
            )
            go = st.form_submit_button("Log in  →", type="primary")
        if go:
            ok, result = verify_login(email, pw)
            if ok:
                st.session_state.user_id = result
                st.rerun()
            else:
                st.error(result)

    with tab_up:
        with st.form("signup_form"):
            email = st.text_input(
                "Email address", placeholder="you@example.com", key="su_email"
            )
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
            go = st.form_submit_button("Create account  →", type="primary")
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
    heading("What would help you travel?")
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
        saved = st.form_submit_button("Save  →", type="primary")

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
    heading("Board Buddy")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Edit my needs"):
            st.session_state.editing = True
            st.rerun()
    with col2:
        if st.button("Log out"):
            st.session_state.user_id = None
            st.session_state.editing = False
            st.rerun()

    # Teammates' bus screen plugs in here (bus_screen.py with
    # show_bus_screen(user_id)). Safe to run before it exists.
    try:
        from bus_screen import show_bus_screen
        show_bus_screen(user_id)
    except ImportError:
        st.info("Bus screen not connected yet.")


user_id = st.session_state.user_id
if user_id is None:
    show_auth()
elif st.session_state.editing or not has_profile(user_id):
    show_questionnaire(user_id)
else:
    show_main(user_id)