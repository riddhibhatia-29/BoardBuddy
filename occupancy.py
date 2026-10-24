#calculates available seats, standing spaces, accessibility availability. 

def get_availability(bus): #bus is a dictionary that contains information for a bus. 
    seats = int(bus["total_seats"])
    occupied = int(bus["occupied_seats"])

    standing_capacity = int(bus["standing_capacity"]) #max number of standing passengers bus can accomodate 
    standing = int(bus["standing_passengers"]) #no. of passengers currently standing. 

    wheelchair_bays = int(bus["wheelchair_bays"])
    occupied_wheelchair = int(
        bus["occupied_wheelchair_bays"]
    )

    shared_bays = int(bus["shared_wheelchair_buggy_bays"])
    occupied_shared = int(bus["occupied_shared_bays"])

    available_seats = max(0, seats - occupied) #max is just to make sure we never get a negative answer. 
    available_standing = max(0, standing_capacity - standing)

    available_wheelchair = max(
        0, wheelchair_bays - occupied_wheelchair
    )

    available_shared = max(
        0, shared_bays - occupied_shared
    )

    total_capacity = seats + standing_capacity
    passengers = occupied + standing

    percentage = round(
        passengers / total_capacity * 100, 1 #rounds to one decimal place.
    ) if total_capacity > 0 else 0 #shortened if-else, means that if total_capacity>0, then calculate %, otherwise just return 0. 

    if percentage >= 85:
        colour = "RED"
        crowding = "Very crowded"
    elif percentage >= 60:
        colour = "YELLOW"
        crowding = "Moderately crowded"
    else:
        colour = "GREEN"
        crowding = "Plenty of space"

    return {
        "available_seats": available_seats,
        "available_standing": available_standing,
        "available_wheelchair_bays": available_wheelchair,
        "available_shared_bays": available_shared,
        "occupancy_percentage": percentage,
        "colour": colour,
        "crowding": crowding
    }
