
from bus_data import get_stops, get_buses, get_routes #imports functions from existing files
from occupancy import get_availability


def get_alternatives( 
    stop_id,
    route_id,
    bus_id,
    service_date,
    destination_id=None,
    needs_seat=False
):
    # Get all stops and find the selected stop
    stops = get_stops()

    selected_stop = next(
        (stop for stop in stops 
         if stop["stop_id"] == stop_id), 
        None
    )

    if selected_stop is None:
        return []

    # Find other stops in the same named area
    same_area_stops = [
        stop for stop in stops #loops through the stops list of dictionaries 
        if stop["area"] == selected_stop["area"] #checks whether the current stop belongs to same area as selected loop 
        and stop["stop_id"] != stop_id #if the user has already selected S001 bus, the alternative route shouldn't suggest that again
    ]

    candidates = [(stop_id, "Same stop")] #its a list containing all the bus stops where we want to search for alternative buses. 


    for stop in same_area_stops:
        candidates.append(
            (stop["stop_id"], "Another stop in the same area")
        )

    alternatives = []

    for candidate_stop_id, location_type in candidates: #each element in candidates is a tuple containing two values

        # Find all buses serving this stop
        buses = get_buses( 
            candidate_stop_id,
            service_date=service_date
        )

        for bus in buses: #looping through every bus returned by get_buses()

            # Don't recommend the original bus
            if bus["bus_id"] == bus_id:
                continue

            # Don't recommend cancelled buses
            if bus["service_status"].lower() == "cancelled": #if bus is cancelled skip that bus
                continue

            # If a destination is given, ensure this route
            # serves that destination in our sample data
            if destination_id is not None: # None means no destination provided 
                destination_routes = get_routes(destination_id)

                if bus["route_id"] not in destination_routes:
                    continue

            availability = get_availability(bus)

            # If a seat is required, exclude buses
            # without available seats
            if needs_seat and availability["available_seats"] == 0:
                continue

            # Determine recommendation type
            if candidate_stop_id != stop_id:
                recommendation = "Consider another stop in the same area"

            elif bus["route_id"] != route_id:
                recommendation = "Take another bus route"

            else:
                recommendation = "Take another bus on the same route"

            stop_name = next(  #finding the nect stop name using next()
                stop["stop_name"]
                for stop in stops
                if stop["stop_id"] == candidate_stop_id
            )

            alternatives.append({
                "bus_id": bus["bus_id"],
                "route_id": bus["route_id"],
                "stop_id": candidate_stop_id,
                "stop_name": stop_name,
                "arrival": bus["estimated_time"],
                "available_seats": availability["available_seats"],
                "occupancy": availability["occupancy_percentage"],
                "colour": availability["colour"],
                "recommendation": recommendation,
                "location_type": location_type
            })

    # Recommend less crowded buses first
    alternatives.sort(
        key=lambda bus: (
            bus["occupancy"],
            bus["arrival"]
        )
    )

    return alternatives
