BOARD BUDDY - SYNTHETIC DEMO DATA

All schedules, capacity, occupancy, vehicle identifiers, and service status are INVENTED for app testing. Route/landmark pairings are approximate interpretations of the user-provided TFI schematic, NOT validated individual stops, stop IDs, service patterns, or current timetables. Do not present these as real-time information.

Files:
stops.csv: illustrative landmark stops
routes.csv: approximate route-stop associations (sequence illustrative, not geographical path)
bus_trips.csv: six hypothetical vehicles per route and sample arrival times on 2026-10-26
bus_capacity.csv: simulated seats/standing and shared accessible bays
occupancy.csv: simulated occupied seats, standing, shared bay status

Join bus_trips.stop_id to stops.stop_id, bus_trips.bus_id to bus_capacity.bus_id and occupancy.bus_id. Each bus_id is a simulated vehicle.

Available seats = total_seats - occupied_seats. Available standing = standing_capacity - standing_passengers. Shared accessible bay free only when occupied_shared_bays=0. Real bus capacity and access rules vary; no live data is supplied.

Suggested next step: use verified GTFS static data for actual stop IDs, route-stop relationships and scheduled trips, then GTFS-RT for arrival/delay updates where accessible. Live seat occupancy and accessible bay availability require a separate verified data source or explicit simulation.
