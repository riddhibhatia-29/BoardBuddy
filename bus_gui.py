"""
BoardBuddy - Bus Journey & Safety App (Streamlit GUI)
=====================================================

Two tabs:

🚌 Plan journey
    Look up buses by stop (required), route (optional), destination (required)
    and date (optional). For each bus: scheduled/expected time, delays, arrival
    at the destination, free seats, standing room, accessible bays and crowding.
    If a bus is delayed, cancelled, busy (60%+ full) or has no seat for someone
    who needs one, the user can see alternative buses - less crowded ones first.

🆘 Safety
    Save trusted contacts. Pressing "I'm in danger" gets the phone's/computer's
    location from the browser, builds a safety message with a Google Maps link,
    and gives one-tap buttons to text or WhatsApp it to each trusted contact.

The app reuses the project's existing code and doesn't change it:
    * bus_data.py           -> get_stops(), get_routes(), get_buses(), read_csv()
    * occupancy.py          -> get_availability()
    * alternative_routes.py -> get_alternatives()
    * safety.py             -> setup_database(), add_contact(), get_contacts(),
                               delete_contact(), create_safety_message()

Expected folder layout:
    BoardBuddy/
        bus_gui.py      <- this file
        bus_data.py, occupancy.py, alternative_routes.py, safety.py
        contacts.csv    (created automatically by safety.py)
        data/
            stops.csv, routes.csv, bus_trips.csv, bus_capacity.csv, occupancy.csv

Install and run:
    pip install streamlit pandas streamlit-js-eval
    streamlit run bus_gui.py

streamlit-js-eval is only used to read the browser's location. Without it,
the Safety tab still works but the user types their coordinates in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional
from urllib.parse import quote

import pandas as pd
import streamlit as st

# Existing BoardBuddy code (must be in the same folder as this file)
from bus_data import DATA_DIR, get_buses, get_routes, get_stops, read_csv
from occupancy import get_availability
from alternative_routes import get_alternatives
from safety import (
    add_contact,
    create_safety_message,
    delete_contact,
    get_contacts,
    setup_database,
)

# Optional: reads the user's location from the browser
try:
    from streamlit_js_eval import get_geolocation
    GEOLOCATION_AVAILABLE = True
except ImportError:
    GEOLOCATION_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE = "BoardBuddy"
APP_ICON = "🚌"
ANY_ROUTE = "Any route"  # Label shown when the user doesn't pick a route

# Maps the colour returned by get_availability() to an icon for the tables
CROWDING_ICONS = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}

# When to suggest alternatives (same rules as test_data.py, plus delays)
DELAY_ALERT_MINUTES = 1       # Delays of at least this many minutes count as a problem
CROWDING_ALERT_PERCENT = 60   # Buses this full or more "may not be ideal"
MAX_ALTERNATIVES = 5          # How many alternatives to show

# Safety settings
EMERGENCY_NUMBER = "112"      # Irish/EU emergency number (999 also works in Ireland)
DEFAULT_COUNTRY_CODE = "353"  # Used to turn local numbers like 087... into +353 87...


# ---------------------------------------------------------------------------
# 1. Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stop:
    """A bus stop, built from one row of stops.csv."""
    stop_id: str
    name: str
    area: str

    def __str__(self) -> str:
        # Used by Streamlit selectboxes to show a friendly label
        return f"{self.name} ({self.stop_id})"


@dataclass(frozen=True)
class Departure:
    """One bus calling at the selected stop, ready for display."""
    bus_id: str
    route: str
    service_date: date
    scheduled_time: time
    estimated_time: Optional[time]          # None when the bus is cancelled
    arrival_at_destination: Optional[time]  # Expected time at the destination stop
    status: str                             # "On time", "Delayed" or "Cancelled"
    delay_minutes: int
    availability: Optional[dict]            # Result of get_availability(); None if cancelled

    @property
    def is_cancelled(self) -> bool:
        return self.status.strip().lower() == "cancelled"

    @property
    def expected_datetime(self) -> Optional[datetime]:
        """Date and expected time combined, or None if cancelled."""
        if self.estimated_time is None:
            return None
        return datetime.combine(self.service_date, self.estimated_time)


@dataclass(frozen=True)
class Alternative:
    """A suggested replacement bus, built from one result of get_alternatives()."""
    bus_id: str
    route: str
    stop_id: str
    stop_name: str
    departs: Optional[time]                 # Expected time at the boarding stop
    arrival_at_destination: Optional[time]  # Expected time at the destination stop
    available_seats: int
    occupancy: float
    colour: str                             # "GREEN", "YELLOW" or "RED"
    recommendation: str                     # e.g. "Take another bus route"
    walking_link: Optional[str]             # Google Maps link if it's a different stop


@dataclass
class SearchQuery:
    """Everything the user selected in the search form."""
    stop: Stop
    destination: Stop
    route: Optional[str] = None        # None means "any route"
    travel_date: Optional[date] = None  # None means "any date"


@dataclass(frozen=True)
class Location:
    """A position to share in a safety alert."""
    latitude: float
    longitude: float
    accuracy_m: Optional[float] = None  # Browser's accuracy estimate in metres


# ---------------------------------------------------------------------------
# Small parsing helpers (CSV values are always text)
# ---------------------------------------------------------------------------

def parse_time(text: str) -> Optional[time]:
    """Turn 'HH:MM' into a time object; blank text (e.g. cancelled) gives None."""
    text = (text or "").strip()
    return datetime.strptime(text, "%H:%M").time() if text else None


def parse_int(text: str, default: int = 0) -> int:
    """Turn text into an int, using a default for blank values."""
    text = (text or "").strip()
    return int(text) if text else default


def format_time(value: Optional[time]) -> str:
    """Show a time as HH:MM, or a dash if there isn't one."""
    return value.strftime("%H:%M") if value else "—"


# ---------------------------------------------------------------------------
# 2. Journey data service - bridge to bus_data.py / occupancy.py / alternative_routes.py
# ---------------------------------------------------------------------------

class TransitDataService:
    """
    Gives the journey tab everything it needs, using the project's existing functions.

    The GUI never touches the CSV files directly - if the data source changes
    later (e.g. GTFS or a live API), only this class and bus_data.py need updating.
    """

    def __init__(self) -> None:
        # Stops: {stop_id: Stop} built from bus_data.get_stops()
        self._stops: dict[str, Stop] = {
            row["stop_id"]: Stop(row["stop_id"], row["stop_name"], row.get("area", ""))
            for row in get_stops()
        }
        # Routes: {route_id: [stop_id, stop_id, ...]} in travel order
        self._route_stops = self._load_route_sequences()
        # All dates that have scheduled trips (for the date picker)
        self._service_dates = sorted({
            date.fromisoformat(row["service_date"]) for row in read_csv("bus_trips.csv")
        })

    @staticmethod
    def _load_route_sequences() -> dict[str, list[str]]:
        """Read routes.csv and list each route's stops in sequence order."""
        sequences: dict[str, list[tuple[int, str]]] = {}
        for row in read_csv("routes.csv"):
            sequences.setdefault(row["route_id"], []).append(
                (int(row["illustrative_sequence"]), row["stop_id"])
            )
        return {
            route: [stop_id for _, stop_id in sorted(stops)]
            for route, stops in sequences.items()
        }

    # ----- Queries used by the GUI ----------------------------------------

    def get_stops(self) -> list[Stop]:
        """All stops, sorted alphabetically by name."""
        return sorted(self._stops.values(), key=lambda s: s.name)

    def get_routes(self, stop: Stop) -> list[str]:
        """Routes serving a stop (uses bus_data.get_routes)."""
        return get_routes(stop.stop_id)

    def get_destinations(self, stop: Stop, route: Optional[str] = None) -> list[Stop]:
        """
        Stops you can travel to from `stop`: every stop that comes AFTER it
        on a route serving it (or on the chosen route only).
        """
        routes = [route] if route else self.get_routes(stop)
        destination_ids: set[str] = set()
        for route_id in routes:
            sequence = self._route_stops.get(route_id, [])
            if stop.stop_id in sequence:
                position = sequence.index(stop.stop_id)
                destination_ids.update(sequence[position + 1:])
        return sorted(
            (self._stops[i] for i in destination_ids if i in self._stops),
            key=lambda s: s.name,
        )

    def get_service_dates(self) -> list[date]:
        """Dates that have scheduled trips in bus_trips.csv."""
        return self._service_dates

    def get_departures(self, query: SearchQuery) -> list[Departure]:
        """Buses at the chosen stop that go on to the chosen destination."""
        date_text = query.travel_date.isoformat() if query.travel_date else None

        # bus_data.get_buses() already filters by stop, route and date and
        # merges each trip with its capacity and occupancy rows.
        buses = get_buses(query.stop.stop_id, query.route, date_text)

        # Where each bus is scheduled to be at the destination stop
        destination_trips = self._trips_at_stop(query.destination.stop_id)

        departures = []
        for bus in buses:
            dest_trip = destination_trips.get((bus["bus_id"], bus["service_date"]))
            # Skip buses that never reach the destination after this stop
            if dest_trip is None or dest_trip["scheduled_time"] <= bus["scheduled_time"]:
                continue
            departures.append(self._to_departure(bus, dest_trip))

        # Sort by scheduled time so cancelled buses (blank estimated time) stay in order
        return sorted(departures, key=lambda d: (d.service_date, d.scheduled_time))

    def get_alternatives_for(
        self, departure: Departure, query: SearchQuery, needs_seat: bool = False
    ) -> list[Alternative]:
        """
        Suggest other buses for a delayed, cancelled or crowded departure.

        alternative_routes.get_alternatives() finds the candidates (same stop
        or another stop in the same area). This method then keeps only the
        ones that are useful for this trip:
            * leave no earlier than the original bus was scheduled to, and
            * actually reach the destination after the boarding stop.
        get_alternatives() already lists less crowded buses first; that order is kept.
        """
        suggestions = get_alternatives(
            stop_id=query.stop.stop_id,
            route_id=departure.route,
            bus_id=departure.bus_id,
            service_date=departure.service_date.isoformat(),
            destination_id=query.destination.stop_id,
            needs_seat=needs_seat,
        )

        destination_trips = self._trips_at_stop(query.destination.stop_id)
        earliest = departure.scheduled_time.strftime("%H:%M")
        service_date = departure.service_date.isoformat()

        alternatives = []
        for alt in suggestions:
            # Skip buses that leave before the user's original bus was due
            if not alt["arrival"] or alt["arrival"] < earliest:
                continue
            # Skip buses that don't go on to the destination from the boarding stop
            dest_trip = destination_trips.get((alt["bus_id"], service_date))
            if dest_trip is None or dest_trip["estimated_time"] <= alt["arrival"]:
                continue

            alternatives.append(Alternative(
                bus_id=alt["bus_id"],
                route=alt["route_id"],
                stop_id=alt["stop_id"],
                stop_name=alt["stop_name"],
                departs=parse_time(alt["arrival"]),
                arrival_at_destination=parse_time(dest_trip["estimated_time"]),
                available_seats=alt["available_seats"],
                occupancy=alt["occupancy"],
                colour=alt["colour"],
                recommendation=alt["recommendation"],
                walking_link=alt["walking_link"],
            ))
        return alternatives

    @staticmethod
    def _trips_at_stop(stop_id: str) -> dict[tuple[str, str], dict]:
        """Rows of bus_trips.csv at one stop, keyed by (bus_id, service_date)."""
        return {
            (row["bus_id"], row["service_date"]): row
            for row in read_csv("bus_trips.csv")
            if row["stop_id"] == stop_id
        }

    @staticmethod
    def _to_departure(bus: dict, dest_trip: dict) -> Departure:
        """Convert a merged bus dictionary from get_buses() into a Departure."""
        cancelled = bus["service_status"].strip().lower() == "cancelled"
        return Departure(
            bus_id=bus["bus_id"],
            route=bus["route_id"],
            service_date=date.fromisoformat(bus["service_date"]),
            scheduled_time=parse_time(bus["scheduled_time"]),
            estimated_time=parse_time(bus["estimated_time"]),
            arrival_at_destination=parse_time(dest_trip["estimated_time"]),
            status=bus["service_status"],
            delay_minutes=parse_int(bus["delay_minutes"]),
            # occupancy.get_availability() works out free seats, bays and crowding
            availability=None if cancelled else get_availability(bus),
        )


# Cache the service so stops and routes are loaded once, not on every rerun
@st.cache_resource
def get_data_service() -> TransitDataService:
    return TransitDataService()


# ---------------------------------------------------------------------------
# 3. Safety service - bridge to safety.py
# ---------------------------------------------------------------------------

class SafetyService:
    """Trusted contacts and safety alerts for one user, using safety.py."""

    def __init__(self, user: str) -> None:
        self.user = user
        setup_database()  # Creates contacts.csv if it doesn't exist yet

    def contacts(self) -> list[dict]:
        """This user's saved contacts: [{'user', 'name', 'phone'}, ...]."""
        return get_contacts(self.user)

    def add(self, name: str, phone: str) -> None:
        """Save a contact. Raises ValueError if something is missing or invalid."""
        if name.strip().lower() in {c["name"].strip().lower() for c in self.contacts()}:
            raise ValueError(f"You already have a contact called {name.strip()}.")
        if len(re.sub(r"\D", "", phone)) < 7:
            raise ValueError("Please enter a full phone number (at least 7 digits).")
        add_contact(self.user, name, phone)

    def remove(self, name: str) -> bool:
        """Delete a contact by name. Returns True if one was deleted."""
        return delete_contact(name, self.user) > 0

    def alert_message(self, location: Location) -> str:
        """The safety message with a Google Maps link to the location."""
        return create_safety_message(self.user, location.latitude, location.longitude)


def international_number(phone: str) -> str:
    """
    Digits-only international number for SMS/WhatsApp links.
    '087 123 4567' -> '353871234567', '+44 7700 900123' -> '447700900123'.
    """
    digits = re.sub(r"\D", "", phone)
    if phone.strip().startswith("+"):
        return digits
    if digits.startswith("00"):
        return digits[2:]
    if digits.startswith("0"):
        return DEFAULT_COUNTRY_CODE + digits[1:]
    return digits


def sms_link(phone: str, message: str) -> str:
    """Link that opens the phone's messaging app with the message filled in."""
    return f"sms:+{international_number(phone)}?&body={quote(message)}"


def whatsapp_link(phone: str, message: str) -> str:
    """Link that opens WhatsApp with the message filled in."""
    return f"https://wa.me/{international_number(phone)}?text={quote(message)}"


def location_from_browser(result) -> tuple[Optional[Location], Optional[str]]:
    """
    Read the value returned by streamlit_js_eval.get_geolocation().
    Returns (location, None) on success, (None, error message) on failure,
    or (None, None) while the browser is still working it out.
    """
    if not result:
        return None, None
    if isinstance(result, dict) and "coords" in result:
        coords = result["coords"]
        return Location(coords["latitude"], coords["longitude"], coords.get("accuracy")), None
    if isinstance(result, dict) and "error" in result:
        error = result["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        return None, message or "Location access was blocked."
    return None, "Couldn't read your location."


# ---------------------------------------------------------------------------
# Journey display helpers
# ---------------------------------------------------------------------------

def status_label(dep: Departure) -> str:
    """Short status text, e.g. 'On time', 'Delayed +4 min' or 'Cancelled'."""
    if dep.is_cancelled:
        return "❌ Cancelled"
    if dep.delay_minutes > 0:
        return f"⚠️ Delayed +{dep.delay_minutes} min"
    return "✅ On time"


def problem_reasons(dep: Departure, needs_seat: bool = False) -> list[str]:
    """
    Why a passenger might want an alternative to this bus (empty list = it's fine).
    Follows test_data.py: 60%+ full, or no seat for someone who needs one,
    plus delays and cancellations.
    """
    if dep.is_cancelled:
        return ["Cancelled"]
    reasons = []
    info = dep.availability
    if dep.delay_minutes >= DELAY_ALERT_MINUTES:
        reasons.append(f"Delayed +{dep.delay_minutes} min")
    if info["occupancy_percentage"] >= CROWDING_ALERT_PERCENT:
        reasons.append(f"{info['crowding']} ({info['occupancy_percentage']:.0f}% full)")
    if needs_seat and info["available_seats"] == 0:
        reasons.append("No seats free")
    return reasons


def prefer_less_crowded(
    alternatives: list[Alternative], chosen: Departure
) -> tuple[list[Alternative], bool]:
    """
    As in test_data.py: keep only alternatives less crowded than the chosen bus.
    Returns (alternatives to show, True if less crowded ones were found).
    If none are less crowded, all alternatives are returned instead.
    """
    if chosen.availability is None:  # Cancelled bus - any working bus is better
        return alternatives, True
    current = chosen.availability["occupancy_percentage"]
    better = [alt for alt in alternatives if alt.occupancy < current]
    return (better, True) if better else (alternatives, False)


def next_departure(departures: list[Departure]) -> Optional[Departure]:
    """The first bus that isn't cancelled and hasn't left yet."""
    now = datetime.now()
    for dep in departures:
        if not dep.is_cancelled and dep.expected_datetime and dep.expected_datetime >= now:
            return dep
    return None


def departures_to_dataframe(departures: list[Departure]) -> pd.DataFrame:
    """Convert departures into a table ready for display."""
    rows = []
    for dep in departures:
        info = dep.availability or {}  # Empty for cancelled buses
        rows.append({
            "Route": dep.route,
            "Bus": dep.bus_id,
            "Date": dep.service_date.strftime("%a %d %b"),
            "Scheduled": format_time(dep.scheduled_time),
            "Expected": format_time(dep.estimated_time),
            "Status": status_label(dep),
            "Arrives at destination": format_time(dep.arrival_at_destination),
            "Seats free": info.get("available_seats"),
            "Standing free": info.get("available_standing"),
            "Wheelchair bays": info.get("available_wheelchair_bays"),
            "Shared bays": info.get("available_shared_bays"),
            "Occupancy": info.get("occupancy_percentage"),
            "Crowding": (f"{CROWDING_ICONS.get(info['colour'], '')} {info['crowding']}"
                         if info else "—"),
        })
    return pd.DataFrame(rows)


def alternatives_to_dataframe(alternatives: list[Alternative]) -> pd.DataFrame:
    """Convert alternative buses into a table ready for display."""
    return pd.DataFrame([{
        "Suggestion": alt.recommendation,
        "Route": alt.route,
        "Bus": alt.bus_id,
        "Board at": alt.stop_name,
        "Departs": format_time(alt.departs),
        "Arrives at destination": format_time(alt.arrival_at_destination),
        "Seats free": alt.available_seats,
        "Occupancy": alt.occupancy,
        "Crowding": CROWDING_ICONS.get(alt.colour, ""),
        "Walking directions": alt.walking_link,  # None when boarding at the same stop
    } for alt in alternatives])


# Column settings shared by both tables
NUMBER_COLUMNS = {
    name: st.column_config.NumberColumn(name, format="%d")
    for name in ("Seats free", "Standing free", "Wheelchair bays", "Shared bays")
}
OCCUPANCY_COLUMN = st.column_config.ProgressColumn(
    "Occupancy", min_value=0, max_value=100, format="%.0f%%"
)


# ---------------------------------------------------------------------------
# 4. User interface
# ---------------------------------------------------------------------------

class BoardBuddyApp:
    """Draws the Streamlit GUI: a journey tab and a safety tab."""

    def __init__(self) -> None:
        self.data: Optional[TransitDataService] = None

    # ----- Shared sections -------------------------------------------------

    def render_header(self) -> None:
        """Title and short description at the top of the page."""
        st.title(f"{APP_ICON} {APP_TITLE}")
        st.caption(
            "Find buses, see how much space is on board, and stay safe on your journey. "
            "Demo data: schedules and occupancy are simulated, not real-time."
        )

    def render_user_box(self) -> str:
        """Sidebar box for the demo username (as in test_data.py - not a secure login)."""
        st.sidebar.header("👤 You")
        user = st.sidebar.text_input(
            "Your name",
            key="user",
            help="Demo username - used to keep your trusted contacts separate. Not a secure login.",
        ).strip()
        if not user:
            st.sidebar.info("Enter your name to use the Safety tab.")
        return user

    # ----- Journey tab -----------------------------------------------------

    def render_journey_tab(self) -> None:
        """Search form, results and alternatives."""
        query = self.render_search_form()

        # Remember the last search so results stay visible after other clicks
        if query is not None:
            st.session_state["last_query"] = query

        last_query = st.session_state.get("last_query")
        if last_query:
            self.render_results(last_query)
        else:
            st.info("Choose a stop and destination above, then press **Search**.")

    def render_search_form(self) -> Optional[SearchQuery]:
        """
        Show the search controls at the top of the journey tab.
        Returns a SearchQuery when the user presses Search, otherwise None.
        """
        col1, col2 = st.columns(2)

        # Stop (required)
        stop: Stop = col1.selectbox(
            "Bus stop", options=self.data.get_stops(), format_func=str
        )

        # Route (optional) - list depends on the chosen stop
        route_choice = col2.selectbox(
            "Route number (optional)",
            options=[ANY_ROUTE] + self.data.get_routes(stop),
        )
        route = None if route_choice == ANY_ROUTE else route_choice

        # Destination (required) - stops later on the route(s)
        col3, col4 = st.columns(2)
        destinations = self.data.get_destinations(stop, route)
        if not destinations:
            col3.warning("No onward stops from here on this route - it may be the last stop.")
            return None
        destination: Stop = col3.selectbox(
            "Destination", options=destinations, format_func=str
        )

        # Date (optional) - only shown if the user ticks the box
        travel_date = None
        service_dates = self.data.get_service_dates()
        with col4:
            if service_dates and st.checkbox("Choose a specific date"):
                travel_date = st.date_input(
                    "Travel date",
                    value=service_dates[0],
                    min_value=service_dates[0],
                    max_value=service_dates[-1],
                )

        if st.button("Search", type="primary"):
            return SearchQuery(stop=stop, destination=destination,
                               route=route, travel_date=travel_date)
        return None

    def render_summary(self, running: list[Departure], cancelled: list[Departure]) -> None:
        """Key figures above the results table."""
        nxt = next_departure(running)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Buses running", len(running))
        if nxt:
            col2.metric(f"Next bus · route {nxt.route}", format_time(nxt.estimated_time),
                        nxt.service_date.strftime("%a %d %b"), delta_color="off")
            col3.metric("Seats free on next bus", nxt.availability["available_seats"],
                        nxt.availability["crowding"], delta_color="off")
        else:
            col2.metric("Next bus", "—")
            col3.metric("Seats free on next bus", "—")
        col4.metric("Cancelled", len(cancelled))

    def render_results(self, query: SearchQuery) -> None:
        """Show the buses that match the search."""
        departures = self.data.get_departures(query)

        st.subheader(f"{query.stop.name} → {query.destination.name}")
        date_text = (query.travel_date.strftime("%A %d %B %Y")
                     if query.travel_date else "All dates")
        st.write(f"**Date:** {date_text} · **Route:** {query.route or ANY_ROUTE}")

        if not departures:
            st.info("No buses found for this search. Try another route or date.")
            return

        # As in test_data.py, cancelled buses are left out of the main list
        running = [dep for dep in departures if not dep.is_cancelled]
        cancelled = [dep for dep in departures if dep.is_cancelled]

        self.render_summary(running, cancelled)
        if running:
            st.dataframe(
                departures_to_dataframe(running),
                hide_index=True,
                width="stretch",
                column_config={**NUMBER_COLUMNS, "Occupancy": OCCUPANCY_COLUMN},
            )
        if cancelled:
            with st.expander(f"❌ {len(cancelled)} cancelled service(s)"):
                st.dataframe(
                    departures_to_dataframe(cancelled)[["Route", "Bus", "Date", "Scheduled"]],
                    hide_index=True,
                )

        self.render_alternatives(query, departures)

    def render_alternatives(self, query: SearchQuery, departures: list[Departure]) -> None:
        """Let the user pick a bus that may not suit them and see other options."""
        st.divider()
        st.subheader("🔀 Alternative buses")

        needs_seat = st.checkbox("I need a seat", help="Flags and skips buses with no free seats")

        # Buses that may not be ideal (delayed, cancelled, busy, or no seat when needed)
        problem_buses = [dep for dep in departures if problem_reasons(dep, needs_seat)]
        if not problem_buses:
            st.success("All buses for this search are on time and have plenty of space.")
            return

        st.write(f"{len(problem_buses)} bus(es) may not be ideal for you. "
                 "BoardBuddy can suggest alternatives:")

        # Pick a bus by its position in the list (Departure holds a dict, so it isn't hashable)
        index = st.selectbox(
            "Show alternatives for",
            options=range(len(problem_buses)),
            format_func=lambda i: (
                f"Route {problem_buses[i].route} · {problem_buses[i].bus_id} · "
                f"{problem_buses[i].service_date.strftime('%a %d %b')} "
                f"{format_time(problem_buses[i].scheduled_time)} — "
                f"{', '.join(problem_reasons(problem_buses[i], needs_seat))}"
            ),
        )
        chosen = problem_buses[index]

        alternatives = self.data.get_alternatives_for(chosen, query, needs_seat)
        if not alternatives:
            st.warning(
                "No suitable alternatives found that reach your destination after this "
                "bus was due. Try unticking 'I need a seat' or choosing another bus."
            )
            return

        # Prefer less crowded buses, then show the top few
        alternatives, found_better = prefer_less_crowded(alternatives, chosen)
        if not found_better:
            st.info("No less-crowded alternatives found. Showing other possible buses.")
        shown = alternatives[:MAX_ALTERNATIVES]

        st.caption(
            f"Showing {len(shown)} of {len(alternatives)} option(s) leaving from "
            f"{format_time(chosen.scheduled_time)} onwards that reach "
            f"{query.destination.name}, least crowded first. "
            "Walking distances to other stops have not been verified."
        )
        st.dataframe(
            alternatives_to_dataframe(shown),
            hide_index=True,
            width="stretch",
            column_config={
                "Seats free": NUMBER_COLUMNS["Seats free"],
                "Occupancy": OCCUPANCY_COLUMN,
                "Walking directions": st.column_config.LinkColumn(
                    "Walking directions", display_text="Open in Google Maps"
                ),
            },
        )

    # ----- Safety tab ------------------------------------------------------

    def render_safety_tab(self, user: str) -> None:
        """Trusted contacts and the 'I'm in danger' alert."""
        st.error(
            f"**In immediate danger? Call {EMERGENCY_NUMBER} or 999.** "
            "BoardBuddy alerts are for letting people you trust know where you are."
        )
        st.link_button(f"📞 Call {EMERGENCY_NUMBER}", f"tel:{EMERGENCY_NUMBER}")

        if not user:
            st.info("👈 Enter your name in the sidebar to save contacts and send alerts.")
            return

        safety = SafetyService(user)
        contacts = safety.contacts()

        self.render_danger_alert(safety, contacts)
        st.divider()
        self.render_contacts(safety, contacts)

    def render_danger_alert(self, safety: SafetyService, contacts: list[dict]) -> None:
        """The big button, then location + one-tap send links for each contact."""
        st.subheader("🆘 Alert my trusted contacts")

        if not contacts:
            st.warning("Add at least one trusted contact below before using the alert.")
            return

        if not st.session_state.get("alert_active"):
            if st.button("🆘 I'm in danger", type="primary", width="stretch"):
                st.session_state["alert_active"] = True
                # New key each time so the browser is asked for a fresh location
                st.session_state["alert_count"] = st.session_state.get("alert_count", 0) + 1
                st.rerun()
            st.caption("Gets your current location and lets you send it to your contacts.")
            return

        location = self.get_location()
        if location is None:
            if st.button("Cancel alert"):
                st.session_state["alert_active"] = False
                st.rerun()
            return

        message = safety.alert_message(location)

        st.success("Your location is ready. Tap a button to send it - "
                   "your messaging app opens with the message filled in.")
        for contact in contacts:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.markdown(f"**{contact['name']}**  \n{contact['phone']}")
            col2.link_button("📱 Text", sms_link(contact["phone"], message), width="stretch")
            col3.link_button("💬 WhatsApp", whatsapp_link(contact["phone"], message),
                             width="stretch")

        with st.expander("Message and map"):
            st.code(message, language=None)  # Has a copy button
            st.map(pd.DataFrame({"lat": [location.latitude], "lon": [location.longitude]}),
                   zoom=15)
            if location.accuracy_m:
                st.caption(f"Location accurate to about {location.accuracy_m:.0f} m.")

        if st.button("✅ I'm safe now - end alert"):
            st.session_state["alert_active"] = False
            st.rerun()

    def get_location(self) -> Optional[Location]:
        """
        Get the user's location from the browser, or let them type it in.
        Returns None until a location is available.
        """
        if GEOLOCATION_AVAILABLE:
            key = f"geolocation_{st.session_state.get('alert_count', 0)}"
            location, error = location_from_browser(get_geolocation(component_key=key))
            if location:
                return location
            if error is None:
                st.info("📍 Getting your location... allow location access if your browser asks.")
                return None
            st.warning(f"Couldn't get your location automatically ({error}). "
                       "Enter it below instead.")
        else:
            st.warning("Automatic location isn't set up (run `pip install streamlit-js-eval`). "
                       "Enter your coordinates below - e.g. from Google Maps.")
        return self.manual_location()

    @staticmethod
    def manual_location() -> Optional[Location]:
        """Typed-in coordinates, checked the same way as test_data.py."""
        col1, col2 = st.columns(2)
        lat_text = col1.text_input("Latitude", placeholder="e.g. 53.3498")
        lon_text = col2.text_input("Longitude", placeholder="e.g. -6.2603")
        if not lat_text or not lon_text:
            return None
        try:
            latitude, longitude = float(lat_text), float(lon_text)
        except ValueError:
            st.error("Please enter valid coordinates.")
            return None
        if not -90 <= latitude <= 90:
            st.error("Invalid latitude.")
            return None
        if not -180 <= longitude <= 180:
            st.error("Invalid longitude.")
            return None
        return Location(latitude, longitude)

    def render_contacts(self, safety: SafetyService, contacts: list[dict]) -> None:
        """List, add and delete trusted contacts."""
        st.subheader("👥 Trusted contacts")

        if "flash" in st.session_state:
            st.success(st.session_state.pop("flash"))

        if contacts:
            for i, contact in enumerate(contacts):
                col1, col2 = st.columns([4, 1])
                col1.markdown(f"**{contact['name']}** — {contact['phone']}")
                if col2.button("Delete", key=f"delete_{i}_{contact['name']}"):
                    safety.remove(contact["name"])
                    st.rerun()
        else:
            st.info("No trusted contacts saved yet.")

        # A form so the inputs clear after saving
        with st.form("add_contact", clear_on_submit=True):
            st.markdown("**Add a trusted contact**")
            col1, col2 = st.columns(2)
            name = col1.text_input("Contact name")
            phone = col2.text_input("Phone number", placeholder="e.g. 087 123 4567")
            if st.form_submit_button("Save contact"):
                try:
                    safety.add(name, phone)
                    # Shown after the rerun, so it isn't lost
                    st.session_state["flash"] = f"Saved {name.strip()} as a trusted contact."
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

    # ----- Main entry point -----------------------------------------------

    def run(self) -> None:
        """Build the whole page."""
        st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
        self.render_header()
        user = self.render_user_box()

        # Load the bus data, with a clear message if the CSV files can't be found
        try:
            self.data = get_data_service()
        except FileNotFoundError as error:
            st.error(
                f"Couldn't find a data file: {error.filename}\n\n"
                f"Put the CSV files in this folder: {DATA_DIR}"
            )
            st.stop()

        journey_tab, safety_tab = st.tabs(["🚌 Plan journey", "🆘 Safety"])
        with journey_tab:
            self.render_journey_tab()
        with safety_tab:
            self.render_safety_tab(user)


# ---------------------------------------------------------------------------
# Run the app
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    BoardBuddyApp().run()
