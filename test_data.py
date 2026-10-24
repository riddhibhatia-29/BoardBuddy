
from bus_data import get_stops, get_routes, get_buses
from occupancy import get_availability

print("WELCOME TO BOARDBUDDY")

# Display available stops
stops = get_stops()

print("\nAvailable bus stops:")

for stop in stops:
    print(stop["stop_id"], "-", stop["stop_name"])

# User chooses a stop
stop_id = input("\nEnter stop ID: ").strip().upper()

valid_stops = {stop["stop_id"] for stop in stops}

if stop_id not in valid_stops:
    print("Invalid stop ID.")

else:
    # Display available routes
    routes = get_routes(stop_id)

    print("\nAvailable routes:", ", ".join(routes))

    route = input("Choose bus route: ").strip().upper()

    if route not in routes:
        print("Invalid route for this stop.")

    else:
        buses = get_buses(stop_id, route)

        if not buses:
            print("No scheduled buses found.")

        for bus in buses:
            print("\n----------------------")
            print("Bus:", bus["route_id"])
            print("Bus ID:", bus["bus_id"])
            print("Date:", bus["service_date"])
            print("Arrival:", bus["estimated_time"])
            print("Status:", bus["service_status"])

            if bus["service_status"].lower() == "cancelled":
                print("This service is cancelled.")
                continue

            availability = get_availability(bus)

            print("Seats:", availability["available_seats"])
            print("Standing:", availability["available_standing"])

            print(
                "Wheelchair bays:",
                availability["available_wheelchair_bays"]
            )

            print(
                "Shared accessible bays:",
                availability["available_shared_bays"]
            )

            print(
                "Occupancy:",
                availability["occupancy_percentage"], "%"
            )

            print("Crowding:", availability["colour"])




