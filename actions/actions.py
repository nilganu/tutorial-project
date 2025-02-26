from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import requests
from rasa_sdk.events import Restarted

def fetch_booking_data(booking_id: str, module: str):
    """Fetch booking data from the Moonstride API based on booking ID and module."""
    moonstride_url = "https://services-uk.moonstride.com"
    baseurl_crm = "/api/crm"
    endpoint = f"{moonstride_url}{baseurl_crm}/v2/bookings/{booking_id}?{module}"

    headers = {
        'Content-Type': 'application/json',
        'token': 'f4e4b34ad40153a09139dbf0ae30d9f82c656fa0#4b683bb6-fd95-46f2-afd2-d058fceb22de'
    }

    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        response_data = response.json()
        return flatten_booking_data(response_data)
    else:
        return {"error": f"API Error {response.status_code}: {response.text}"}

def flatten_booking_data(response_data):
    """Flatten booking data and passenger details from the response."""
    flattened_response = {
        "BookingId": response_data.get("BookingId", "N/A"),
        "ReferenceNumber": response_data.get("ReferenceNumber", "N/A"),
        "BookingAmount": response_data.get("BookingAmount", "N/A"),
        "Title": response_data.get("Title", "N/A"),
        "BookingCurrency": response_data.get("BookingCurrency", {}).get("Name", "N/A"),
        "BookingDateTime": response_data.get("BookingDateTime", "N/A"),
        "DepartureDate": response_data.get("DepartureDate", "N/A"),
        "TravelStartDate": response_data.get("TravelStartDate", "N/A"),
        "TravelEndDate": response_data.get("TravelEndDate", "N/A"),
        "TotalNumberOfPassengers": sum(int(n) for n in response_data.get("BookingPassengers", {}).get("NumberOfPassengers", {}).values()),
        "Passengers": [
            {
                "FirstName": p.get('FirstName', 'N/A'),
                "LastName": p.get('LastName', 'N/A'),
                "Age": p.get('Age', '0'),  # Defaulting age to '0' if not available
                "PassportNumber": p.get('PassportNumber', 'Not Available')
            }
            for p in response_data.get("Passengers", [])
        ],
        "Customer": {
            "CustomerReferenceNumber": response_data.get("Customer", {}).get("ReferenceNumber", "N/A"),
            "CustomerType": response_data.get("Customer", {}).get("CustomerType", {}).get("Name", "N/A"),
            "CustomerName": response_data.get("Customer", {}).get("Name", "N/A"),
            "Email": response_data.get("Customer", {}).get("Email", "N/A"),
            "Gender": response_data.get("Customer", {}).get("Gender", {}).get("Name", "N/A"),
            "BirthDate": response_data.get("Customer", {}).get("BirthDate", "N/A")
        }
    }
    return flattened_response
class ActionRestart(Action):
    def name(self):
        return "action_restart"

    def run(self, dispatcher, tracker, domain):
        return [Restarted()]
    
class ActionCheckSufficientFunds(Action):
    def name(self) -> Text:
        return "action_check_sufficient_funds"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # hard-coded balance for tutorial purposes. in production this
        # would be retrieved from a database or an API
        balance = 1000
        transfer_amount = tracker.get_slot("amount")
        has_sufficient_funds = transfer_amount <= balance
        return [SlotSet("has_sufficient_funds", has_sufficient_funds)]

class ActionGetBookingDetail(Action):
    def name(self) -> Text:
        return "action_get_booking_detail"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        booking_id = tracker.get_slot('bookingId')
        module = tracker.get_slot('modulename')
        booking_details = fetch_booking_data(booking_id, module)

        if 'error' not in booking_details:
            general_details = (
                f"Booking ID: {booking_details['BookingId']}\n"
                f"Amount: {booking_details['BookingAmount']}\n"
                f"Departure: {booking_details['DepartureDate']}\n"
                f"Travel Start: {booking_details['TravelStartDate']}\n"
                f"Travel End: {booking_details['TravelEndDate']}"
            )
            dispatcher.utter_message(text=f"General Booking Details:\n{general_details}")

            if module == "passengers":
                passengers = booking_details.get('Passengers', [])
                if passengers:
                    passenger_details = "Passenger Details:\n"
                    for i, passenger in enumerate(passengers, 1):
                        passenger_details += (
                            f"  Passenger {i}: {passenger['FirstName']} {passenger['LastName']}\n"
                            f"Age: {passenger['Age']}\n"
                            f"Passport: {passenger['PassportNumber']}\n"
                    )
                    dispatcher.utter_message(text=passenger_details)
                else:
                    dispatcher.utter_message(text="No passenger details available.")
            elif module == "customer":
                customer = booking_details.get('Customer', {})
                customer_details = (
                    f"Customer Ref No: {customer['CustomerReferenceNumber']}\n"
                    f"Customer Type: {customer['CustomerType']}\n"
                    f"Name: {customer['CustomerName']}\n"
                    f"Email: {customer['Email']}\n"
                    f"Gender: {customer['Gender']}\n"
                    f"Birth Date: {customer['BirthDate']}"
                )
                dispatcher.utter_message(text=f"Customer Details:\n{customer_details}")

            return [SlotSet("overall_booking_details", general_details)]
        else:
            dispatcher.utter_message(text=booking_details['error'])
            return [SlotSet("booking_details_error", booking_details['error'])]

class ActionPostEnquiry(Action):
    def name(self) -> Text:
        return "action_create_new_enquiry"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        # Extract slots
        title = tracker.get_slot('title')
        travel_date = tracker.get_slot('travelDate')
        sell_channel = tracker.get_slot('sellChannel')

        # Prepare the data for the POST request
        data = {
            "Title": title,
            "TravelDate": travel_date,
            "SellChannel": {"Code": sell_channel}
        }
        
        # URL for the enquiry API endpoint
        url = 'https://services-uk.moonstride.com/api/crm/v1/enquiries'
        
        headers = {
            'Content-Type': 'application/json',
            'token': 'f4e4b34ad40153a09139dbf0ae30d9f82c656fa0#4b683bb6-fd95-46f2-afd2-d058fceb22de'         
        }

        # Send the POST request
        response = requests.post(url, json=data, headers=headers)
        print(response)
        response_data = response.json()

        # Debugging output
        #dispatcher.utter_message(text=f"API Response: {response_data}")
        
        # Check response status and provide feedback to user
        if response.status_code == 201:
            enquiry_message = f"Enquiry created successfully. Reference Number: {response_data['ReferenceNumber']}"
            dispatcher.utter_message(text=enquiry_message)
            return [SlotSet("reference_number", response_data['ReferenceNumber'])]
        else:
            error_message = f"Failed to create enquiry. Error: {response_data.get('Message', 'Unknown error')}"
            dispatcher.utter_message(text=error_message)
            return [SlotSet("enquiry_details_error", True)]

