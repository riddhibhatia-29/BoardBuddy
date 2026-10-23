import csv
from pathlib import Path
DATA = Path(__file__).parent
def load(name):
    with (DATA / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

stops = {s["stop_id"]: s["stop_name"] for s in load("stops.csv")}
capacities = {b["bus_id"]: b for b in load("bus_capacity.csv")}
occupancies = {b["bus_id"]: b for b in load("occupancy.csv")}
for trip in load("bus_trips.csv")[:10]:
    bus = capacities[trip["bus_id"]]
    occ = occupancies[trip["bus_id"]]
    free_seats = int(bus["total_seats"]) - int(occ["occupied_seats"])
    print(trip["route_id"], stops[trip["stop_id"]], trip["estimated_time"] or "CANCELLED", "free seats:", free_seats)
