"""
BoardBuddy - Bus Departure & Occupancy Viewer
=============================================

A Streamlit GUI that lets a user look up buses by:
    * Stop            (required)
    * Route number    (optional - "Any route" by default)
    * Destination     (required - any stop later on a route serving the chosen stop)
    * Date            (optional - all dates by default)

For every matching bus it shows the scheduled and expected time, delays or
cancellations, the expected arrival at the destination, and how much space
is free on board (seats, standing, wheelchair and shared bays, crowding).

The app reuses the project's existing data code instead of reading the CSVs itself:
    * bus_data.py   -> get_stops(), get_routes(), get_buses(), read_csv()
    * occupancy.py  -> get_availability()

Expected folder layout:
    BoardBuddy/
        app.py          <- this file
        bus_data.py
        occupancy.py
        data/
            stops.csv, routes.csv, bus_trips.csv, bus_capacity.csv, occupancy.csv

Run with:
    streamlit run app.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional

import pandas as pd
import streamlit as st

# Existing BoardBuddy data-handling code (must be in the same folder as this file)
from bus_data import DATA_DIR, get_buses, get_routes, get_stops, read_csv
from occupancy import get_availability


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE = "BoardBuddy"
APP_ICON = "🚌"
ANY_ROUTE = "Any route"  # Label shown when the user doesn't pick a route

# Maps the colour returned by get_availability() to an icon for the table
CROWDING_ICONS = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}


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


@dataclass
class SearchQuery:
    """Everything the user selected in the search form."""
    stop: Stop
    destination: Stop
    route: Optional[str] = None        # None means "any route"
    travel_date: Optional[date] = None  # None means "any date"


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
# 2. Data service - the bridge between the GUI and bus_data.py / occupancy.py
# ---------------------------------------------------------------------------

class TransitDataService:
    """
    Gives the GUI everything it needs, using the project's existing functions.

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
        destination_trips = {
            (row["bus_id"], row["service_date"]): row
            for row in read_csv("bus_trips.csv")
            if row["stop_id"] == query.destination.stop_id
        }

        departures = []
        for bus in buses:
            dest_trip = destination_trips.get((bus["bus_id"], bus["service_date"]))
            # Skip buses that never reach the destination after this stop
            if dest_trip is None or dest_trip["scheduled_time"] <= bus["scheduled_time"]:
                continue
            departures.append(self._to_departure(bus, dest_trip))

        # Sort by scheduled time so cancelled buses (blank estimated time) stay in order
        return sorted(departures, key=lambda d: (d.service_date, d.scheduled_time))

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
# Display helpers
# ---------------------------------------------------------------------------

def status_label(dep: Departure) -> str:
    """Short status text, e.g. 'On time', 'Delayed +4 min' or 'Cancelled'."""
    if dep.is_cancelled:
        return "❌ Cancelled"
    if dep.delay_minutes > 0:
        return f"⚠️ Delayed +{dep.delay_minutes} min"
    return "✅ On time"


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


# ---------------------------------------------------------------------------
# 3. User interface
# ---------------------------------------------------------------------------

class BoardBuddyApp:
    """Draws the Streamlit GUI and connects it to the data service."""

    def __init__(self) -> None:
        self.data: Optional[TransitDataService] = None

    # ----- Page sections ---------------------------------------------------

    def render_header(self) -> None:
        """Title and short description at the top of the page."""
        st.title(f"{APP_ICON} {APP_TITLE}")
        st.caption(
            "Find buses from your stop and see how much space is on board. "
            "Demo data: schedules and occupancy are simulated, not real-time."
        )

    def render_search_form(self) -> Optional[SearchQuery]:
        """
        Show the search controls in the sidebar.
        Returns a SearchQuery when the user presses Search, otherwise None.
        """
        st.sidebar.header("Search")

        # Stop (required)
        stop: Stop = st.sidebar.selectbox(
            "Bus stop", options=self.data.get_stops(), format_func=str
        )

        # Route (optional) - list depends on the chosen stop
        route_choice = st.sidebar.selectbox(
            "Route number (optional)",
            options=[ANY_ROUTE] + self.data.get_routes(stop),
        )
        route = None if route_choice == ANY_ROUTE else route_choice

        # Destination (required) - stops later on the route(s)
        destinations = self.data.get_destinations(stop, route)
        if not destinations:
            st.sidebar.warning(
                "No onward stops from here on this route - it may be the last stop."
            )
            return None
        destination: Stop = st.sidebar.selectbox(
            "Destination", options=destinations, format_func=str
        )

        # Date (optional) - only shown if the user ticks the box
        travel_date = None
        service_dates = self.data.get_service_dates()
        if service_dates and st.sidebar.checkbox("Choose a specific date"):
            travel_date = st.sidebar.date_input(
                "Travel date",
                value=service_dates[0],
                min_value=service_dates[0],
                max_value=service_dates[-1],
            )

        if st.sidebar.button("Search", type="primary", width="stretch"):
            return SearchQuery(stop=stop, destination=destination,
                               route=route, travel_date=travel_date)
        return None

    def render_summary(self, departures: list[Departure]) -> None:
        """Key figures above the results table."""
        nxt = next_departure(departures)
        cancelled = sum(dep.is_cancelled for dep in departures)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Buses found", len(departures))
        if nxt:
            col2.metric(f"Next bus · route {nxt.route}", format_time(nxt.estimated_time),
                        nxt.service_date.strftime("%a %d %b"), delta_color="off")
            col3.metric("Seats free on next bus", nxt.availability["available_seats"],
                        nxt.availability["crowding"], delta_color="off")
        else:
            col2.metric("Next bus", "—")
            col3.metric("Seats free on next bus", "—")
        col4.metric("Cancelled", cancelled)

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

        self.render_summary(departures)
        st.dataframe(
            departures_to_dataframe(departures),
            hide_index=True,
            width="stretch",
            column_config={
                # Whole numbers (blank for cancelled buses)
                **{name: st.column_config.NumberColumn(name, format="%d")
                   for name in ("Seats free", "Standing free",
                                "Wheelchair bays", "Shared bays")},
                "Occupancy": st.column_config.ProgressColumn(
                    "Occupancy", min_value=0, max_value=100, format="%.0f%%"
                ),
            },
        )

    # ----- Main entry point -----------------------------------------------

    def run(self) -> None:
        """Build the whole page."""
        st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
        self.render_header()

        # Load the data, with a clear message if the CSV files can't be found
        try:
            self.data = get_data_service()
        except FileNotFoundError as error:
            st.error(
                f"Couldn't find a data file: {error.filename}\n\n"
                f"Put the CSV files in this folder: {DATA_DIR}"
            )
            st.stop()

        query = self.render_search_form()

        # Remember the last search so results stay visible after other clicks
        if query is not None:
            st.session_state["last_query"] = query

        last_query = st.session_state.get("last_query")
        if last_query:
            self.render_results(last_query)
        else:
            st.info("👈 Choose a stop and destination in the sidebar, then press **Search**.")


# ---------------------------------------------------------------------------
# Run the app
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    BoardBuddyApp().run()
