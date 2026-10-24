
import webbrowser

from bus_data import get_stops, get_routes, get_buses
from occupancy import get_availability
from alternative_routes import get_alternatives

from safety import (
    setup_database,
    add_contact,
    get_contacts,
    delete_contact,
    create_safety_message
)


# ---------------- BUS JOURNEY ----------------

def bus_journey():
    stops = get_stops()
    valid_stops = {stop["stop_id"] for stop in stops}

    print("\n===== PLAN YOUR BUS JOURNEY =====")

    for stop in stops:
        print(stop["stop_id"], "-", stop["stop_name"])

    stop_id = input("\nEnter stop ID: ").strip().upper()

    if stop_id not in valid_stops:
        print("Invalid stop ID.")
        return

    routes = get_routes(stop_id)

    if not routes:
        print("No routes found for this stop.")
        return

    print("\nAvailable routes:", ", ".join(routes))

    route_id = input("Choose route: ").strip().upper()

    if route_id not in routes:
        print("Invalid route.")
        return

    service_date = input(
        "Service date [2026-10-26]: "
    ).strip() or "2026-10-26"

    buses = get_buses(stop_id, route_id, service_date)

    buses = [
        bus for bus in buses
        if bus["service_status"].lower() != "cancelled"
    ]

    if not buses:
        print("No buses found.")
        return

    print("\n===== AVAILABLE BUSES =====")

    for i, bus in enumerate(buses, 1):
        info = get_availability(bus)

        print(f"\n{i}. Route {bus['route_id']}")
        print("Bus ID:", bus["bus_id"])
        print("Arrival:", bus["estimated_time"])
        print("Available seats:", info["available_seats"])
        print("Available standing:", info["available_standing"])
        print("Wheelchair bays:", info["available_wheelchair_bays"])
        print("Shared bays:", info["available_shared_bays"])
        print("Occupancy:", info["occupancy_percentage"], "%")
        print("Crowding:", info["colour"])

    choice = input("\nChoose bus number: ").strip()

    if not choice.isdigit() or not 1 <= int(choice) <= len(buses):
        print("Invalid selection.")
        return

    selected = buses[int(choice) - 1]
    info = get_availability(selected)

    print("\n===== SELECTED BUS =====")
    print("Route:", selected["route_id"])
    print("Arrival:", selected["estimated_time"])
    print("Free seats:", info["available_seats"])
    print("Occupancy:", info["occupancy_percentage"], "%")
    print("Crowding:", info["crowding"])

    needs_seat = input(
        "\nDo you need a seat? (yes/no): "
    ).strip().lower() == "yes"

    if info["occupancy_percentage"] >= 60 or (
        needs_seat and info["available_seats"] == 0
    ):
        print("\nThis bus may not be ideal for your needs.")
        print("BoardBuddy can suggest alternatives!")

    answer = input(
        "\nWould you like alternative buses? (yes/no): "
    ).strip().lower()

    if answer != "yes":
        return

    destination_id = input(
        "\nEnter destination stop ID (optional): "
    ).strip().upper()

    if destination_id and destination_id not in valid_stops:
        print("Invalid destination.")
        return

    alternatives = get_alternatives(
        stop_id=stop_id,
        route_id=route_id,
        bus_id=selected["bus_id"],
        service_date=service_date,
        destination_id=destination_id or None,
        needs_seat=needs_seat
    )

    if not alternatives:
        print("\nNo suitable alternatives found.")
        return

    # Prefer alternatives with lower occupancy
    better_alternatives = [
        bus for bus in alternatives
        if bus["occupancy"] < info["occupancy_percentage"]
    ]

    if better_alternatives:
        alternatives = better_alternatives
    else:
        print(
            "\nNo less-crowded alternatives found. "
            "Showing other possible buses."
        )

    displayed = alternatives[:5]

    print("\n===== ALTERNATIVE BUS SUGGESTIONS =====")

    for i, alternative in enumerate(displayed, 1):
        print(f"\n{i}. Route {alternative['route_id']}")
        print("Stop:", alternative["stop_name"])
        print("Arrival:", alternative["arrival"])
        print("Free seats:", alternative["available_seats"])
        print("Occupancy:", alternative["occupancy"], "%")
        print("Crowding:", alternative["colour"])
        print("Suggestion:", alternative["recommendation"])

        if alternative["walking_link"]:
            print("Google Maps walking directions available.")

    choice = input(
        "\nChoose an alternative number for walking "
        "directions (or press Enter to skip): "
    ).strip()

    if choice.isdigit() and 1 <= int(choice) <= len(displayed):
        alternative = displayed[int(choice) - 1]
        link = alternative["walking_link"]

        if link:
            print("\nOpening Google Maps...")
            print(link)
            webbrowser.open(link)
        else:
            print("This bus uses your original stop.")

    if not destination_id:
        print("\nCheck that the alternative reaches your destination.")

    print(
        "\nNote: Bus data is simulated. "
        "Walking distance, route direction and arrival "
        "feasibility have not been verified."
    )


# ---------------- SAFETY FEATURES ----------------

def safety_menu(user):

    while True:
        print("\n===== SAFETY FEATURES =====")
        print("1. Add trusted contact")
        print("2. View trusted contacts")
        print("3. Delete trusted contact")
        print("4. Create safety alert")
        print("5. Back to main menu")

        choice = input("\nChoose option: ").strip()

        if choice == "1":
            name = input("Contact name: ")
            phone = input("Phone number: ")

            try:
                add_contact(user, name, phone)
                print("\nTrusted contact saved!")
            except ValueError as error:
                print(error)

        elif choice == "2":
            contacts = get_contacts(user)

            if not contacts:
                print("\nNo trusted contacts found.")
            else:
                print("\n===== YOUR TRUSTED CONTACTS =====")

                for i, contact in enumerate(contacts, 1):
                    print(
                        f"{i}. {contact['name']} - "
                        f"{contact['phone']}"
                    )

        elif choice == "3":
            name = input("Enter contact name to delete: ").strip()

            deleted = delete_contact(name, user)

            if deleted:
                print("Contact deleted successfully.")
            else:
                print("Contact not found.")

        elif choice == "4":
            print("\n===== CREATE SAFETY ALERT =====")
            print("Enter coordinates to share.")
            print("This demo does not detect your location.")

            try:
                latitude = float(input("Latitude: "))
                longitude = float(input("Longitude: "))

                if not (-90 <= latitude <= 90):
                    print("Invalid latitude.")
                    continue

                if not (-180 <= longitude <= 180):
                    print("Invalid longitude.")
                    continue

            except ValueError:
                print("Please enter valid coordinates.")
                continue

            message = create_safety_message(
                user,
                latitude,
                longitude
            )

            print("\n===== YOUR SAFETY MESSAGE =====")
            print(message)

            print("\nTrusted contacts:")

            contacts = get_contacts(user)

            if not contacts:
                print("No trusted contacts saved.")
            else:
                for contact in contacts:
                    print(
                        contact["name"],
                        "-",
                        contact["phone"]
                    )

            print(
                "\nCopy the message and send it to a "
                "trusted contact using your messaging app."
            )
            print("BoardBuddy has not sent it automatically.")

        elif choice == "5":
            return

        else:
            print("Invalid option. Please try again.")


# ---------------- MAIN MENU ----------------

def main():

    setup_database()

    print("\n================================")
    print("       WELCOME TO BOARDBUDDY")
    print("================================")

    # Demo username only, not secure login
    user = input("\nEnter demo username: ").strip()

    if not user:
        print("Username cannot be empty.")
        return

    while True:

        print("\n========== MAIN MENU ==========")
        print("1. Plan bus journey")
        print("2. Safety features")
        print("3. Exit")

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            bus_journey()

        elif choice == "2":
            safety_menu(user)

        elif choice == "3":
            print("\nThank you for using BoardBuddy!")
            break

        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()

