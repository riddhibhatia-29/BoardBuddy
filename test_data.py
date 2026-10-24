
from bus_data import get_stops, get_routes, get_buses
from occupancy import get_availability
from alternative_routes import get_alternatives


print("\n===== WELCOME TO BOARDBUDDY =====")

# STEP 1: Show all available bus stops
stops = get_stops()

print("\nAvailable stops:")

for stop in stops:
    print(stop["stop_id"], "-", stop["stop_name"])

# STEP 2: User chooses a stop
stop_id = input("\nEnter your stop ID: ").strip().upper()

valid_stops = {stop["stop_id"] for stop in stops}

if stop_id not in valid_stops:
    print("Invalid stop ID.")

else:
    # STEP 3: User chooses a bus route
    routes = get_routes(stop_id)

    print("\nAvailable routes:", ", ".join(routes))

    route_id = input("Choose your route: ").strip().upper()

    if route_id not in routes:
        print("Invalid route.")

    else:
        # Our CSV dataset contains simulated trips
        service_date = input(
            "Enter service date [2026-10-26]: "
        ).strip() or "2026-10-26"

        # STEP 4: Get matching buses
        buses = get_buses(
            stop_id,
            route_id,
            service_date
        )

        buses = [
            bus for bus in buses
            if bus["service_status"].lower() != "cancelled"
        ]

        if not buses:
            print("\nNo available buses found.")

        else:
            print("\n===== AVAILABLE BUSES =====")

            for index, bus in enumerate(buses, start=1):
                availability = get_availability(bus)

                print(f"\n{index}. Bus {bus['route_id']}")
                print("Bus ID:", bus["bus_id"])
                print("Arrival:", bus["estimated_time"])
                print("Status:", bus["service_status"])
                print("Free seats:", availability["available_seats"])
                print("Occupancy:", availability["occupancy_percentage"], "%")
                print("Crowding:", availability["colour"])

            # STEP 5: Select one of the buses
            choice = input("\nChoose a bus number from the list: ")

            if not choice.isdigit() or not (1 <= int(choice) <= len(buses)):
                print("Invalid selection.")

            else:
                selected_bus = buses[int(choice) - 1]
                availability = get_availability(selected_bus)

                print("\n===== YOUR SELECTED BUS =====")
                print("Route:", selected_bus["route_id"])
                print("Arrival:", selected_bus["estimated_time"])
                print("Available seats:", availability["available_seats"])
                print("Crowding:", availability["colour"])

                # STEP 6: Accessibility preference
                needs_seat = input(
                    "\nDo you need a seat? (yes/no): "
                ).strip().lower() == "yes"

                # STEP 7: Ask whether alternatives are needed
                show_alternatives = (
                    availability["occupancy_percentage"] >= 60
                    or (needs_seat and availability["available_seats"] == 0)
                )

                if show_alternatives:
                    print("\nThis bus may not be your best option.")
                else:
                    print("\nThis bus has relatively low crowding.")

                answer = input(
                    "Would you like alternative buses? (yes/no): "
                ).strip().lower()

                if answer == "yes":
                    print("\nOptional: enter your destination stop ID.")
                    print("Leave blank to see possible alternatives.")

                    destination_id = input(
                        "Destination stop ID: "
                    ).strip().upper()

                    if destination_id and destination_id not in valid_stops:
                        print("Invalid destination stop.")
                    else:
                        alternatives = get_alternatives(
                            stop_id=stop_id,
                            route_id=route_id,
                            bus_id=selected_bus["bus_id"],
                            service_date=service_date,
                            destination_id=destination_id or None,
                            needs_seat=needs_seat
                        )

                        print("\n===== ALTERNATIVE BUSES =====")

                        if not alternatives:
                            print("No matching alternatives found.")

                        for alternative in alternatives[:5]:
                            print("\n----------------------")
                            print("Route:", alternative["route_id"])
                            print("Stop:", alternative["stop_name"])
                            print("Arrival:", alternative["arrival"])
                            print("Available seats:", alternative["available_seats"])
                            print("Occupancy:", alternative["occupancy"], "%")
                            print("Crowding:", alternative["colour"])
                            print("Suggestion:", alternative["recommendation"])

                        if not destination_id:
                            print(
                                "\nNote: Check that an alternative "
                                "actually serves your destination."
                            )

                        print(
                            "\nAll results are simulated. "
                            "Walking distances and bus directions "
                            "have not been verified."
                        )





