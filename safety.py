import csv
import os

DATABASE = "contacts.csv"


# Connect to the CSV file / create it if it does not exist
def connect():
    if not os.path.exists(DATABASE):
        with open(DATABASE, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["user", "name", "phone"])

    return DATABASE



# Create the trusted contacts table
def setup_database():
    with connect() as db:
        #unique number to each contact INTEGER PRIMARY KEY AUTOINCREMENT
        #NOT NUll cannt be left empty
        db.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                name TEXT NOT NULL, 
                phone TEXT NOT NULL
            )
        """)


# Save a trusted contact
def add_contact(user, name, phone):
    name = name.strip() #removes unnessary spaces around a word
    phone = phone.strip()#removes unnecessary spaces around the phone number

    if not name or not phone:
        raise ValueError("Please enter both a name and phone number.") #prevents an empty contact from being saves it raises an error id it is saved

 connect() #makes sure the CSV file exists
          with open(DATABASE, "a", newline="") as file: #opens in append mode so the existing contacts are not erased
        writer = csv.writer(file)# to write the rows
        writer.writerow([user, name, phone]) #adds the new contect as one row



# Retrieve the user's trusted contacts
def get_contacts(user): 
    connect()  # Make sure the CSV file exists

    contacts = []#to store the matching contects

    with open(DATABASE, "r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:#one row at a time
            if row["user"] == user: #check whether the contect belongs to the requested user
                contacts.append(row)

    return contacts#list of matching contacts back the code 




# Delete a trusted contact
def delete_contact(contact_name, user):
    contacts = get_contacts(user) #retrives the user's contacts

    with open(DATABASE, "w", newline="") as file: # write mode w clears the existing file so we can rewrite the contects we need to keep
        #newline prevents the unwanted blank lines 
        #dictionary data into the CSV file
        writer = csv.DictWriter( #opens the CSV foiles in write mode so the contents will be rewritten
            file,
            fieldnames=["user", "name", "phone"] #column headings
        )
        writer.writeheader() #names that do  match the anme being deletednot

#check each contect in the list if the name does not match the name we want to delete it wirtes that contact back into the CSV file
        for contact in contacts:
            if contact["name"] != contact_name:
                writer.writerow(contact)





# Create a safety-alert message
def create_safety_message(name, latitude, longitude): #getting the geographical coordinates
    location_link = (
        f"https://www.google.com/maps?q={latitude},{longitude}" #stores the map link
    )

    return (
        f"SAFETY ALERT: I may need assistance. "
        f"Please check on me.\n" #f allows the location link to be added to the message 
        f"My current location: {location_link}"
    )