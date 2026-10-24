#finds buses that serve a selected stop - displays their time of arrival, delays/cancellations

import csv
from pathlib import Path #pathlib gives Python instructions as to where your file is stored.

DATA_DIR = Path(__file__).parent / "data" #Path converts the location to a path object and stores it in data folder. 


def read_csv(filename):
    with open(DATA_DIR / filename, newline="",
              encoding="utf-8-sig") as file: #utf-8-sig translates characters, symbols into binary numbers
        return list(csv.DictReader(file)) #converts each row into a dictionary and combines all dictionaries into a list 


def get_stops(): 
    return read_csv("stops.csv")


def get_routes(stop_id):
    routes = read_csv("routes.csv")

    return sorted(set(
        row["route_id"]
        for row in routes
        if row["stop_id"] == stop_id
    ))

#for example if you call get_routes("5002"), extracts the route number from the matching row. 
#set is just to remove the duplicated values. 


def get_buses(stop_id, route_id=None, service_date=None): #stop_id - stop user selected, route_id and service_date are optional. 
    trips = read_csv("bus_trips.csv")
    capacities = read_csv("bus_capacity.csv")
    occupancies = read_csv("occupancy.csv")

    capacity_lookup = {  #creating a dictionary where bus_id is the key, i.e. {"BB01":{"bus_id":"BB01","total_seats":"35","standing_capacity":"25"}}
        row["bus_id"]: row
        for row in capacities
    }

    occupancy_lookup = {
        row["bus_id"]: row
        for row in occupancies
    }

    results = [] #this is where we will store the buses that match the user's selection

    for trip in trips:
        if trip["stop_id"] != stop_id: #if the bus trip isn't at the stop user selected, skip it. 
            continue

        if route_id and trip["route_id"] != route_id: #if user has selected a route, then skips the trips belonging to other routes. 
            continue

        if service_date and trip["service_date"] != service_date: #applies a date filter if date provided. 
            continue

        bus_id = trip["bus_id"] #get the bus_id from the trip 

        if bus_id not in capacity_lookup: #just so that there is no error. 
            continue

        if bus_id not in occupancy_lookup:
            continue

        bus = {                            #takes key-value pair from each dictionary and puts them into one dictionary. ** operator unpacks dictionary. 
            **trip,
            **capacity_lookup[bus_id],
            **occupancy_lookup[bus_id]
        }

        results.append(bus)
 
    return sorted(   #sorts the matching buses by date and time of arrival. 
        results,
        key=lambda bus: ( #lambda is small function definition - for each bus, use its date and estimated time arrival to decide where it belongs in the sorted list. 
            bus["service_date"],
            bus["estimated_time"]
        )
    )

