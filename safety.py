
import csv
from pathlib import Path
from urllib.parse import quote

DATABASE = Path(__file__).parent / "contacts.csv"
FIELDS = ["user", "name", "phone"]


def connect():
    if not DATABASE.exists():
        with open(DATABASE, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(FIELDS)

    return DATABASE


def setup_database():
    # CSV doesn't need a SQL CREATE TABLE command
    connect()


def add_contact(user, name, phone):
    name = name.strip()
    phone = phone.strip()

    if not user.strip() or not name or not phone:
        raise ValueError("User, name and phone are required.")

    connect()

    with open(DATABASE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([user, name, phone])


def get_contacts(user):
    connect()
    contacts = []

    with open(DATABASE, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row["user"] == user:
                contacts.append(row)

    return contacts


def delete_contact(contact_name, user):
    connect()

    # Read ALL contacts so other users' data isn't deleted
    with open(DATABASE, "r", newline="", encoding="utf-8") as file:
        all_contacts = list(csv.DictReader(file))

    remaining = [
        contact for contact in all_contacts
        if not (
            contact["user"] == user
            and contact["name"] == contact_name
        )
    ]

    with open(DATABASE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(remaining)

    return len(all_contacts) - len(remaining)


def create_safety_message(name, latitude, longitude):
    location_link = (
        f"https://www.google.com/maps?q={latitude},{longitude}"
    )

    return (
        f"SAFETY ALERT from {name}: I may need assistance. "
        f"Please check on me.\n"
        f"My current location: {location_link}"
    )


