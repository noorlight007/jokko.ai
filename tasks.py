from celery_app import celery
from typing import Any, Dict, Optional, Tuple
import httpx
from whatsapp_http import send_whatsapp_message

import os, json
from dotenv import load_dotenv
load_dotenv()

WHATSAPP_PHONE_NUMBER_ID=os.getenv("PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
WHATSAPP_PERMANENT_TOKEN = os.getenv("PARMANENT_ACCESS_TOKEN")
VERIFY_TOKEN = "6984125oO!?"


from location_manage import (get_countries, get_cities_by_country, get_airports_by_country, get_countries_with_airports)

from db_user import create_or_get_user
from utils_db import can_user_perform_action
from db_driver_routes import get_all_driver_routes_for_a_driver_chatbot
from db_contact_req import create_contact_request_chatbot
from db_parcel_events import create_parcel_event_chatbot
from db_pickup_events import create_pickup_event_chatbot
# from db_driver_routes import get_all_driver_routes

from message_ids import add_message_id
from utils import *

import redis
r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def state_key(sender): 
    return f"wa:state:{sender}"

def data_key(sender):
    return f"wa:data:{sender}"

def user_key(sender):
    return f"wa:user_role:{sender}"


def clear_user(sender) -> bool:
    return r.delete(user_key(sender)) == 1


def to_airport_data_key(sender):
    return f"wa:to_airport_data:{sender}"

def from_airport_data_key(sender):
    return f"wa:from_airport_data:{sender}"

def pb_gp_trip_date_key(sender):
    return f"wa:pb_gp_trip_date_:{sender}"

def gp_routes_key(sender):
    return f"wa:gp_routes:{sender}"

def delete_gp_route_key(sender):
    return f"wa:delete_gp_route:{sender}"

def error_count_key(sender):
    return f"wa:error_count:{sender}"

def get_state(sender):
    return r.get(state_key(sender))

def set_state(sender, state):
    r.setex(state_key(sender), 60*60, state)  # 60 minutes TTL

def clear_state(sender) -> bool:
    return r.delete(state_key(sender)) == 1


def get_user_role(sender):
    """Get stored conversation data for a user"""
    role = r.get(user_key(sender))
    if role:
        return str(role)
    return None

def set_user_role(sender, role):
    """Store conversation data for a user"""
    r.setex(user_key(sender), 60*60, role)  # 60 minutes TTL
    

# ----------- Parcel request data management in Redis (can be used to store intermediate data during the conversation) -----------
def get_data(sender) -> dict:
    """Get stored conversation data for a user"""
    data = r.get(data_key(sender))
    if data:
        return json.loads(data)
    return {}

def set_data(sender, data: dict):
    """Store conversation data for a user"""
    r.setex(data_key(sender), 60*60, json.dumps(data))  # 60 minutes TTL

def update_data(sender, key: str, value: any):
    """Update a specific field in user's conversation data"""
    data = get_data(sender)
    data[key] = value
    set_data(sender, data)

def clear_data(sender) -> bool:
    """Clear all stored data for a user"""
    return r.delete(data_key(sender)) == 1

# ----------- to airport data management in Redis (can be used to store intermediate data during the conversation) -----------
def get_to_airport_data(sender) -> dict:
    """Get stored conversation data for a user"""
    data = r.get(to_airport_data_key(sender))
    if data:
        return json.loads(data)
    return {}

def set_to_airport_data(sender, data: dict):
    """Store conversation data for a user"""
    r.setex(to_airport_data_key(sender), 60*60, json.dumps(data))  # 60 minutes TTL

def update_to_airport_data(sender, key: str, value: any):
    """Update a specific field in user's conversation data"""
    data = get_to_airport_data(sender)
    data[key] = value
    set_to_airport_data(sender, data)

def clear_to_airport_data(sender) -> bool:
    """Clear all stored data for a user"""
    return r.delete(to_airport_data_key(sender)) == 1


# ----------- From airport data management in Redis (can be used to store intermediate data during the conversation) -----------
def get_from_airport_data(sender) -> dict:
    """Get stored conversation data for a user"""
    data = r.get(from_airport_data_key(sender))
    if data:
        return json.loads(data)
    return {}

def set_from_airport_data(sender, data: dict):
    """Store conversation data for a user"""
    r.setex(from_airport_data_key(sender), 60*60, json.dumps(data))  # 60 minutes TTL

def update_from_airport_data(sender, key: str, value: any):
    """Update a specific field in user's conversation data"""
    data = get_from_airport_data(sender)
    data[key] = value
    set_from_airport_data(sender, data)

def clear_from_airport_data(sender) -> bool:
    """Clear all stored data for a user"""
    return r.delete(from_airport_data_key(sender)) == 1


# ----------- Publish GP trip data management in Redis (can be used to store intermediate data during the conversation) -----------
def get_pb_gp_trip_data(sender) -> dict:
    """Get stored conversation data for a user"""
    data = r.get(pb_gp_trip_date_key(sender))
    if data:
        return json.loads(data)
    return {}

def set_pb_gp_trip_data(sender, data: dict):
    """Store conversation data for a user"""
    r.setex(pb_gp_trip_date_key(sender), 60*60, json.dumps(data))  # 60 minutes TTL

def update_pb_gp_trip_data(sender, key: str, value: any):
    """Update a specific field in user's conversation data"""
    data = get_pb_gp_trip_data(sender)
    data[key] = value
    set_pb_gp_trip_data(sender, data)

def clear_pb_gp_trip_data(sender) -> bool:
    """Clear all stored data for a user"""
    return r.delete(pb_gp_trip_date_key(sender)) == 1

# ----------- GP routes status data management in Redis 

def get_gp_routes(sender) -> dict:
    """Get stored GP routes data for a user"""
    data = r.get(gp_routes_key(sender))
    if data:
        return json.loads(data)
    return {}

def set_gp_routes(sender, data: dict):
    """Store GP routes data for a user"""
    r.setex(gp_routes_key(sender), 60*60, json.dumps(data))  # 60 minutes TTL

def update_gp_routes(sender, key: str, value: any):
    """Update a specific field in user's GP routes data"""
    data = get_gp_routes(sender)
    data[key] = value
    set_gp_routes(sender, data)

def clear_gp_routes(sender) -> bool:
    """Clear all stored GP routes data for a user"""
    return r.delete(gp_routes_key(sender)) == 1


# ----------- GP route delete data management in Redis
def get_delete_gp_route(sender) -> dict:
    """Get stored GP route delete data for a user"""
    data = r.get(delete_gp_route_key(sender))
    if data:
        return json.loads(data)
    return {}

def set_delete_gp_route(sender, data: dict):
    """Store GP route delete data for a user"""
    r.setex(delete_gp_route_key(sender), 60*60, json.dumps(data))  # 60 minutes TTL

def update_delete_gp_route(sender, key: str, value: any):
    """Update a specific field in user's GP route delete data"""
    data = get_delete_gp_route(sender)
    data[key] = value
    set_delete_gp_route(sender, data)

def clear_delete_gp_route(sender) -> bool:
    """Clear all stored GP route delete data for a user"""
    return r.delete(delete_gp_route_key(sender)) == 1



# ----------- Error counts -----------
def get_error_count_exceeds_3(sender) -> int:
    """Get error count for a user"""
    count = r.get(error_count_key(sender))
    if int(count) >= 3:
        return True
    return False

def increment_error_count(sender):
    """Increment error count for a user"""
    r.incr(error_count_key(sender))

def clear_error_count(sender):
    """Clear error count for a user"""
    r.delete(error_count_key(sender))


def clear_all(sender):
    """Clear both state and data for a user"""
    clear_state(sender)
    clear_data(sender)

# ---- END of Redis data management functions for conversation state and data ----



# ==================== HELPER FUNCTIONS ====================

def build_summary(sender: str) -> str:
    """Build a formatted summary of the user's shipment request"""
    data = get_data(sender)
    
    summary = "📝 Merci pour ces informations !\n\nVoici le récapitulatif de votre demande :\n"
    
    # Departure information
    if data.get('departure_country') and data.get('departure_city'):
        summary += f"📍 *Départ:*\n"
        summary += f"   Pays: {data['departure_country']}\n"
        summary += f"   Ville: {data['departure_city']}\n"
    
    # Destination information
    if data.get('destination_country') and data.get('destination_city'):
        summary += f"🎯 *Destination:*\n"
        summary += f"   Pays: {data['destination_country']}\n"
        summary += f"   Ville: {data['destination_city']}\n"
    
    # Send date
    if data.get('send_date'):
        summary += f"📅 *Date d'envoi:* {data['send_date']}\n"
    
    # Shipping type
    if data.get('shipping_type'):
        summary += f"📦 *Type d'envoi:* {data['shipping_type']}\n\nVeuillez confirmer la demande :"
    
    return summary

# This function is to show summary of GP's Publish trip redis data, it will be used to confirm the trip details before publishing it for matching with clients' requests
def build_pb_gp_trip_summary(sender: str) -> str:

    """
    pb_gp_trip_departure_country
    pb_gp_trip_departure_city
    pb_gp_trip_dest_country
    pb_gp_trip_dest_city
    pb_gp_trip_date_option_text
    pb_gp_trip_shipping_type_text
    """

    data = get_pb_gp_trip_data(sender)

    print("*****************")
    print(data)
    
    summary = "📝 Merci pour ces informations !\n\nVoici le récapitulatif de votre demande :\n"
    
    # Departure information
    if data.get('pb_gp_trip_departure_country') and data.get('pb_gp_trip_departure_city'):
        summary += f"📍 *Départ:*\n"
        summary += f"   Pays: {data['pb_gp_trip_departure_country']}\n"
        summary += f"   Ville: {data['pb_gp_trip_departure_city']}\n"
    
    # Destination information
    if data.get('pb_gp_trip_dest_country') and data.get('pb_gp_trip_dest_city'):
        summary += f"🎯 *Destination:*\n"
        summary += f"   Pays: {data['pb_gp_trip_dest_country']}\n"
        summary += f"   Ville: {data['pb_gp_trip_dest_city']}\n"
    
    # Send date
    if data.get('pb_gp_trip_date_option_text'):
        summary += f"📅 *Date du trajet:* {data['pb_gp_trip_date_option_text']}\n"
    
    # Shipping type
    if data.get('pb_gp_trip_shipping_type_text'):
        summary += f"{data['pb_gp_trip_shipping_type_text']}\n\nMerci de vérifier que tout est correct 😊\n\nVeuillez confirmer la demande :"
    
    return summary





# Build data summary of GP status flow
def build_pb_gp_status_summary(sender: str) -> str:
    """
    gp_status_route
    gp_status
    """
    data = get_gp_routes(sender)
    summary = "📝 Merci pour ces informations !\n\nVoici le récapitulatif de votre demande :\n"
    if data.get('gp_status_route'):
        summary += f"📍 *Trajet:*\n"
        summary += f"   {data['gp_status_route']}\n"
    if data.get('gp_status'):
        summary += f"📌 *Statut:*\n"
        summary += f"   {data['gp_status']}\n"
    
    summary += "\nMerci de vérifier que tout est correct 😊\n\nVeuillez confirmer la demande :"
    return summary


def build_to_airport_summary(sender: str) -> str:

    # departure_country
    # departure_airport
    # departure_city
    # departure_date_preference
    # num_travelers_preference
    # num_small_cases_preference
    # num_medium_cases_preference
    # num_big_cases_preference
    """Build a formatted summary of the user's to airport request"""
    data = get_to_airport_data(sender)
    
    summary = "📝 Merci pour ces informations !\n\nVoici le récapitulatif de votre demande :\n"
    
    # Departure information
    if data.get('departure_country') and data.get('departure_city'):
        summary += f"📍 *Départ:*\n"
        summary += f"   Pays: {data['departure_country']}\n"
        summary += f"   Aéroport: {data['departure_airport']}\n"
        summary += f"   Ville: {data['departure_city']}\n"
    
    # Send date
    if data.get('departure_date_preference'):
        summary += f"📅 *Date du trajet:* {data['departure_date_preference']}\n"
    
    # Number of passengers
    if data.get('num_travelers_preference'):
        summary += f"👥 *Nombre de passagers:* {data['num_travelers_preference']}\n"
    
    # Number of small luggage
    if data.get('num_small_cases_preference'):
        summary += f"🧳 *Nombre de petits bagages:* {data['num_small_cases_preference']}\n"
    
    # Number of medium luggage
    if data.get('num_medium_cases_preference'):
        summary += f"🧳 *Nombre de bagages moyens:* {data['num_medium_cases_preference']}\n"
    
    # Number of big luggage
    if data.get('num_big_cases_preference'):
        summary += f"🧳 *Nombre de gros bagages:* {data['num_big_cases_preference']}\n\nVeuillez confirmer la demande :" # Also finalize the summary with a confirmation request
    
    return summary


def build_from_airport_summary(sender: str) -> str:

    # departure_country
    # departure_airport
    # departure_city
    # departure_date_preference
    # num_travelers_preference
    # num_small_cases_preference
    # num_medium_cases_preference
    # num_big_cases_preference
    """Build a formatted summary of the user's to airport request"""
    data = get_from_airport_data(sender)
    
    summary = "📝 Merci pour ces informations !\n\nVoici le récapitulatif de votre demande :\n"
    
    # Departure information
    if data.get('departure_country') and data.get('departure_city'):
        summary += f"📍 *Arrivée:*\n"
        summary += f"   Pays: {data['departure_country']}\n"
        summary += f"   Aéroport: {data['departure_airport']}\n"
        summary += f"   Ville: {data['departure_city']}\n"
    
    # Send date
    if data.get('departure_date_preference'):
        summary += f"📅 *Date du trajet:* {data['departure_date_preference']}\n"
    
    # Number of passengers
    if data.get('num_travelers_preference'):
        summary += f"👥 *Nombre de passagers:* {data['num_travelers_preference']}\n"
    
    # Number of small luggage
    if data.get('num_small_cases_preference'):
        summary += f"🧳 *Nombre de petits bagages:* {data['num_small_cases_preference']}\n"
    
    # Number of medium luggage
    if data.get('num_medium_cases_preference'):
        summary += f"🧳 *Nombre de bagages moyens:* {data['num_medium_cases_preference']}\n"
    
    # Number of big luggage
    if data.get('num_big_cases_preference'):
        summary += f"🧳 *Nombre de gros bagages:* {data['num_big_cases_preference']}\n\nVeuillez confirmer la demande :" # Also finalize the summary with a confirmation request
    
    return summary



def send_error_message(sender: str, headers: dict, url: str):
    """Helper function to send error messages to the user"""
    text = f"❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "text",
        "text": {
            "body": text.strip()
        }
    }
    send_whatsapp_message(sender, payload, headers, url)

def client_send_welcome_msg(sender, headers: dict, url: str):
    """Helper function to send welcome message to the user"""
    text = f"👋 Bienvenue sur Jokko Ai !\n\nVotre assistant WhatsApp pour vous aider à trouver rapidement la bonne personne pour vos envois de colis ou vos trajets aéroportuaires, sans prise de tête.\n\nVeuillez Choisir le service de votre choix :"
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text.strip()},
            "action": {
                "button": "Afficher le menu",
                "sections": [
                    {
                        "title": "Seleccione desde aquí",
                        "rows": [
                            {
                            "id": "role_customer1",
                            "title": "Envoyer un colis"
                            },
                            {
                            "id": "role_customer2",
                            "title": "Aller à l’aéroport"
                            },
                            {
                            "id": "role_customer3",
                            "title": "Retour de l’aéroport"
                            },
                            {
                            "id": "role_customer4",
                            "title": "Autres services"
                            }

                        ],
                    }
                ]
            },
        },
    }
    send_whatsapp_message(sender, payload, headers, url)

def professional_send_welcome_msg(sender, headers: dict, url: str):
    """Helper function to send welcome message to the user"""
    text = f"👋 Bienvenue sur Jokko Ai !\n\nVotre assistant WhatsApp pour vous aider à trouver rapidement la bonne personne pour vos envois de colis ou vos trajets aéroportuaires, sans prise de tête.\n\nVeuillez sélectionner le service de votre choix :"
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text.strip()},
            "action": {
                "button": "Afficher le menu",
                "sections": [
                    {
                        "title": "Seleccione desde aquí",
                        "rows": [
                            {
                            "id": "role_pro_1",
                            "title": "Publier un trajet GP"
                            },
                            {
                            "id": "role_pro_2",
                            "title": "Mettre à jour statut GP"
                            },
                            {
                            "id": "role_pro_3",
                            "title": "Supprimer des trajets"
                            },

                            {
                            "id": "role_pro_4",
                            "title": "Envoyer un colis"
                            },

                            {
                            "id": "role_pro_5",
                            "title": "Aller à l’aéroport"
                            },

                            {
                            "id": "role_pro_6",
                            "title": "Retour de l’aéroport"
                            },

                            {
                            "id": "role_pro_7",
                            "title": "Autres services"
                            }

                        ],
                    }
                ]
            },
        },
    }
    send_whatsapp_message(sender, payload, headers, url)

def driver_send_welcome_msg(sender, headers: dict, url: str):
    """Helper function to send welcome message to the user"""
    text = f"👋 Bienvenue sur Jokko Ai !\n\nVotre assistant WhatsApp pour vous aider à trouver rapidement la bonne personne pour vos envois de colis ou vos trajets aéroportuaires, sans prise de tête.\n\nVeuillez sélectionner le service de votre choix :"
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text.strip()},
            "action": {
                "button": "Afficher le menu",
                "sections": [
                    {
                        "title": "Seleccione desde aquí",
                        "rows": [
                            {
                                "id": "role_driver_1",
                                "title": "Mes disponibilités"
                            },
                            {
                                "id": "role_driver_2",
                                "title": "Envoyer un colis"
                            },

                            {
                                "id": "role_driver_3",
                                "title": "Aller à l'aéroport"
                            },

                            {
                                "id": "role_driver_4",
                                "title": "Retour de l'aéroport"
                            },
                            {
                                "id": "role_driver_5",
                                "title": "Autres services"
                            }
                        ],
                    }
                ]
            },
        },
    }
    send_whatsapp_message(sender, payload, headers, url)


def send_service_selected_role_customer1_msg(sender, headers: dict, url: str):
    """Helper function to send message after service selection for role_customer1"""
    text = f"🙏 Super, merci pour votre choix !\n🌍 Dans quel pays se trouve le colis / document ?"

    countries, count = get_countries()
    print(f"Available countries for shipment: {countries}")
    rows = []
    for c in countries:
        rows.append({
            "id": f"list_country_{c['id']}",
            "title": c['name']
        })
    # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
    rows.append({"id": f"list_country_700", "title": "Menu précédent"})
    rows.append({"id": f"list_country_701", "title": "Menu principal"})

    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text.strip()},
            "action": {
                "button": "Choisir le pays",
                "sections": [
                    {
                        "title": "Pays",
                        "rows": rows
                    }
                ]
            },
        },
    }
    send_whatsapp_message(sender, payload, headers, url)


def send_city_selection_msg(sender, headers: dict, url: str, country_id: int):
    """Helper function to send city selection message after country selection"""
    cities = get_cities_by_country(country_id)
    rows = []
    for c in cities:
        rows.append({
            "id": f"list_city_{c['id']}",
            "title": c['name']
        })
    rows.append({"id": f"list_city_700", "title": "Menu précédent"})
    rows.append({"id": f"list_city_701", "title": "Menu principal"})
    
    text = f"📍 Dans quelle ville se trouve le colis / document ?"
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text.strip()},
            "action": {
                "button": "Choisir la ville",
                "sections": [
                    {
                        "title": "Pays",
                        "rows": rows
                    }
                ]
            },
        },
    }

    send_whatsapp_message(sender, payload, headers, url)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def process_webhook(self, payload: dict):
    """
    Do slow work here: DB writes, API calls, business logic
    """
    # print(payload)
    # your processing logic
    data = payload

    
    url = f"https://graph.facebook.com/v23.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_PERMANENT_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Profile name (if present)
                profile_name = None
                try:
                    profile_name = value["contacts"][0]["profile"]["name"]
                    print(f"Profile name = {profile_name}")
                except Exception:
                    pass

                messages = value.get("messages")
                if not messages:
                    continue  # could be a status/event update

                msg = messages[0]
                print(msg)
                msg_id = msg.get("id")

                new_msg_check = add_message_id(msg_id)
                if not new_msg_check:
                    print("🔁 Duplicate message. Skipping.")
                    return "okay", 200

                # Sender WhatsApp ID (phone number in international format without +)
                sender = msg.get("from")
                print(f"👤 Sender = {sender}")

                msg_type, list_msg_id, button_msg_id, text_body, media_id, latitude, longitude = extract_message_fields(msg)

                if media_id:
                    print(f"🖼️ media_id = {media_id}")
                if latitude is not None and longitude is not None:
                    print(f"📍 location = ({latitude}, {longitude})")

                print(f"💬 Message ({msg_type}) = {text_body}")
                # session['msg_context'][sender]['state']
                print(f"📊 Current session context: {get_state(sender) if get_state(sender) else 'None'}")

                # First checking the user role
                clear_user(sender)
                user_role = get_user_role(sender)
                
                if not user_role:
                    role_obj = create_or_get_user(sender, profile_name)  # This will create a new user with default role "client" if not exists, or get the existing user role
                    print(role_obj.user_type)
                    if not role_obj:
                        user_role = "client"
                        set_user_role(sender, user_role)
                    else:
                        # print(f"resolved user role = {user_role}")
                        set_user_role(sender, role_obj.user_type)
                    user_role = get_user_role(sender)
                
                print(f"user role = {user_role}")



                if user_role == "client":
                    if not get_state(sender):
                        # Update state for next step
                        set_state(sender, "service_selected")

                        # Build interactive reply
                        client_send_welcome_msg(sender, headers, url)

                        # # Send message to WhatsApp (sync httpx client for Flask route)
                        # send_whatsapp_message(sender, payload, headers, url)

                        return "ok", 200
                    
                    # New flow: user has selected a service from the menu
                    elif get_state(sender) == "service_selected":
                        ## Continue here
                        # ✅✅✅
                        if msg_type == "interactive_list_reply" and list_msg_id == "role_customer1":
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            # Store service type
                            update_data(sender, 'service_type', 'Envoyer un colis')

                            set_state(sender, "shipment_country_selected")

                            send_service_selected_role_customer1_msg(sender, headers, url)
                            
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            # send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_customer2":
                            # resetting error count on valid selection
                            clear_error_count(sender)
                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                            rows = []
                            countries = get_countries_with_airports()
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "to_airport_country_selected")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            update_to_airport_data(sender, 'context', "Ride to Airport")
                            return "ok", 200

                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_customer3":
                            # resetting error count on valid selection
                            clear_error_count(sender)
                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l'aéroport d'arrivée ?"

                            rows = []
                            countries = get_countries_with_airports()
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "from_airport_country_selected")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200



                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_customer4":
                            text = "🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\nVeuillez sélectionner le service de votre choix :"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Type de service ?",
                                        "sections": [
                                            {
                                                "title": "Date d'envoi",
                                                "rows": [
                                                    {
                                                        "id": "other_gp",
                                                        "title": "Inscription GP"
                                                    },
                                                    {
                                                        "id": "other_AIBD",
                                                        "title": "Inscription Transp. AIBD"
                                                    },
                                                    {
                                                        "id": "other_contact",
                                                        "title": "Contact service client"
                                                    },
                                                    {
                                                        "id": "other_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "other_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "client_others")

                            send_whatsapp_message(sender, payload, headers, url)
                            return "okay", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    ##########################################################################################
                    ################################### Client ###############################################
                    ########################### Parcel Request Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "shipment_country_selected":
                        # clear_data(sender)  # clearing any previously stored data to avoid conflicts and ensure clean state for new request
                        # clear_state(sender) # clearing state to avoid conflicts and ensure clean state for new request, we will set the correct state at the end of this block based on user selection
                        # return "ok", 200
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_data(sender, 'departure_country_id', country_id)
                                update_data(sender, 'departure_country', country)
                            
                            set_state(sender, "departure_city_selected")
                            
                            send_city_selection_msg(sender, headers, url, get_data(sender).get('departure_country_id'))

                            return "ok", 200
                        
                        else:

                            send_whatsapp_message(sender, payload, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif city_id == "700":
                                # Store service type
                                update_data(sender, 'service_type', 'Envoyer un colis')

                                set_state(sender, "shipment_country_selected")

                                send_service_selected_role_customer1_msg(sender, headers, url)
                                
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                # send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200


                            # Store departure city
                            city = text_body
                            if city:
                                update_data(sender, 'departure_city_id', city_id)
                                update_data(sender, 'departure_city', city)

                            countries, count = get_countries()
                            rows = []
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})
                            text = f"🌍 Dans quel pays allez-vous envoyer le colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "destination_country_selected")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "destination_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "700":
                                
                                set_state(sender, "departure_city_selected")
                            
                                send_city_selection_msg(sender, headers, url, get_data(sender).get('departure_country_id'))

                                return "ok", 200

                            # Store destination country
                            country = text_body
                            if country:
                                update_data(sender, 'destination_country_id', country_id)
                                update_data(sender, 'destination_country', country)

                            cities = get_cities_by_country(get_data(sender).get('destination_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})
                            
                            text = f"📍 Dans quelle ville allez-vous envoyer le colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la ville",
                                        "sections": [
                                            {
                                                "title": "Villes",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "destination_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "text",
                                "text": {
                                    "body": text.strip()
                                }
                            }
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in destination country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "destination_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.split("_")[-1]

                            # Store destination city
                            city = text_body
                            if city:
                                update_data(sender, 'destination_city_id', city_id)
                                update_data(sender, 'destination_city', city)

                            if list_msg_id == "list_city_701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif list_msg_id == "list_city_700":
                                
                                # Update state for next step

                                countries = get_countries()
                                rows = []
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})
                                text = f"🌍 Dans quel pays allez-vous envoyer le colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "destination_country_selected")

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            text = "📅 Quand souhaitez-vous envoyer votre colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la date",
                                        "sections": [
                                            {
                                                "title": "Date d'envoi",
                                                "rows": [
                                                    {
                                                        "id": "send_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "send_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "send_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "send_date_other",
                                                        "title": "Une date ultérieure"
                                                    },
                                                    {
                                                        "id": "send_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "send_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                },
                            }
                            set_state(sender, "send_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                                
                            print("⚠️ Unexpected message type or list selection in destination city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "send_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("send_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            send_date_option = list_msg_id.replace("send_date_", "")

                            if send_date_option == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif send_date_option == "700":
                                # Update state for next step

                                cities = get_cities_by_country(get_data(sender).get('destination_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})
                                
                                text = f"📍 Dans quelle ville allez-vous envoyer le colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la ville",
                                            "sections": [
                                                {
                                                    "title": "Villes",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }

                                set_state(sender, "destination_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            # Store send date
                            update_data(sender, 'send_date', text_body)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = f"📦 Quel est le type d'envoi ?"

                            # List of shipping types - you can replace with actual types from your database
                            shipping_types = [
                                {"id": "shipping_type_documents", "title": "Documents"},
                                {"id": "shipping_type_petit_colis", "title": "Petit colis"},
                                {"id": "shipping_type_moyen_colis", "title": "Moyen colis"},
                                {"id": "shipping_type_grand_colis", "title": "Grand colis"},
                                {"id": "shipping_type_mixte", "title": "Mixte petit/moyen colis"},
                                {"id": "shipping_type_mixte_tous", "title": "Mixte tous types colis"},
                                {"id": "shipping_type_700", "title": "Menu précédent"},
                                {"id": "shipping_type_701", "title": "Menu principal"}
                            ]

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "button": "Choix type colis ?",
                                        "sections": [
                                            {
                                                "title": "Types d'envoi",
                                                "rows": shipping_types
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "shipping_type_selected")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in send date selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "shipping_type_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("shipping_type_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            shipping_type_id = list_msg_id.replace("shipping_type_", "")

                            if shipping_type_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif shipping_type_id == "700":
                                # Update state for next step

                                text = f"📅 Quand souhaitez-vous envoyer votre colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la date",
                                            "sections": [
                                                {
                                                    "title": "Date d'envoi",
                                                    "rows": [
                                                        {
                                                            "id": "send_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "send_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "send_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "send_date_other",
                                                            "title": "Une date ultérieure"
                                                        },
                                                        {
                                                            "id": "send_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "send_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "send_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200


                            # Store shipping type
                            update_data(sender, 'shipping_type', text_body)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            # Build and send summary
                            text = build_summary(sender)
                            ## You can build a nice summary of the collected info here to show to the user before confirming the request
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                            
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            
                            set_state(sender, "request_confirmation")
                            
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in shipping type selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "request_confirmation":
                        if msg_type == "interactive_button_reply" and button_msg_id in ["parcel_req_Oui", "parcel_req_700", "parcel_req_701"]:
                            # resetting error count on valid selection
                            clear_error_count(sender)


                            if button_msg_id == "parcel_req_701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_msg_id == "parcel_req_700":
                                # Update state for next step

                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = f"📦 Quel est le type d'envoi ?"

                                # List of shipping types - you can replace with actual types from your database
                                shipping_types = [
                                    {"id": "shipping_type_documents", "title": "Documents"},
                                    {"id": "shipping_type_petit_colis", "title": "Petit colis"},
                                    {"id": "shipping_type_moyen_colis", "title": "Moyen colis"},
                                    {"id": "shipping_type_grand_colis", "title": "Grand colis"},
                                    {"id": "shipping_type_mixte", "title": "Mixte petit/moyen colis"},
                                    {"id": "shipping_type_mixte_tous", "title": "Mixte tous types colis"},
                                    {"id": "shipping_type_700", "title": "Menu précédent"},
                                    {"id": "shipping_type_701", "title": "Menu principal"}
                                ]

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {
                                            "text": text.strip()
                                        },
                                        "action": {
                                            "button": "Choix type colis ?",
                                            "sections": [
                                                {
                                                    "title": "Types d'envoi",
                                                    "rows": shipping_types
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "shipping_type_selected")

                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200

                            elif button_msg_id == "parcel_req_Oui":

                                # Create Parcel event
                                payload = {"from_country_id": get_data(sender).get('departure_country_id'),
                                           "to_country_id": get_data(sender).get('destination_country_id'),
                                           "from_city_id": get_data(sender).get('departure_city_id'),
                                           "to_city_id": get_data(sender).get('destination_city_id'),
                                           "travel_period": get_data(sender).get('send_date'),
                                           "shipment_type": get_data(sender).get('shipping_type')}

                                new_parcel_event, message = create_parcel_event_chatbot(sender, payload)
                                if not new_parcel_event:
                                    
                                    if message == "pending_event_exists":
                                        text = "⚠️ Vous avez déjà une demande en cours de traitement. Veuillez patienter ou créer une nouvelle demande ultérieurement."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        clear_data(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Oups, une erreur est survenue lors de la création de votre demande. Veuillez réessayer ultérieurement."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        clear_data(sender)
                                        return "ok", 200

                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un GP disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                # Here you would typically save the confirmed request to your database and/or trigger the next steps of your flow
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)
                                clear_data(sender)
                                return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            return "ok", 200
                    
                    ########################### Parcel Request Flow Steps ###########################
                    #######################################  ENDS HERE #####################################


                    ##########################################################################################
                    ########################### Get Ride to Airport Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_to_airport_data(sender, 'departure_country_id', country_id)
                                update_to_airport_data(sender, 'departure_country', country)
                            
                            
                            airports = get_airports_by_country(get_to_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for a in airports:
                                rows.append({
                                    "id": f"list_airport_{a['id']}",
                                    "title": a['name']
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                            print(f"Available airports for country_id {country_id}:", rows)

                            text = "✈️ Quel est l'aéroport de départ ?"

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                        "sections": [
                                            {
                                                "title": "and",
                                                "rows": rows
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "departure_airport_selected")

                            # clear_state(sender)

                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "departure_airport_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_airport_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            airport_id = list_msg_id.replace("list_airport_", "")
                            if airport_id == "700":
                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                                rows = []
                                countries = get_countries_with_airports()
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})


                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "to_airport_country_selected")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif airport_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure airport
                            airport = text_body
                            if airport:
                                update_to_airport_data(sender, 'departure_airport_id', airport_id)
                                update_to_airport_data(sender, 'departure_airport', airport)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = "📍 D’où partez-vous ?"

                            cities = get_cities_by_country(get_to_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Ville de départ",
                                        "sections": [
                                            {
                                                "title": "Ville de départ",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                            
                            # clear_state(sender) 
                            set_state(sender, "to_airport_departure_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in airport selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "700":
                                airports = get_airports_by_country(get_to_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for a in airports:
                                    rows.append({
                                        "id": f"list_airport_{a['id']}",
                                        "title": a['name']
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                                print(f"Available airports for country_id {country_id}:", rows)

                                text = "✈️ Quel est l'aéroport de départ ?"

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                            "sections": [
                                                {
                                                    "title": "and",
                                                    "rows": rows
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "departure_airport_selected")

                                # clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # Store departure city
                            city = text_body
                            if city:
                                update_to_airport_data(sender, 'departure_city_id', city_id)
                                update_to_airport_data(sender, 'departure_city', city)

                            

                            text = "📅 Quand souhaitez-vous partir ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Date de départ",
                                        "sections": [
                                            {
                                                "title": "Date de départ",
                                                "rows": [
                                                    {
                                                        "id": "dep_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "dep_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "dep_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "dep_date_other",
                                                        "title": "Autre période"
                                                    },
                                                    {
                                                        "id": "dep_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "dep_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)  
                            set_state(sender, "to_airport_departure_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_departure_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("dep_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            dep_date_id = list_msg_id.replace("dep_date_", "")

                            if dep_date_id == "700":
                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = "📍 D’où partez-vous ?"

                                cities = get_cities_by_country(get_to_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Ville de départ",
                                            "sections": [
                                                {
                                                    "title": "Ville de départ",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                
                                # clear_state(sender) 
                                set_state(sender, "to_airport_departure_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif dep_date_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure date preference
                            dep_date_pref = text_body
                            if dep_date_pref:
                                update_to_airport_data(sender, 'departure_date_preference', dep_date_pref)

                            
                            
                            text = "👥 Quel est le nombre de voyageurs ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nombre de voyageurs",
                                        "sections": [
                                            {
                                                "title": "Nombre de voyageurs",
                                                "rows": [
                                                    {
                                                        "id": "num_travelers_1",
                                                        "title": "1️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_travelers_3",
                                                        "title": "2️⃣ 3 ou 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_4",
                                                        "title": "Plus de 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_travelers_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_travelers_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in departure date selection step.")
                            return "ok", 200                        

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_travelers_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_travelers_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_travelers_id = list_msg_id.replace("num_travelers_", "")

                            if num_travelers_id == "700":
                                text = "📅 Quand souhaitez-vous partir ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Date de départ",
                                            "sections": [
                                                {
                                                    "title": "Date de départ",
                                                    "rows": [
                                                        {
                                                            "id": "dep_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "dep_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "dep_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "dep_date_other",
                                                            "title": "Autre période"
                                                        },
                                                        {
                                                            "id": "dep_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "dep_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)  
                                set_state(sender, "to_airport_departure_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_travelers_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of travelers preference
                            num_travelers_pref = text_body
                            if num_travelers_pref:
                                update_to_airport_data(sender, 'num_travelers_preference', num_travelers_pref)
                            
                            # Here you would typically
                            text = "🧳 Combien de petites valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb petites valises",
                                        "sections": [
                                            {
                                                "title": "Nb petites valises",
                                                "rows": [
                                                    {
                                                        "id": "num_small_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_small_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_small_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_small_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_small_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of travelers selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_small_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_small_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_small_cases_id = list_msg_id.replace("num_small_cases_", "")

                            if num_small_cases_id == "700":
                                text = "👥 Quel est le nombre de voyageurs ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "NB de voyageurs",
                                            "sections": [
                                                {
                                                    "title": "NB de voyageurs",
                                                    "rows": [
                                                        {
                                                            "id": "num_travelers_1",
                                                            "title": "1️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_travelers_3",
                                                            "title": "2️⃣ 3 ou 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_4",
                                                            "title": "Plus de 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_travelers_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_travelers_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_small_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of small cases preference
                            num_small_cases_pref = text_body
                            if num_small_cases_pref:
                                update_to_airport_data(sender, 'num_small_cases_preference', num_small_cases_pref)

                            
                            
                            # Here you would
                            text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb valises moyennes",
                                        "sections": [
                                            {
                                                "title": "Nb valises moyennes",
                                                "rows": [
                                                    {
                                                        "id": "num_medium_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_medium_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_medium_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_medium_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_medium_cases_id = list_msg_id.replace("num_medium_cases_", "")

                            if num_medium_cases_id == "700":
                                text = "🧳 Combien de petites valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb petites valises",
                                            "sections": [
                                                {
                                                    "title": "Nb petites valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_small_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_small_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_small_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_small_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_small_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_medium_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of medium cases preference
                            num_medium_cases_pref = text_body
                            if num_medium_cases_pref:
                                update_to_airport_data(sender, 'num_medium_cases_preference', num_medium_cases_pref)

                            # Here you
                            text = "🧳 Combien de grandes valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb grandes valises",
                                        "sections": [
                                            {
                                                "title": "Nb grandes valises",
                                                "rows": [
                                                    {
                                                        "id": "num_big_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_big_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_big_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_big_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_big_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_big_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_big_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_big_cases_id = list_msg_id.replace("num_big_cases_", "")

                            if num_big_cases_id == "700":
                                text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb valises moyennes",
                                            "sections": [
                                                {
                                                    "title": "Nb valises moyennes",
                                                    "rows": [
                                                        {
                                                            "id": "num_medium_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_medium_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_big_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")
                                # Send main menu message
                                client_send_welcome_msg(sender, headers, url)
                                return "ok", 200
                            
                            # Store number of big cases preference
                            num_big_cases_pref = text_body
                            if num_big_cases_pref:
                                update_to_airport_data(sender, 'num_big_cases_preference', num_big_cases_pref)

                            # Here you would
                            text = build_to_airport_summary(sender)
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_summary")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of big cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_summary":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("to_air_req_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            button_id = button_msg_id.replace("to_air_req_", "")

                            if button_id == "700":
                                # User wants to go back to previous menu (number of big cases)
                                text = "🧳 Combien de grandes valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb grandes valises",
                                            "sections": [
                                                {
                                                    "title": "Nb grandes valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_big_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_big_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_big_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_big_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_big_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_to_airport_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_id == "Oui":

                                # Create Driver Pickup event in database with collected data
                                payload = {
                                    "from_country_id": get_to_airport_data(sender).get('departure_country_id'),
                                    "from_airport_id": get_to_airport_data(sender).get('departure_airport_id'),
                                    "from_city_id": get_to_airport_data(sender).get('departure_city_id'),
                                    "travel_period": get_to_airport_data(sender).get('departure_date_preference'),
                                    "num_of_people": get_to_airport_data(sender).get('num_travelers_preference'),
                                    "num_of_small_cases": get_to_airport_data(sender).get('num_small_cases_preference'),
                                    "num_of_med_cases": get_to_airport_data(sender).get('num_medium_cases_preference'),
                                    "num_of_large_cases": get_to_airport_data(sender).get('num_big_cases_preference')
                                }
                                pickup_creation , message = create_pickup_event_chatbot(sender, payload, "Ride to Airport")

                                if not pickup_creation:
                                    if message == "event_already_exists":
                                        text = "⚠️ Vous avez déjà une demande de transport en cours pour ce trajet. Nous vous invitons à patienter le temps que nous trouvions un transporteur correspondant à votre demande ou à créer une nouvelle demande pour un autre trajet."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Une erreur est survenue lors de la création de votre demande. Veuillez réessayer dans quelques instants."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200

                                # Here you would typically trigger the actual service request based on collected data
                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un Transporteur disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                clear_state(sender)
                                clear_to_airport_data(sender)
                                # set_state(sender, "to_airport_request_submitted")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            else:
                                send_error_message(sender, headers, url)
                                increment_error_count(sender)
                                if get_error_count_exceeds_3(sender):
                                    clear_all(sender)
                                    clear_error_count(sender)
                                    print("⚠️ Too many errors. Resetting conversation.")
                                print("⚠️ Unexpected button selection in summary step.")
                                return "ok", 200
                    
                    ########################### Get Ride to Airport Flow Steps ###########################
                    #######################################  ENDS HERE ###################################


                    ##########################################################################################
                    ########################### Get Ride from Airport Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_from_airport_data(sender, 'departure_country_id', country_id)
                                update_from_airport_data(sender, 'departure_country', country)


                            
                            
                            airports = get_airports_by_country(get_from_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for a in airports:
                                rows.append({
                                    "id": f"list_airport_{a['id']}",
                                    "title": a['name']
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                            print(f"Available airports for country_id {country_id}:", rows)

                            text = "✈️ Quel est l’aéroport d’arrivée ?"

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                        "sections": [
                                            {
                                                "title": "and",
                                                "rows": rows
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "departure_from_airport_selected")

                            # clear_state(sender)

                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "departure_from_airport_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_airport_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            airport_id = list_msg_id.replace("list_airport_", "")
                            if airport_id == "700":
                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                                rows = []
                                countries = get_countries_with_airports()
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})


                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "from_airport_country_selected")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif airport_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure airport
                            airport = text_body
                            if airport:
                                update_from_airport_data(sender, 'departure_airport_id', airport_id)
                                update_from_airport_data(sender, 'departure_airport', airport)

                            

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = "📍 Dans quelle ville souhaitez-vous aller ?"

                            cities = get_cities_by_country(get_from_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Ville de départ",
                                        "sections": [
                                            {
                                                "title": "Ville de départ",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                            
                            # clear_state(sender) 
                            set_state(sender, "from_airport_departure_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in airport selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "from_airport_departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "700":
                                airports = get_airports_by_country(get_from_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for a in airports:
                                    rows.append({
                                        "id": f"list_airport_{a['id']}",
                                        "title": a['name']
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                                print(f"Available airports for country_id {country_id}:", rows)

                                text = "✈️ Quel est l’aéroport d’arrivée ?"

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                            "sections": [
                                                {
                                                    "title": "and",
                                                    "rows": rows
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "departure_from_airport_selected")

                                # clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # Store departure city
                            city = text_body
                            if city:
                                update_from_airport_data(sender, 'departure_city_id', city_id)
                                update_from_airport_data(sender, 'departure_city', city)

                            

                            text = "📅 Quand arrivez-vous ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Date de départ",
                                        "sections": [
                                            {
                                                "title": "Date de départ",
                                                "rows": [
                                                    {
                                                        "id": "dep_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "dep_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "dep_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "dep_date_other",
                                                        "title": "Autre période"
                                                    },
                                                    {
                                                        "id": "dep_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "dep_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)  
                            set_state(sender, "from_airport_departure_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_departure_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("dep_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            dep_date_id = list_msg_id.replace("dep_date_", "")

                            if dep_date_id == "700":
                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = "📍 Dans quelle ville souhaitez-vous aller ?"

                                cities = get_cities_by_country(get_from_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Ville de départ",
                                            "sections": [
                                                {
                                                    "title": "Ville de départ",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                
                                # clear_state(sender) 
                                set_state(sender, "from_airport_departure_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif dep_date_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure date preference
                            dep_date_pref = text_body
                            if dep_date_pref:
                                update_from_airport_data(sender, 'departure_date_preference', dep_date_pref)

                            
                            
                            text = "👥 Quel est le nombre de voyageurs ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nombre de voyageurs",
                                        "sections": [
                                            {
                                                "title": "Nombre de voyageurs",
                                                "rows": [
                                                    {
                                                        "id": "num_travelers_1",
                                                        "title": "1️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_travelers_3",
                                                        "title": "2️⃣ 3 ou 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_4",
                                                        "title": "Plus de 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_travelers_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_travelers_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in departure date selection step.")
                            return "ok", 200 

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_travelers_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_travelers_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_travelers_id = list_msg_id.replace("num_travelers_", "")

                            if num_travelers_id == "700":
                                text = "📅 Quand arrivez-vous ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Date de départ",
                                            "sections": [
                                                {
                                                    "title": "Date de départ",
                                                    "rows": [
                                                        {
                                                            "id": "dep_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "dep_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "dep_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "dep_date_other",
                                                            "title": "Autre période"
                                                        },
                                                        {
                                                            "id": "dep_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "dep_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)  
                                set_state(sender, "from_airport_departure_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_travelers_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of travelers preference
                            num_travelers_pref = text_body
                            if num_travelers_pref:
                                update_from_airport_data(sender, 'num_travelers_preference', num_travelers_pref)


                            # Here you would typically
                            text = "🧳 Combien de petites valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb petites valises",
                                        "sections": [
                                            {
                                                "title": "Nb petites valises",
                                                "rows": [
                                                    {
                                                        "id": "num_small_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_small_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_small_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_small_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_small_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of travelers selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_small_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_small_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_small_cases_id = list_msg_id.replace("num_small_cases_", "")

                            if num_small_cases_id == "700":
                                text = "👥 Quel est le nombre de voyageurs ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "NB de voyageurs",
                                            "sections": [
                                                {
                                                    "title": "NB de voyageurs",
                                                    "rows": [
                                                        {
                                                            "id": "num_travelers_1",
                                                            "title": "1️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_travelers_3",
                                                            "title": "2️⃣ 3 ou 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_4",
                                                            "title": "Plus de 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_travelers_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_travelers_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_small_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of small cases preference
                            num_small_cases_pref = text_body
                            if num_small_cases_pref:
                                update_from_airport_data(sender, 'num_small_cases_preference', num_small_cases_pref)

                            
                            
                            # Here you would
                            text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb valises moyennes",
                                        "sections": [
                                            {
                                                "title": "Nb valises moyennes",
                                                "rows": [
                                                    {
                                                        "id": "num_medium_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_medium_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_medium_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_medium_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_medium_cases_id = list_msg_id.replace("num_medium_cases_", "")

                            if num_medium_cases_id == "700":
                                text = "🧳 Combien de petites valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb petites valises",
                                            "sections": [
                                                {
                                                    "title": "Nb petites valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_small_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_small_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_small_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_small_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_small_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_medium_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of medium cases preference
                            num_medium_cases_pref = text_body
                            if num_medium_cases_pref:
                                update_from_airport_data(sender, 'num_medium_cases_preference', num_medium_cases_pref)

                            
                            
                            # Here you
                            text = "🧳 Combien de grandes valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb grandes valises",
                                        "sections": [
                                            {
                                                "title": "Nb grandes valises",
                                                "rows": [
                                                    {
                                                        "id": "num_big_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_big_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_big_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_big_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_big_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_big_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_big_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_big_cases_id = list_msg_id.replace("num_big_cases_", "")

                            if num_big_cases_id == "700":
                                text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb valises moyennes",
                                            "sections": [
                                                {
                                                    "title": "Nb valises moyennes",
                                                    "rows": [
                                                        {
                                                            "id": "num_medium_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_medium_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_big_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")
                                # Send main menu message
                                client_send_welcome_msg(sender, headers, url)
                                return "ok", 200
                            
                            # Store number of big cases preference
                            num_big_cases_pref = text_body
                            if num_big_cases_pref:
                                update_from_airport_data(sender, 'num_big_cases_preference', num_big_cases_pref)

                            
                            
                            # Here you would
                            text = build_from_airport_summary(sender)
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_summary")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of big cases selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_summary":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("from_air_req_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            button_id = button_msg_id.replace("from_air_req_", "")

                            if button_id == "700":
                                # User wants to go back to previous menu (number of big cases)
                                text = "🧳 Combien de grandes valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb grandes valises",
                                            "sections": [
                                                {
                                                    "title": "Nb grandes valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_big_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_big_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_big_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_big_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_big_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")
                                clear_from_airport_data(sender)

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_id == "Oui":

                                # Create Driver Pickup event in database with collected data
                                payload = {
                                    "from_country_id": get_to_airport_data(sender).get('departure_country_id'),
                                    "from_airport_id": get_to_airport_data(sender).get('departure_airport_id'),
                                    "from_city_id": get_to_airport_data(sender).get('departure_city_id'),
                                    "travel_period": get_to_airport_data(sender).get('departure_date_preference'),
                                    "num_of_people": get_to_airport_data(sender).get('num_travelers_preference'),
                                    "num_of_small_cases": get_to_airport_data(sender).get('num_small_cases_preference'),
                                    "num_of_med_cases": get_to_airport_data(sender).get('num_medium_cases_preference'),
                                    "num_of_large_cases": get_to_airport_data(sender).get('num_big_cases_preference')
                                }
                                pickup_creation , message = create_pickup_event_chatbot(sender, payload, "Airport Pickup")

                                if not pickup_creation:
                                    if message == "event_already_exists":
                                        text = "⚠️ Vous avez déjà une demande de transport en cours pour ce trajet. Nous vous invitons à patienter le temps que nous trouvions un transporteur correspondant à votre demande ou à créer une nouvelle demande pour un autre trajet."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Une erreur est survenue lors de la création de votre demande. Veuillez réessayer dans quelques instants."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200

                                # Here you would typically trigger the actual service request based on collected data
                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un Transporteur disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                clear_state(sender)
                                clear_from_airport_data(sender)
                                # set_state(sender, "to_airport_request_submitted")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            else:
                                send_error_message(sender, headers, url)
                                increment_error_count(sender)
                                if get_error_count_exceeds_3(sender):
                                    clear_all(sender)
                                    clear_error_count(sender)
                                    print("⚠️ Too many errors. Resetting conversation.")
                                print("⚠️ Unexpected button selection in summary step.")
                                return "ok", 200


                    ########################### Get Ride from Airport Flow Steps ###########################
                    #######################################  ENDS HERE ###################################

                    ##########################################################################################
                    ########################### Client Others Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    elif get_state(sender) == "client_others":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("other_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            list_msg_id = list_msg_id.replace("other_", "")

                            if list_msg_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif list_msg_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif list_msg_id in ["gp", "AIBD", "contact"]:
                                text = f"📝 Merci pour ces informations !\nVoici le récapitulatif de votre demande :\n\n👉 Autres services -> *{text_body}*\n\nMerci de vérifier que tout est correct 😊\n\nVeuillez confirmer la demande :"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button",
                                        "body": {
                                            "text": text.strip()
                                        },
                                        "action": {
                                            "buttons": [
                                                {
                                                    "type": "reply",
                                                    "reply": {
                                                        "id": "others_Oui",
                                                        "title": "Oui"
                                                    }
                                                },
                                                {
                                                    "type": "reply",
                                                    "reply": {
                                                        "id": "others_700",
                                                        "title": "Menu précédent"
                                                    }
                                                },
                                                {
                                                    "type": "reply",
                                                    "reply": {
                                                        "id": "others_701",
                                                        "title": "Menu principal"
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                }


                                # Update state for next step
                                set_state(sender, "others_confirm")
                                send_whatsapp_message(sender, payload, headers, url)
                                return "Okay", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected button selection in summary step.")
                            return "ok", 200

                    elif get_state(sender) == "others_confirm":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("others_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            option_id = button_msg_id.replace("others_", "")

                            if option_id == "700":
                                text = "🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\nVeuillez sélectionner le service de votre choix :"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la date",
                                            "sections": [
                                                {
                                                    "title": "Date d'envoi",
                                                    "rows": [
                                                        {
                                                            "id": "other_gp",
                                                            "title": "Inscription GP"
                                                        },
                                                        {
                                                            "id": "other_AIBD",
                                                            "title": "Inscription Transp. AIBD"
                                                        },
                                                        {
                                                            "id": "other_contact",
                                                            "title": "Contact service client"
                                                        },
                                                        {
                                                            "id": "other_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "other_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    },
                                }

                                set_state(sender, "client_others")

                                send_whatsapp_message(sender, payload, headers, url)
                                return "okay", 200

                            elif option_id == "701":

                                # Update state for next step
                                set_state(sender, "service_selected")
                                clear_from_airport_data(sender)

                                client_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif option_id == "Oui":
                                # Here you would typically trigger the actual service request based on collected data
                                text = "📩 Merci, votre demande a bien été prise en compte.\n\n📞 Nous vous contacterons très bientôt !\n\n🙏 Merci de nous avoir fait confiance.\nÀ très bientôt pour un nouveau service !"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                clear_state(sender)
                                # set_state(sender, "to_airport_request_submitted")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            else:
                                send_error_message(sender, headers, url)
                                increment_error_count(sender)
                                if get_error_count_exceeds_3(sender):
                                    clear_all(sender)
                                    clear_error_count(sender)
                                    print("⚠️ Too many errors. Resetting conversation.")
                                print("⚠️ Unexpected button selection in summary step.")
                                return "ok", 200

                    
                    ########################### Client Others Flow Steps ###########################
                    #######################################  ENDS HERE ###################################
                    
                    else:
                        print("⚠️ Message received in unknown state. Resetting conversation.")
                        clear_all(sender)
                        return "ok", 200

                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

                elif user_role == "professional":
                    if not get_state(sender):
                        # Update state for next step
                        set_state(sender, "service_selected")

                        # Build interactive reply
                        professional_send_welcome_msg(sender, headers, url)

                        # # Send message to WhatsApp (sync httpx client for Flask route)
                        # send_whatsapp_message(sender, payload, headers, url)

                        return "ok", 200
                    
                    # New flow: user has selected a service from the menu
                    elif get_state(sender) == "service_selected":
                        ## Continue here
                        ## Publish a GP trip
                        # ✅✅✅
                        if msg_type == "interactive_list_reply" and list_msg_id == "role_pro_1":
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            text = ""

                            ## Check if the professional has enough credits
                            
                            if not can_user_perform_action(sender, "GP Publish tour"):
                                text = "Vous ne disposez pas de suffisamment de crédits sur votre compte pour publier un voyage GP.\n\n🛒 Pour acheter des crédits 💰, cliquez sur le lien 🔗 ci-dessous :\n👉 https://jokko-ai.sn/"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {"body": text}
                                }
                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)
                                return "ok", 200

                            text = "🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Quel est le pays de départ ?"
                            countries, count = get_countries()
                            rows = []
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # rows.append({"id": f"list_country_other", "title": "Autre"})
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "pb_gp_trip_depart_country_select")
                            
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_pro_2":
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            from db_gp_routes import get_gp_routes_for_professional_chatbot
                            routes = get_gp_routes_for_professional_chatbot(sender)
                            if len(routes) == 0:
                                text = "🚫 Vous n'avez actuellement aucun itinéraire GP publié. Veuillez publier un nouveau trajet GP."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {"body": text}
                                }
                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)
                                return "ok", 200

                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                            rows = []

                            for route in routes:
                                from_city = route['from_city']
                                to_city = route['to_city']
                                rows.append({
                                    "id": f"list_route_{route['id']}",
                                    "title": f"{from_city} ➡️ {to_city}"
                                })
                            # Appending  Autre trajet
                            # rows.append({"id": f"list_route_other", "title": "Autre trajet"})
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_route_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_route_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Elige la ruta",
                                        "sections": [
                                            {
                                                "title": "Trajets",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "gp_status_route_select")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_pro_3":
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            from db_gp_routes import get_gp_routes_for_professional_chatbot
                            routes = get_gp_routes_for_professional_chatbot(sender)
                            if len(routes) == 0:
                                text = "🚫 Vous n'avez actuellement aucun itinéraire GP publié. Veuillez publier un nouveau trajet GP."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {"body": text}
                                }
                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)
                                return "ok", 200
                            

                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🗑️ Quel trajet souhaitez-vous supprimer ?"

                            rows = []

                            for route in routes:
                                from_city = route['from_city']
                                to_city = route['to_city']
                                rows.append({
                                    "id": f"list_route_{route['id']}",
                                    "title": f"{from_city} ➡️ {to_city}"
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_route_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_route_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Elige la ruta",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "delete_gp_route_select")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200


                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_pro_4":
                            set_state(sender, "shipment_country_selected")

                            send_service_selected_role_customer1_msg(sender, headers, url)
                            
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            # send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_pro_5":
                            # resetting error count on valid selection
                            clear_error_count(sender)
                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                            rows = []
                            countries = get_countries_with_airports()
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "to_airport_country_selected")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_pro_6":
                            # resetting error count on valid selection
                            clear_error_count(sender)
                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l'aéroport d'arrivée ?"

                            rows = []
                            countries = get_countries_with_airports()
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "from_airport_country_selected")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_pro_7":
                            text = "🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\nVeuillez sélectionner le service de votre choix :"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Type de service",
                                        "sections": [
                                            {
                                                "title": "Date d'envoi",
                                                "rows": [
                                                    {
                                                        "id": "other_r_cred",
                                                        "title": "Afficher crédit restants"
                                                    },
                                                    {
                                                        "id": "other_pur_li",
                                                        "title": "Acheter des crédits"
                                                    },
                                                    {
                                                        "id": "other_contact",
                                                        "title": "Contact service client"
                                                    },
                                                    {
                                                        "id": "other_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "other_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "pro_others")

                            send_whatsapp_message(sender, payload, headers, url)
                            return "okay", 200


                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("eee⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200
                            

                    ##########################################################################################
                    ################################### Professional ###############################################
                    ########################### Publish a GP trip Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################
                    # ✅✅✅
                    elif get_state(sender) == "pb_gp_trip_depart_country_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")
                            if country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            elif country_id == "700":

                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)
                                
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                # send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                 
                            # Store departure country into redis
                            country = text_body
                            if country:
                                update_pb_gp_trip_data(sender, 'pb_gp_trip_departure_country_id', country_id)
                                update_pb_gp_trip_data(sender, 'pb_gp_trip_departure_country', country)
                            
                            text = "📍 Quelle est la ville de départ ?"
                            rows = []
                            # Get Cities for the selected country
                            cities = get_cities_by_country(get_pb_gp_trip_data(sender).get('pb_gp_trip_departure_country_id'))
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la ville",
                                        "sections": [
                                            {
                                                "title": "Villes",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                            set_state(sender, "pb_gp_trip_depart_city_select")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in departure country selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "pb_gp_trip_depart_city_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif city_id == "700":

                                text = "🌍 Quel est le pays de départ ?"
                                countries = get_countries()
                                rows = []
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                rows.append({"id": f"list_country_other", "title": "Autre"})
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }

                                set_state(sender, "pb_gp_trip_depart_country_select")

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200

                            
                            # Store departure city into redis
                            city = text_body
                            if city:
                                update_pb_gp_trip_data(sender, 'pb_gp_trip_departure_city_id', city_id)
                                update_pb_gp_trip_data(sender, 'pb_gp_trip_departure_city', city)
                            
                            text = "🌍 Quel est le pays de destination ?"
                            rows = []
                            countries, count = get_countries()
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "pb_gp_trip_dest_country_select")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in destination city selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "pb_gp_trip_dest_country_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")
                            if country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "700":
                                text = "📍 Quelle est la ville de départ ?"
                                rows = []
                                cities = get_cities_by_country(get_pb_gp_trip_data(sender).get('pb_gp_trip_departure_country_id'))
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding Other option
                                rows.append({"id": f"list_city_other", "title": "Autre"})
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la ville",
                                            "sections": [
                                                {
                                                    "title": "Villes",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "pb_gp_trip_dest_city_select")
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            # Store destination country into redis
                            country = text_body
                            if country:
                                update_pb_gp_trip_data(sender, 'pb_gp_trip_dest_country_id', country_id)
                                update_pb_gp_trip_data(sender, 'pb_gp_trip_dest_country', country)
                            
                            text = "📍 Quelle est la ville de destination ?"
                            rows = []
                            # Get Cities for the selected country
                            cities = get_cities_by_country(get_pb_gp_trip_data(sender).get('pb_gp_trip_dest_country_id'))
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la ville",
                                        "sections": [
                                            {
                                                "title": "Villes",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "pb_gp_trip_dest_city_select")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in destination country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "pb_gp_trip_dest_city_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")
                            if city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif city_id == "700":
                                text = "🌍 Quel est le pays de destination ?"
                                countries, count = get_countries()
                                rows = []
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding other country
                                rows.append({"id": f"list_country_other", "title": "Autre"})
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }

                                set_state(sender, "pb_gp_trip_dest_country_select")

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            # Store destination city into redis
                            city = text_body
                            if city:
                                update_pb_gp_trip_data(sender, 'pb_gp_trip_dest_city_id', city_id)
                                update_pb_gp_trip_data(sender, 'pb_gp_trip_dest_city', city)
                            
                            text = "📅 Quand a lieu le voyage ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la date",
                                        "sections": [
                                            {
                                                "title": "Date du voyage",
                                                "rows": [
                                                    {
                                                        "id": "gp_trip_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "gp_trip_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "gp_trip_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "gp_trip_date_other",
                                                        "title": "Une date ultérieure"
                                                    },
                                                    {
                                                        "id": "gp_trip_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "gp_trip_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                },
                            }
                            set_state(sender, "pb_gp_trip_date_select")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in destination city selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "pb_gp_trip_date_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("gp_trip_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            date_option = list_msg_id.replace("gp_trip_date_", "")

                            if date_option == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif date_option == "700":
                                text = "📍 Quelle est la ville de destination ?"
                                rows = []
                                cities = get_cities_by_country(get_pb_gp_trip_data(sender).get('pb_gp_trip_dest_country_id'))
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding Other option
                                rows.append({
                                    "id": "list_city_other",
                                    "title": "Autre"
                                })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la ville",
                                            "sections": [
                                                {
                                                    "title": "Villes",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "pb_gp_trip_dest_city_select")
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            # Store trip date into redis
                            update_pb_gp_trip_data(sender, 'pb_gp_trip_date_option', date_option)
                            update_pb_gp_trip_data(sender, 'pb_gp_trip_date_option_text', text_body)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = "📦 Quel type d’envoi pouvez-vous prendre ?"

                            # List of shipping types - you can replace with actual types from your database
                            shipping_types = [
                                {"id": "gp_shipping_type_documents", "title": "Documents"},
                                {"id": "gp_shipping_type_petit_colis", "title": "Petit colis"},
                                {"id": "gp_shipping_type_moyen_colis", "title": "Moyen colis"},
                                {"id": "gp_shipping_type_grand_colis", "title": "Grand colis"},
                                {"id": "gp_shipping_type_mixte", "title": "Mixte petit/moyen colis"},
                                {"id": "gp_shipping_type_mixte_tous", "title": "Mixte tous types colis"},
                                {"id": "gp_shipping_type_700", "title": "Menu précédent"},
                                {"id": "gp_shipping_type_701", "title": "Menu principal"}
                            ]

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "button": "Choix type colis ?",
                                        "sections": [
                                            {
                                                "title": "Types d'envoi",
                                                "rows": shipping_types
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "pb_gp_trip_shipping_type_select")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in trip date selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "pb_gp_trip_shipping_type_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("gp_shipping_type_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            shipping_type_id = list_msg_id.replace("gp_shipping_type_", "")

                            if shipping_type_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif shipping_type_id == "700":
                                text = "📅 Quand a lieu le voyage ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la date",
                                            "sections": [
                                                {
                                                    "title": "Date du voyage",
                                                    "rows": [
                                                        {
                                                            "id": "gp_trip_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "gp_trip_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "gp_trip_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "gp_trip_date_other",
                                                            "title": "Une date ultérieure"
                                                        },
                                                        {
                                                            "id": "gp_trip_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "gp_trip_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "pb_gp_trip_date_select")
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            # Store shipping type into redis
                            update_pb_gp_trip_data(sender, 'pb_gp_trip_shipping_type_id', shipping_type_id)
                            update_pb_gp_trip_data(sender, 'pb_gp_trip_shipping_type_text', text_body)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            
                            summary_text = build_pb_gp_trip_summary(sender)
                            
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": summary_text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "gp_trp_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "gp_trp_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "gp_trp_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "pb_gp_trip_confirmation")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in shipping type selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "pb_gp_trip_confirmation":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("gp_trp_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            button_id = button_msg_id.replace("gp_trp_", "")
                            if button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif button_id == "700":
                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = "📦 Quel type d’envoi pouvez-vous prendre ?"

                                # List of shipping types - you can replace with actual types from your database
                                shipping_types = [
                                    {"id": "gp_shipping_type_documents", "title": "Documents"},
                                    {"id": "gp_shipping_type_petit_colis", "title": "Petit colis"},
                                    {"id": "gp_shipping_type_moyen_colis", "title": "Moyen colis"},
                                    {"id": "gp_shipping_type_grand_colis", "title": "Grand colis"},
                                    {"id": "gp_shipping_type_mixte", "title": "Mixte petit/moyen colis"},
                                    {"id": "gp_shipping_type_mixte_tous", "title": "Mixte tous types colis"},
                                    {"id": "gp_shipping_type_700", "title": "Menu précédent"},
                                    {"id": "gp_shipping_type_701", "title": "Menu principal"}
                                ]

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {
                                            "text": text.strip()
                                        },
                                        "action": {
                                            "button": "Choix type colis ?",
                                            "sections": [
                                                {
                                                    "title": "Types d'envoi",
                                                    "rows": shipping_types
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "pb_gp_trip_shipping_type_select")

                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif button_id == "Oui":

                                # Clear GP trip data from redis as flow is completed
                                # clear_pb_gp_trip_data(sender)

                                # Create GP trip in the database
                                # TODO - Create GP trip in the database with the collected data. 
                                from db_gp_routes import create_route_for_professional_chatbot
                                # get_pb_gp_trip_data(sender).get('pb_gp_trip_dest_country_id')
                                route_data = {
                                    "from_country_id": get_pb_gp_trip_data(sender).get('pb_gp_trip_departure_country_id'),
                                    "to_country_id": get_pb_gp_trip_data(sender).get('pb_gp_trip_dest_country_id'),
                                    "from_city_id": get_pb_gp_trip_data(sender).get('pb_gp_trip_departure_city_id'),
                                    "to_city_id": get_pb_gp_trip_data(sender).get('pb_gp_trip_dest_city_id'),
                                    "travel_period": get_pb_gp_trip_data(sender).get('pb_gp_trip_date_option_text'),
                                    "shipment_type": get_pb_gp_trip_data(sender).get('pb_gp_trip_shipping_type_text')
                                }
                                print(route_data)
                                result, msg = create_route_for_professional_chatbot(sender, route_data)
                                text = ""
                                if not result:
                                    if msg == "not_all_data":
                                        text = "❌ Oups, il semble qu'il manque des informations pour finaliser votre demande. Veuillez recommencer le processus et vous assurer de fournir toutes les informations nécessaires. Nous nous excusons pour ce désagrément."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)
                                        return "okay", 200
                                    
                                    elif msg == "deduction_failed":
                                        text = "❌ Oups, une erreur est survenue lors de la déduction de vos crédits. Veuillez réessayer dans quelques instants. Si le problème persiste, n'hésitez pas à contacter notre support client. Nous nous excusons pour ce désagrément."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)
                                        return "okay", 200
                                    
                                    elif msg == "insufficient_credits":
                                        text = "Vous ne disposez pas de suffisamment de crédits sur votre compte pour publier un voyage GP.\n\n🛒 Pour acheter des crédits 💰, cliquez sur le lien 🔗 ci-dessous :\n👉 https://jokko-ai.sn/"
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "okay", 200
                                    
                                    elif msg == "no_user":
                                        text = "❌ Oups, nous n'avons pas pu trouver votre profil utilisateur. Veuillez vous assurer que vous avez un compte chez nous et réessayer. Si le problème persiste, n'hésitez pas à contacter notre support client. Nous nous excusons pour ce désagrément."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)
                                        clear_state(sender)
                                        return "okay", 200
                                    
                                    elif msg == "existing_route":
                                        text = "❌ Oups, il semble que vous ayez déjà un trajet en cours. Veuillez vérifier vos trajets existants avant d'en créer un nouveau. Nous nous excusons pour ce désagrément."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "okay", 200
                                    
                                    elif msg == "exception":
                                        text = "❌ Oups, une erreur est survenue lors de la création de votre trajet. Veuillez réessayer dans quelques instants. Si le problème persiste, n'hésitez pas à contacter notre support client. Nous nous excusons pour ce désagrément."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)
                                        clear_state(sender)
                                        return "okay", 200
                                else:
                                    text = "✅ Votre trajet a été créé avec succès !"
                                    
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }


                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)

                                # Reset state and data for new interactions
                                clear_state(sender)

                                clear_data(sender)

                                return "okay", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in shipping type selection step.")
                            return "ok", 200
                            

                    ########################### Publish a GP trip Flow Steps ###########################
                    #######################################  ENDS HERE ################################-----

                    ##########################################################################################
                    ################################### Professional ###############################################
                    ########################### GP Status Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################
                    # ✅✅✅
                    elif get_state(sender) == "gp_status_route_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_route_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            route_id = list_msg_id.replace("list_route_", "")
                            if route_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")
                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif route_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)


                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store selected route into redis
                            route = text_body
                            if route:
                                update_gp_routes(sender, 'gp_status_route_id', route_id)
                                update_gp_routes(sender, 'gp_status_route', route)
                            
                            text = "🔄 Quel est votre statut actuel pour ce trajet ?"

                            rows = []
                            # List of GP status options - you can replace with actual statuses from your database
                            gp_status_options = [
                                {"id": "gp_stat_avail", "title": "Disponible"},
                                {"id": "gp_stat_unavail", "title": "Indisponible"},
                                {"id": "gp_stat_700", "title": "Menu précédent"},
                                {"id": "gp_stat_701", "title": "Menu principal"}
                            ]

                            for status in gp_status_options:
                                rows.append({
                                    "id": status["id"],
                                    "title": status["title"]
                                })

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le statut",
                                        "sections": [
                                            {
                                                "title": "Statut du trajet",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "gp_status_select")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in GP status route selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "gp_status_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("gp_stat_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            status_id = list_msg_id.replace("gp_stat_", "")

                            if status_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)


                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif status_id == "700":
                                from db_gp_routes import get_gp_routes_for_professional_chatbot
                                routes = get_gp_routes_for_professional_chatbot(sender)
                                if len(routes) == 0:
                                    text = "🚫 Vous n'avez actuellement aucun itinéraire GP publié. Veuillez publier un nouveau trajet GP."
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": sender,
                                        "type": "text",
                                        "text": {"body": text}
                                    }
                                    send_whatsapp_message(sender, payload, headers, url)

                                    clear_state(sender)
                                    return "ok", 200

                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                                rows = []

                                for route in routes:
                                    from_city = route['from_city']
                                    to_city = route['to_city']
                                    rows.append({
                                        "id": f"list_route_{route['id']}",
                                        "title": f"{from_city} ➡️ {to_city}"
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_route_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_route_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Elige la ruta",
                                            "sections": [
                                                {
                                                    "title": "Trajets",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "gp_status_route_select")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            # Store selected status into redis
                            status = text_body
                            if status:
                                update_gp_routes(sender, 'gp_status_id', status_id)
                                update_gp_routes(sender, 'gp_status', status)
                            
                            text = build_pb_gp_status_summary(sender)

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "buttons": [
                                            {"type": "reply", "reply": {"id": "gp_stat_oui", "title": "Oui"}},
                                            {"type": "reply", "reply": {"id": "gp_stat_700", "title": "Menu précédent"}},
                                            {"type": "reply", "reply": {"id": "gp_stat_701", "title": "Menu principal"}},
                                        ]
                                    },
                                },
                            }

                            # set state to confirmation step
                            set_state(sender, "gp_status_confirmation")

                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            
                            print("⚠️ Unexpected message type or list selection in GP status selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "gp_status_confirmation":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("gp_stat_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)
                            button_id = button_msg_id.replace("gp_stat_", "")

                            if button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")
                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            

                            elif button_id == "700":
                                # User wants to go back to previous menu
                                text = f"🔄 Quel est votre statut actuel pour ce trajet ?"
                                rows = []

                                # List of GP status options - you can replace with actual statuses from your database
                                gp_status_options = [
                                    {"id": "gp_stat_avail", "title": "Disponible"},
                                    {"id": "gp_stat_unavail", "title": "Indisponible"},
                                    {"id": "gp_stat_700", "title": "Menu précédent"},
                                    {"id": "gp_stat_701", "title": "Menu principal"}
                                ]

                                for status in gp_status_options:
                                    rows.append({
                                        "id": status["id"],
                                        "title": status["title"]
                                    })
                                
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le statut",
                                            "sections": [
                                                {
                                                    "title": "Statut du trajet",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }

                                set_state(sender, "gp_status_select")

                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif button_id == "oui":

                                # Change status of the route in the database based on the selected status and route
                                from db_gp_routes import update_professional_route_status_chatbot
                                route_id = get_gp_routes(sender).get('gp_status_route_id')
                                new_status = get_gp_routes(sender).get('gp_status')
                                result, msg = update_professional_route_status_chatbot(route_id, new_status)
                                if not result:
                                    if msg == "already_in_status":
                                        text = f"ℹ️ Votre trajet est déjà marqué comme '{new_status}'. Aucune mise à jour n'était nécessaire."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                    
                                    elif msg == "insufficient_credits":
                                        text = "Vous ne disposez pas de suffisamment de crédits sur votre compte pour publier un voyage GP.\n\n🛒 Pour acheter des crédits 💰, cliquez sur le lien 🔗 ci-dessous :\n👉 https://jokko-ai.sn/"
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200

                                    elif msg == "deduction_failed":
                                        text = "Des erreurs se sont produites lors de la modification du statut du voyage. Veuillez contacter l'assistance."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "Des erreurs se sont produites lors de la modification du statut du voyage. Veuillez contacter l'assistance."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200

                                text = "📩 Merci, votre demande a bien été prise en compte.\n\n🙏 Merci de nous avoir fait confiance.\nÀ très bientôt pour un nouveau service !"
                                
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)

                                return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            return "ok", 200


                    ########################### GP Status trip Flow Steps ###########################
                    #######################################  ENDS HERE ################################-----



                    ##########################################################################################
                    ################################### Professional ###############################################
                    ########################### GP route delete Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################
                    # ✅✅✅
                    elif get_state(sender) == "delete_gp_route_select": 
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_route_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            route_id = list_msg_id.replace("list_route_", "")
                            if route_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")
                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif route_id == "700":

                                # Update state for next step
                                set_state(sender, "service_selected")
                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                        
                            
                            route_to_delete = text_body
                            update_delete_gp_route(sender, "route_to_delete", route_to_delete)
                            update_delete_gp_route(sender, "route_id_to_delete", route_id)
                            
                            # Here you would typically delete the selected route from your database
                            text = f"📝 Merci pour ces informations \n\nVoici le récapitulatif de votre demande :\n\n{route_to_delete}\n\nMerci de vérifier que tout est correct 😊\n\nVeuillez confirmer la demande :"

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "buttons": [
                                            {"type": "reply", "reply": {"id": "gp_del_oui", "title": "Oui"}},
                                            {"type": "reply", "reply": {"id": "gp_del_700", "title": "Menu précédent"}},
                                            {"type": "reply", "reply": {"id": "gp_del_701", "title": "Menu principal"}},
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "delete_gp_route_confirmation")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in GP route delete selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "delete_gp_route_confirmation":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("gp_del_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            button_id = button_msg_id.replace("gp_del_", "")
                            if button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")
                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # ✅✅✅
                            elif button_id == "700":
                                # User wants to go back to previous menu
                                from db_gp_routes import get_gp_routes_for_professional_chatbot
                                routes = get_gp_routes_for_professional_chatbot(sender)
                                if len(routes) == 0:
                                    text = "🚫 Vous n'avez actuellement aucun itinéraire GP publié. Veuillez publier un nouveau trajet GP."
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": sender,
                                        "type": "text",
                                        "text": {"body": text}
                                    }
                                    send_whatsapp_message(sender, payload, headers, url)

                                    clear_state(sender)
                                    return "ok", 200
                                

                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🗑️ Quel trajet souhaitez-vous supprimer ?"

                                rows = []

                                for route in routes:
                                    from_city = route['from_city']
                                    to_city = route['to_city']
                                    rows.append({
                                        "id": f"list_route_{route['id']}",
                                        "title": f"{from_city} ➡️ {to_city}"
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_route_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_route_701", "title": "Menu principal"})


                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Elige la ruta",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "delete_gp_route_select")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            # ✅✅✅
                            elif button_id == "oui":
                                from db_gp_routes import delete_professional_route
                                delete_result = delete_professional_route(get_delete_gp_route(sender).get('route_id_to_delete'))

                                if not delete_result:
                                    text = "Des erreurs se sont produites lors de la suppression du trajet. Veuillez contacter l'assistance."
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": sender,
                                        "type": "text",
                                        "text": {
                                            "body": text.strip()
                                        }
                                    }

                                    send_whatsapp_message(sender, payload, headers, url)
                                    clear_state(sender)
                                    return "ok", 200
                                
                                # Here you would typically delete the selected route from your database
                                text = "📩 Merci, votre demande a bien été prise en compte.\n\n🙏 Merci de nous avoir fait confiance.\nÀ très bientôt pour un nouveau service !"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)

                                return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in GP route delete confirmation step.")

                            return "ok", 200


                    ########################### GP Route delete Flow Steps ###########################
                    #######################################  ENDS HERE ################################-----


                    ##########################################################################################
                    ################################### Client ###############################################
                    ########################### Parcel Request Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "shipment_country_selected":
                        # clear_data(sender)  # clearing any previously stored data to avoid conflicts and ensure clean state for new request
                        # clear_state(sender) # clearing state to avoid conflicts and ensure clean state for new request, we will set the correct state at the end of this block based on user selection
                        # return "ok", 200
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_data(sender, 'departure_country_id', country_id)
                                update_data(sender, 'departure_country', country)
                            
                            set_state(sender, "departure_city_selected")
                            
                            send_city_selection_msg(sender, headers, url, get_data(sender).get('departure_country_id'))

                            return "ok", 200
                        
                        else:

                            send_whatsapp_message(sender, payload, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif city_id == "700":
                                # Store service type
                                update_data(sender, 'service_type', 'Envoyer un colis')

                                set_state(sender, "shipment_country_selected")

                                send_service_selected_role_customer1_msg(sender, headers, url)
                                
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                # send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200


                            # Store departure city
                            city = text_body
                            if city:
                                update_data(sender, 'departure_city_id', city_id)
                                update_data(sender, 'departure_city', city)

                            countries, count = get_countries()
                            rows = []
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})
                            text = f"🌍 Dans quel pays allez-vous envoyer le colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "destination_country_selected")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "destination_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "700":
                                
                                set_state(sender, "departure_city_selected")
                            
                                send_city_selection_msg(sender, headers, url, get_data(sender).get('departure_country_id'))

                                return "ok", 200

                            # Store destination country
                            country = text_body
                            if country:
                                update_data(sender, 'destination_country_id', country_id)
                                update_data(sender, 'destination_country', country)

                            cities = get_cities_by_country(get_data(sender).get('destination_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})
                            
                            text = f"📍 Dans quelle ville allez-vous envoyer le colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la ville",
                                        "sections": [
                                            {
                                                "title": "Villes",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "destination_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "text",
                                "text": {
                                    "body": text.strip()
                                }
                            }
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in destination country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "destination_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.split("_")[-1]

                            # Store destination city
                            city = text_body
                            if city:
                                update_data(sender, 'destination_city_id', city_id)
                                update_data(sender, 'destination_city', city)

                            if list_msg_id == "list_city_701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif list_msg_id == "list_city_700":
                                
                                # Update state for next step

                                countries, count = get_countries()
                                rows = []
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})
                                text = f"🌍 Dans quel pays allez-vous envoyer le colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "destination_country_selected")

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            text = "📅 Quand souhaitez-vous envoyer votre colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la date",
                                        "sections": [
                                            {
                                                "title": "Date d'envoi",
                                                "rows": [
                                                    {
                                                        "id": "send_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "send_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "send_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "send_date_other",
                                                        "title": "Une date ultérieure"
                                                    },
                                                    {
                                                        "id": "send_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "send_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                },
                            }
                            set_state(sender, "send_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                                
                            print("⚠️ Unexpected message type or list selection in destination city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "send_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("send_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            send_date_option = list_msg_id.replace("send_date_", "")

                            if send_date_option == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif send_date_option == "700":
                                # Update state for next step

                                cities = get_cities_by_country(get_data(sender).get('destination_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})
                                
                                text = f"📍 Dans quelle ville allez-vous envoyer le colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la ville",
                                            "sections": [
                                                {
                                                    "title": "Villes",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }

                                set_state(sender, "destination_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            # Store send date
                            update_data(sender, 'send_date', text_body)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = f"📦 Quel est le type d'envoi ?"

                            # List of shipping types - you can replace with actual types from your database
                            shipping_types = [
                                {"id": "shipping_type_documents", "title": "Documents"},
                                {"id": "shipping_type_petit_colis", "title": "Petit colis"},
                                {"id": "shipping_type_moyen_colis", "title": "Moyen colis"},
                                {"id": "shipping_type_grand_colis", "title": "Grand colis"},
                                {"id": "shipping_type_mixte", "title": "Mixte petit/moyen colis"},
                                {"id": "shipping_type_mixte_tous", "title": "Mixte tous types colis"},
                                {"id": "shipping_type_700", "title": "Menu précédent"},
                                {"id": "shipping_type_701", "title": "Menu principal"}
                            ]

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "button": "Choix type colis ?",
                                        "sections": [
                                            {
                                                "title": "Types d'envoi",
                                                "rows": shipping_types
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "shipping_type_selected")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in send date selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "shipping_type_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("shipping_type_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            shipping_type_id = list_msg_id.replace("shipping_type_", "")

                            if shipping_type_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif shipping_type_id == "700":
                                # Update state for next step

                                text = f"📅 Quand souhaitez-vous envoyer votre colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la date",
                                            "sections": [
                                                {
                                                    "title": "Date d'envoi",
                                                    "rows": [
                                                        {
                                                            "id": "send_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "send_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "send_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "send_date_other",
                                                            "title": "Une date ultérieure"
                                                        },
                                                        {
                                                            "id": "send_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "send_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "send_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200


                            # Store shipping type
                            update_data(sender, 'shipping_type', text_body)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            # Build and send summary
                            text = build_summary(sender)
                            ## You can build a nice summary of the collected info here to show to the user before confirming the request
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                            
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            
                            set_state(sender, "request_confirmation")
                            
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in shipping type selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "request_confirmation":
                        if msg_type == "interactive_button_reply" and button_msg_id in ["parcel_req_Oui", "parcel_req_700", "parcel_req_701"]:
                            # resetting error count on valid selection
                            clear_error_count(sender)


                            if button_msg_id == "parcel_req_701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_msg_id == "parcel_req_700":
                                # Update state for next step

                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = f"📦 Quel est le type d'envoi ?"

                                # List of shipping types - you can replace with actual types from your database
                                shipping_types = [
                                    {"id": "shipping_type_documents", "title": "Documents"},
                                    {"id": "shipping_type_petit_colis", "title": "Petit colis"},
                                    {"id": "shipping_type_moyen_colis", "title": "Moyen colis"},
                                    {"id": "shipping_type_grand_colis", "title": "Grand colis"},
                                    {"id": "shipping_type_mixte", "title": "Mixte petit/moyen colis"},
                                    {"id": "shipping_type_mixte_tous", "title": "Mixte tous types colis"},
                                    {"id": "shipping_type_700", "title": "Menu précédent"},
                                    {"id": "shipping_type_701", "title": "Menu principal"}
                                ]

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {
                                            "text": text.strip()
                                        },
                                        "action": {
                                            "button": "Choix type colis ?",
                                            "sections": [
                                                {
                                                    "title": "Types d'envoi",
                                                    "rows": shipping_types
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "shipping_type_selected")

                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200

                            elif button_msg_id == "parcel_req_Oui":

                                # Create Parcel event
                                payload = {"from_country_id": get_data(sender).get('departure_country_id'),
                                           "to_country_id": get_data(sender).get('destination_country_id'),
                                           "from_city_id": get_data(sender).get('departure_city_id'),
                                           "to_city_id": get_data(sender).get('destination_city_id'),
                                           "travel_period": get_data(sender).get('send_date'),
                                           "shipment_type": get_data(sender).get('shipping_type')}

                                new_parcel_event, message = create_parcel_event_chatbot(sender, payload)
                                if not new_parcel_event:
                                    
                                    if message == "pending_event_exists":
                                        text = "⚠️ Vous avez déjà une demande en cours de traitement. Veuillez patienter ou créer une nouvelle demande ultérieurement."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        clear_data(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Oups, une erreur est survenue lors de la création de votre demande. Veuillez réessayer ultérieurement."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        clear_data(sender)
                                        return "ok", 200

                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un GP disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                # Here you would typically save the confirmed request to your database and/or trigger the next steps of your flow
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)
                                clear_data(sender)
                                return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            return "ok", 200
                    
                    ########################### Parcel Request Flow Steps ###########################
                    #######################################  ENDS HERE #####################################


                    ##########################################################################################
                    ########################### Get Ride to Airport Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_to_airport_data(sender, 'departure_country_id', country_id)
                                update_to_airport_data(sender, 'departure_country', country)
                            
                            
                            airports = get_airports_by_country(get_to_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for a in airports:
                                rows.append({
                                    "id": f"list_airport_{a['id']}",
                                    "title": a['name']
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                            print(f"Available airports for country_id {country_id}:", rows)

                            text = "✈️ Quel est l'aéroport de départ ?"

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                        "sections": [
                                            {
                                                "title": "and",
                                                "rows": rows
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "departure_airport_selected")

                            # clear_state(sender)

                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "departure_airport_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_airport_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            airport_id = list_msg_id.replace("list_airport_", "")
                            if airport_id == "700":
                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                                rows = []
                                countries = get_countries_with_airports()
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})


                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "to_airport_country_selected")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif airport_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure airport
                            airport = text_body
                            if airport:
                                update_to_airport_data(sender, 'departure_airport_id', airport_id)
                                update_to_airport_data(sender, 'departure_airport', airport)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = "📍 D’où partez-vous ?"

                            cities = get_cities_by_country(get_to_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Ville de départ",
                                        "sections": [
                                            {
                                                "title": "Ville de départ",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                            
                            # clear_state(sender) 
                            set_state(sender, "to_airport_departure_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in airport selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "700":
                                airports = get_airports_by_country(get_to_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for a in airports:
                                    rows.append({
                                        "id": f"list_airport_{a['id']}",
                                        "title": a['name']
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                                print(f"Available airports for country_id {country_id}:", rows)

                                text = "✈️ Quel est l'aéroport de départ ?"

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                            "sections": [
                                                {
                                                    "title": "and",
                                                    "rows": rows
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "departure_airport_selected")

                                # clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # Store departure city
                            city = text_body
                            if city:
                                update_to_airport_data(sender, 'departure_city_id', city_id)
                                update_to_airport_data(sender, 'departure_city', city)

                            

                            text = "📅 Quand souhaitez-vous partir ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Date de départ",
                                        "sections": [
                                            {
                                                "title": "Date de départ",
                                                "rows": [
                                                    {
                                                        "id": "dep_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "dep_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "dep_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "dep_date_other",
                                                        "title": "Autre période"
                                                    },
                                                    {
                                                        "id": "dep_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "dep_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)  
                            set_state(sender, "to_airport_departure_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_departure_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("dep_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            dep_date_id = list_msg_id.replace("dep_date_", "")

                            if dep_date_id == "700":
                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = "📍 D’où partez-vous ?"

                                cities = get_cities_by_country(get_to_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Ville de départ",
                                            "sections": [
                                                {
                                                    "title": "Ville de départ",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                
                                # clear_state(sender) 
                                set_state(sender, "to_airport_departure_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif dep_date_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure date preference
                            dep_date_pref = text_body
                            if dep_date_pref:
                                update_to_airport_data(sender, 'departure_date_preference', dep_date_pref)

                            
                            
                            text = "👥 Quel est le nombre de voyageurs ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nombre de voyageurs",
                                        "sections": [
                                            {
                                                "title": "Nombre de voyageurs",
                                                "rows": [
                                                    {
                                                        "id": "num_travelers_1",
                                                        "title": "1️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_travelers_3",
                                                        "title": "2️⃣ 3 ou 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_4",
                                                        "title": "Plus de 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_travelers_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_travelers_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in departure date selection step.")
                            return "ok", 200                        

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_travelers_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_travelers_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_travelers_id = list_msg_id.replace("num_travelers_", "")

                            if num_travelers_id == "700":
                                text = "📅 Quand souhaitez-vous partir ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Date de départ",
                                            "sections": [
                                                {
                                                    "title": "Date de départ",
                                                    "rows": [
                                                        {
                                                            "id": "dep_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "dep_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "dep_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "dep_date_other",
                                                            "title": "Autre période"
                                                        },
                                                        {
                                                            "id": "dep_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "dep_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)  
                                set_state(sender, "to_airport_departure_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_travelers_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of travelers preference
                            num_travelers_pref = text_body
                            if num_travelers_pref:
                                update_to_airport_data(sender, 'num_travelers_preference', num_travelers_pref)
                            
                            # Here you would typically
                            text = "🧳 Combien de petites valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb petites valises",
                                        "sections": [
                                            {
                                                "title": "Nb petites valises",
                                                "rows": [
                                                    {
                                                        "id": "num_small_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_small_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_small_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_small_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_small_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of travelers selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_small_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_small_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_small_cases_id = list_msg_id.replace("num_small_cases_", "")

                            if num_small_cases_id == "700":
                                text = "👥 Quel est le nombre de voyageurs ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "NB de voyageurs",
                                            "sections": [
                                                {
                                                    "title": "NB de voyageurs",
                                                    "rows": [
                                                        {
                                                            "id": "num_travelers_1",
                                                            "title": "1️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_travelers_3",
                                                            "title": "2️⃣ 3 ou 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_4",
                                                            "title": "Plus de 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_travelers_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_travelers_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_small_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of small cases preference
                            num_small_cases_pref = text_body
                            if num_small_cases_pref:
                                update_to_airport_data(sender, 'num_small_cases_preference', num_small_cases_pref)

                            
                            
                            # Here you would
                            text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb valises moyennes",
                                        "sections": [
                                            {
                                                "title": "Nb valises moyennes",
                                                "rows": [
                                                    {
                                                        "id": "num_medium_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_medium_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_medium_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_medium_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_medium_cases_id = list_msg_id.replace("num_medium_cases_", "")

                            if num_medium_cases_id == "700":
                                text = "🧳 Combien de petites valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb petites valises",
                                            "sections": [
                                                {
                                                    "title": "Nb petites valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_small_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_small_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_small_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_small_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_small_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_medium_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of medium cases preference
                            num_medium_cases_pref = text_body
                            if num_medium_cases_pref:
                                update_to_airport_data(sender, 'num_medium_cases_preference', num_medium_cases_pref)

                            # Here you
                            text = "🧳 Combien de grandes valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb grandes valises",
                                        "sections": [
                                            {
                                                "title": "Nb grandes valises",
                                                "rows": [
                                                    {
                                                        "id": "num_big_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_big_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_big_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_big_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_big_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_big_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_big_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_big_cases_id = list_msg_id.replace("num_big_cases_", "")

                            if num_big_cases_id == "700":
                                text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb valises moyennes",
                                            "sections": [
                                                {
                                                    "title": "Nb valises moyennes",
                                                    "rows": [
                                                        {
                                                            "id": "num_medium_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_medium_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_big_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")
                                # Send main menu message
                                professional_send_welcome_msg(sender, headers, url)
                                return "ok", 200
                            
                            # Store number of big cases preference
                            num_big_cases_pref = text_body
                            if num_big_cases_pref:
                                update_to_airport_data(sender, 'num_big_cases_preference', num_big_cases_pref)

                            # Here you would
                            text = build_to_airport_summary(sender)
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_summary")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of big cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_summary":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("to_air_req_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            button_id = button_msg_id.replace("to_air_req_", "")

                            if button_id == "700":
                                # User wants to go back to previous menu (number of big cases)
                                text = "🧳 Combien de grandes valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb grandes valises",
                                            "sections": [
                                                {
                                                    "title": "Nb grandes valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_big_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_big_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_big_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_big_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_big_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_to_airport_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_id == "Oui":

                                # Create Driver Pickup event in database with collected data
                                payload = {
                                    "from_country_id": get_to_airport_data(sender).get('departure_country_id'),
                                    "from_airport_id": get_to_airport_data(sender).get('departure_airport_id'),
                                    "from_city_id": get_to_airport_data(sender).get('departure_city_id'),
                                    "travel_period": get_to_airport_data(sender).get('departure_date_preference'),
                                    "num_of_people": get_to_airport_data(sender).get('num_travelers_preference'),
                                    "num_of_small_cases": get_to_airport_data(sender).get('num_small_cases_preference'),
                                    "num_of_med_cases": get_to_airport_data(sender).get('num_medium_cases_preference'),
                                    "num_of_large_cases": get_to_airport_data(sender).get('num_big_cases_preference')
                                }
                                pickup_creation , message = create_pickup_event_chatbot(sender, payload, "Ride to Airport")

                                if not pickup_creation:
                                    if message == "event_already_exists":
                                        text = "⚠️ Vous avez déjà une demande de transport en cours pour ce trajet. Nous vous invitons à patienter le temps que nous trouvions un transporteur correspondant à votre demande ou à créer une nouvelle demande pour un autre trajet."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Une erreur est survenue lors de la création de votre demande. Veuillez réessayer dans quelques instants."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200

                                # Here you would typically trigger the actual service request based on collected data
                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un Transporteur disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                clear_state(sender)
                                clear_to_airport_data(sender)
                                # set_state(sender, "to_airport_request_submitted")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            else:
                                send_error_message(sender, headers, url)
                                increment_error_count(sender)
                                if get_error_count_exceeds_3(sender):
                                    clear_all(sender)
                                    clear_error_count(sender)
                                    print("⚠️ Too many errors. Resetting conversation.")
                                print("⚠️ Unexpected button selection in summary step.")
                                return "ok", 200
                    
                    ########################### Get Ride to Airport Flow Steps ###########################
                    #######################################  ENDS HERE ###################################


                    ##########################################################################################
                    ########################### Get Ride from Airport Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_from_airport_data(sender, 'departure_country_id', country_id)
                                update_from_airport_data(sender, 'departure_country', country)

                            airports = get_airports_by_country(get_from_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for a in airports:
                                rows.append({
                                    "id": f"list_airport_{a['id']}",
                                    "title": a['name']
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                            print(f"Available airports for country_id {country_id}:", rows)

                            text = "✈️ Quel est l’aéroport d’arrivée ?"

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                        "sections": [
                                            {
                                                "title": "and",
                                                "rows": rows
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "departure_from_airport_selected")

                            # clear_state(sender)

                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "departure_from_airport_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_airport_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            airport_id = list_msg_id.replace("list_airport_", "")
                            if airport_id == "700":
                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                                rows = []
                                countries = get_countries_with_airports()
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})


                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "from_airport_country_selected")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif airport_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure airport
                            airport = text_body
                            if airport:
                                update_from_airport_data(sender, 'departure_airport_id', airport_id)
                                update_from_airport_data(sender, 'departure_airport', airport)

                            

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = "📍 Dans quelle ville souhaitez-vous aller ?"

                            cities = get_cities_by_country(get_from_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Ville de départ",
                                        "sections": [
                                            {
                                                "title": "Ville de départ",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                            
                            # clear_state(sender) 
                            set_state(sender, "from_airport_departure_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in airport selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "from_airport_departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "700":
                                airports = get_airports_by_country(get_from_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for a in airports:
                                    rows.append({
                                        "id": f"list_airport_{a['id']}",
                                        "title": a['name']
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                                print(f"Available airports for country_id {country_id}:", rows)

                                text = "✈️ Quel est l’aéroport d’arrivée ?"

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                            "sections": [
                                                {
                                                    "title": "and",
                                                    "rows": rows
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "departure_from_airport_selected")

                                # clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # Store departure city
                            city = text_body
                            if city:
                                update_from_airport_data(sender, 'departure_city_id', city_id)
                                update_from_airport_data(sender, 'departure_city', city)

                            

                            text = "📅 Quand arrivez-vous ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Date de départ",
                                        "sections": [
                                            {
                                                "title": "Date de départ",
                                                "rows": [
                                                    {
                                                        "id": "dep_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "dep_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "dep_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "dep_date_other",
                                                        "title": "Autre période"
                                                    },
                                                    {
                                                        "id": "dep_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "dep_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)  
                            set_state(sender, "from_airport_departure_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200
                
                    # ✅✅✅
                    elif get_state(sender) == "from_airport_departure_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("dep_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            dep_date_id = list_msg_id.replace("dep_date_", "")

                            if dep_date_id == "700":
                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = "📍 Dans quelle ville souhaitez-vous aller ?"

                                cities = get_cities_by_country(get_from_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Ville de départ",
                                            "sections": [
                                                {
                                                    "title": "Ville de départ",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                
                                # clear_state(sender) 
                                set_state(sender, "from_airport_departure_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif dep_date_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure date preference
                            dep_date_pref = text_body
                            if dep_date_pref:
                                update_from_airport_data(sender, 'departure_date_preference', dep_date_pref)

                            
                            
                            text = "👥 Quel est le nombre de voyageurs ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nombre de voyageurs",
                                        "sections": [
                                            {
                                                "title": "Nombre de voyageurs",
                                                "rows": [
                                                    {
                                                        "id": "num_travelers_1",
                                                        "title": "1️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_travelers_3",
                                                        "title": "2️⃣ 3 ou 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_4",
                                                        "title": "Plus de 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_travelers_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_travelers_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in departure date selection step.")
                            return "ok", 200 

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_travelers_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_travelers_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_travelers_id = list_msg_id.replace("num_travelers_", "")

                            if num_travelers_id == "700":
                                text = "📅 Quand arrivez-vous ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Date de départ",
                                            "sections": [
                                                {
                                                    "title": "Date de départ",
                                                    "rows": [
                                                        {
                                                            "id": "dep_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "dep_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "dep_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "dep_date_other",
                                                            "title": "Autre période"
                                                        },
                                                        {
                                                            "id": "dep_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "dep_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)  
                                set_state(sender, "from_airport_departure_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            # ✅✅✅
                            elif num_travelers_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of travelers preference
                            num_travelers_pref = text_body
                            if num_travelers_pref:
                                update_from_airport_data(sender, 'num_travelers_preference', num_travelers_pref)


                            # Here you would typically
                            text = "🧳 Combien de petites valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb petites valises",
                                        "sections": [
                                            {
                                                "title": "Nb petites valises",
                                                "rows": [
                                                    {
                                                        "id": "num_small_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_small_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_small_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_small_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_small_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of travelers selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_small_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_small_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_small_cases_id = list_msg_id.replace("num_small_cases_", "")

                            if num_small_cases_id == "700":
                                text = "👥 Quel est le nombre de voyageurs ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "NB de voyageurs",
                                            "sections": [
                                                {
                                                    "title": "NB de voyageurs",
                                                    "rows": [
                                                        {
                                                            "id": "num_travelers_1",
                                                            "title": "1️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_travelers_3",
                                                            "title": "2️⃣ 3 ou 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_4",
                                                            "title": "Plus de 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_travelers_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_travelers_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_small_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of small cases preference
                            num_small_cases_pref = text_body
                            if num_small_cases_pref:
                                update_from_airport_data(sender, 'num_small_cases_preference', num_small_cases_pref)

                            
                            
                            # Here you would
                            text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb valises moyennes",
                                        "sections": [
                                            {
                                                "title": "Nb valises moyennes",
                                                "rows": [
                                                    {
                                                        "id": "num_medium_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_medium_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_medium_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_medium_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_medium_cases_id = list_msg_id.replace("num_medium_cases_", "")

                            if num_medium_cases_id == "700":
                                text = "🧳 Combien de petites valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb petites valises",
                                            "sections": [
                                                {
                                                    "title": "Nb petites valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_small_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_small_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_small_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_small_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_small_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_medium_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
 
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of medium cases preference
                            num_medium_cases_pref = text_body
                            if num_medium_cases_pref:
                                update_from_airport_data(sender, 'num_medium_cases_preference', num_medium_cases_pref)


                            # Here you
                            text = "🧳 Combien de grandes valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb grandes valises",
                                        "sections": [
                                            {
                                                "title": "Nb grandes valises",
                                                "rows": [
                                                    {
                                                        "id": "num_big_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_big_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_big_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_big_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_big_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_big_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_big_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_big_cases_id = list_msg_id.replace("num_big_cases_", "")

                            if num_big_cases_id == "700":
                                text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb valises moyennes",
                                            "sections": [
                                                {
                                                    "title": "Nb valises moyennes",
                                                    "rows": [
                                                        {
                                                            "id": "num_medium_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_medium_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_big_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")
                                # Send main menu message
                                professional_send_welcome_msg(sender, headers, url)
                                return "ok", 200
                            
                            # Store number of big cases preference
                            num_big_cases_pref = text_body
                            if num_big_cases_pref:
                                update_from_airport_data(sender, 'num_big_cases_preference', num_big_cases_pref)

                            
                            
                            # Here you would
                            text = build_from_airport_summary(sender)
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_summary")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of big cases selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_summary":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("from_air_req_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            button_id = button_msg_id.replace("from_air_req_", "")

                            if button_id == "700":
                                # User wants to go back to previous menu (number of big cases)
                                text = "🧳 Combien de grandes valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb grandes valises",
                                            "sections": [
                                                {
                                                    "title": "Nb grandes valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_big_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_big_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_big_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_big_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_big_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")
                                clear_from_airport_data(sender)

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_id == "Oui":
                                # Here you would typically trigger the actual service request based on collected data
                                # Create Driver Pickup event in database with collected data
                                payload = {
                                    "from_country_id": get_to_airport_data(sender).get('departure_country_id'),
                                    "from_airport_id": get_to_airport_data(sender).get('departure_airport_id'),
                                    "from_city_id": get_to_airport_data(sender).get('departure_city_id'),
                                    "travel_period": get_to_airport_data(sender).get('departure_date_preference'),
                                    "num_of_people": get_to_airport_data(sender).get('num_travelers_preference'),
                                    "num_of_small_cases": get_to_airport_data(sender).get('num_small_cases_preference'),
                                    "num_of_med_cases": get_to_airport_data(sender).get('num_medium_cases_preference'),
                                    "num_of_large_cases": get_to_airport_data(sender).get('num_big_cases_preference')
                                }
                                pickup_creation , message = create_pickup_event_chatbot(sender, payload, "Airport Pickup")

                                if not pickup_creation:
                                    if message == "event_already_exists":
                                        text = "⚠️ Vous avez déjà une demande de transport en cours pour ce trajet. Nous vous invitons à patienter le temps que nous trouvions un transporteur correspondant à votre demande ou à créer une nouvelle demande pour un autre trajet."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Une erreur est survenue lors de la création de votre demande. Veuillez réessayer dans quelques instants."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                

                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un Transporteur disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                clear_state(sender)
                                clear_from_airport_data(sender)
                                # set_state(sender, "to_airport_request_submitted")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            else:
                                send_error_message(sender, headers, url)
                                increment_error_count(sender)
                                if get_error_count_exceeds_3(sender):
                                    clear_all(sender)
                                    clear_error_count(sender)
                                    print("⚠️ Too many errors. Resetting conversation.")
                                print("⚠️ Unexpected button selection in summary step.")
                                return "ok", 200
                    
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected button selection in summary step.")
                            return "ok", 200


                    ########################### Get Ride from Airport Flow Steps ###########################
                    #######################################  ENDS HERE ###################################

                    ##########################################################################################
                    ########################### Professional Others Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "pro_others":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("other_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            list_msg_id = list_msg_id.replace("other_", "")

                            if list_msg_id == "700":

                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif list_msg_id == "701":

                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # ✅✅✅
                            elif list_msg_id == "r_cred":
                                
                                # Get remaining credits for professional
                                from db_credits import get_user_credit_balance_chatbot
                                credit_balance = get_user_credit_balance_chatbot(sender)
                                if credit_balance is None:
                                    text = "💳 Impossible de récupérer votre solde de crédits pour le moment."
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": sender,
                                        "type": "text",
                                        "text": {
                                            "body": text.strip()
                                        }
                                    }
                                    
                                    clear_state(sender)

                                    send_whatsapp_message(sender, payload, headers, url)
                                    return "Okay", 200

                                text = f"💳 Il vous reste actuellement {credit_balance} crédits disponibles."

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                # Update state for next step
                                clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "Okay", 200
                            
                            # ✅✅✅
                            elif list_msg_id == "pur_li":
                                text = "🛒 Pour acheter des crédits 💰, cliquez sur le lien 🔗 ci-dessous :\n\n👉 https://jokko-ai.sn/"

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "Okay", 200

                            elif list_msg_id == "contact":

                                # Uploading contact request in the database
                                
                                create_req, message = create_contact_request_chatbot(sender)
                                if not create_req:
                                    if message == "open_request_exists":
                                        text = "Vous avez déjà une demande de contact en cours. Veuillez patienter jusqu'à sa clôture. Merci !"
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        clear_state(sender)

                                        send_whatsapp_message(sender, payload, headers, url)

                                        return "Okay", 200
                                    else:
                                        text = "❌ Une erreur est survenue lors de la création de votre demande de contact. Veuillez réessayer ultérieurement."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        clear_state(sender)

                                        send_whatsapp_message(sender, payload, headers, url)

                                        return "Okay", 200                                


                                text = "📩 Votre demande a bien été prise en compte.\nNotre équipe vous contactera très rapidement sur WhatsApp."

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "Okay", 200
                            
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            
                            print("tghgh5⚠️ Unexpected button selection in summary step.")
                            return "ok", 200

                    
                    ########################### Client Others Flow Steps #################################
                    #######################################  ENDS HERE ###################################
                    else:
                        print("⚠️ Message received in unknown state. Resetting conversation.")
                        clear_all(sender)
                        return "ok", 200

                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

                elif user_role == "driver":
                    if not get_state(sender):
                        # Update state for next step
                        set_state(sender, "service_selected")

                        # Build interactive reply
                        driver_send_welcome_msg(sender, headers, url)

                        # # Send message to WhatsApp (sync httpx client for Flask route)
                        # send_whatsapp_message(sender, payload, headers, url)

                        return "ok", 200
                    
                    elif get_state(sender) == "service_selected":
                        
                        # ✅✅✅
                        if msg_type == "interactive_list_reply" and list_msg_id == "role_driver_1":
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            from utils_db import can_user_perform_action
                            if not can_user_perform_action(sender, "Driver status change"):
                                text = "❌ Désolé, vous n'avez pas assez de crédits pour effectuer cette action. Veuillez acheter des crédits pour continuer :\n\n👉 https://jokko-ai.sn/"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                # Update state for next step
                                clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            routes = get_all_driver_routes_for_a_driver_chatbot(sender)
                            if len(routes) == 0:
                                text = "Aucun itinéraire n'a été créé pour votre profil de chauffeur."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                # Update state for next step
                                clear_state(sender)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n📍 Sur quel trajet souhaitez-vous modifier votre statut ?"

                            rows = []
                            for route in routes:
                                from_city = route['from_city']
                                to_airport = route['to_airport']
                                rows.append({
                                    "id": f"list_route_{route['id']}",
                                    "title": f"{from_city} ↔️ {to_airport}"
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_route_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_route_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le trajet",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "driver_route_select")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_driver_2":
                            set_state(sender, "shipment_country_selected")

                            send_service_selected_role_customer1_msg(sender, headers, url)
                            
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            # send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_driver_3":
                            # resetting error count on valid selection
                            clear_error_count(sender)
                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                            rows = []
                            countries = get_countries_with_airports()
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "to_airport_country_selected")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_driver_4":
                            # resetting error count on valid selection
                            clear_error_count(sender)
                            text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l'aéroport d'arrivée ?"

                            rows = []
                            countries = get_countries_with_airports()
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})


                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                        
                            set_state(sender, "from_airport_country_selected")
                            # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        # ✅✅✅
                        elif msg_type == "interactive_list_reply" and list_msg_id == "role_driver_5":
                            text = "🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\nVeuillez sélectionner le service de votre choix :"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Type de service ?",
                                        "sections": [
                                            {
                                                "title": "Date d'envoi",
                                                "rows": [
                                                    {
                                                        "id": "other_r_cred",
                                                        "title": "Afficher crédits restants"
                                                    },
                                                    {
                                                        "id": "other_pur_li",
                                                        "title": "Acheter des crédits"
                                                    },
                                                    {
                                                        "id": "other_contact",
                                                        "title": "Contact service client"
                                                    },
                                                    {
                                                        "id": "other_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "other_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "pro_others")

                            send_whatsapp_message(sender, payload, headers, url)
                            return "okay", 200


                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    
                    ##########################################################################################
                    ################################### Driver ###############################################
                    ########################### Driver Status Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "driver_route_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_route_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            route_id = list_msg_id.replace("list_route_", "")
                            if route_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")
                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif route_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store selected route into redis
                            route = text_body
            
                            if route:
                                update_gp_routes(sender, 'gp_status_route_id', route_id)
                                update_gp_routes(sender, 'gp_status_route', route)
                            
                            text = "🔄 Quel est votre statut actuel pour ce trajet ?"

                            rows = []
                            # List of GP status options - you can replace with actual statuses from your database
                            gp_status_options = [
                                {"id": "dri_stat_avail", "title": "Disponible"},
                                {"id": "dri_stat_unavail", "title": "Indisponible"},
                                {"id": "dri_stat_700", "title": "Menu précédent"},
                                {"id": "dri_stat_701", "title": "Menu principal"}
                            ]

                            for status in gp_status_options:
                                rows.append({
                                    "id": status["id"],
                                    "title": status["title"]
                                })

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le statut",
                                        "sections": [
                                            {
                                                "title": "Statut du trajet",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "driver_status_select")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in driver status route selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "driver_status_select":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("dri_stat_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            status_id = list_msg_id.replace("dri_stat_", "")

                            if status_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # ✅✅✅
                            elif status_id == "700":
                                from utils_db import can_user_perform_action
                                if not can_user_perform_action(sender, "Driver status change"):
                                    text = "❌ Désolé, vous n'avez pas assez de crédits pour effectuer cette action. Veuillez acheter des crédits pour continuer :\n\n👉 https://jokko-ai.sn/"
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": sender,
                                        "type": "text",
                                        "text": {
                                            "body": text.strip()
                                        }
                                    }

                                    # Update state for next step
                                    clear_state(sender)

                                    send_whatsapp_message(sender, payload, headers, url)
                                    return "ok", 200
        
                                routes = get_all_driver_routes_for_a_driver_chatbot(sender)
                                if len(routes) == 0:
                                    text = "Aucun itinéraire n'a été créé pour votre profil de chauffeur."
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": sender,
                                        "type": "text",
                                        "text": {
                                            "body": text.strip()
                                        }
                                    }

                                    # Update state for next step
                                    clear_state(sender)
                                    send_whatsapp_message(sender, payload, headers, url)
                                    return "ok", 200

                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n📍 Sur quel trajet souhaitez-vous modifier votre statut ?"

                                rows = []
                                for route in routes:
                                    from_city = route['from_city']
                                    to_airport = route['to_airport']
                                    rows.append({
                                        "id": f"list_route_{route['id']}",
                                        "title": f"{from_city} ↔️ {to_airport}"
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_route_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_route_701", "title": "Menu principal"})


                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le trajet",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "driver_route_select")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            # Store selected status into redis
                            status = text_body
                            if status:
                                update_gp_routes(sender, 'gp_status_id', status_id)
                                update_gp_routes(sender, 'gp_status', status)
                            
                            text = build_pb_gp_status_summary(sender)

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "buttons": [
                                            {"type": "reply", "reply": {"id": "dri_stat_oui", "title": "Oui"}},
                                            {"type": "reply", "reply": {"id": "dri_stat_700", "title": "Menu précédent"}},
                                            {"type": "reply", "reply": {"id": "dri_stat_701", "title": "Menu principal"}},
                                        ]
                                    },
                                },
                            }

                            # set state to confirmation step
                            set_state(sender, "driver_status_confirmation")

                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            
                            print("⚠️ Unexpected message type or list selection in GP status selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "driver_status_confirmation":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("dri_stat_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)
                            button_id = button_msg_id.replace("dri_stat_", "")

                            if button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")
                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            

                            elif button_id == "700":
                                # User wants to go back to previous menu
                                text = f"🔄 Quel est votre statut actuel pour ce trajet ?"
                                rows = []
                                # List of driver status options - you can replace with actual statuses from your database
                                driver_status_options = [
                                    {"id": "dri_stat_avail", "title": "Disponible"},
                                    {"id": "dri_stat_unavail", "title": "Indisponible"},
                                    {"id": "dri_stat_700", "title": "Menu précédent"},
                                    {"id": "dri_stat_701", "title": "Menu principal"}
                                ]

                                for status in driver_status_options:
                                    rows.append({
                                        "id": status["id"],
                                        "title": status["title"]
                                    })
                                
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le statut",
                                            "sections": [
                                                {
                                                    "title": "Statut du trajet",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }

                                set_state(sender, "driver_status_select")

                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif button_id == "oui":
                                # Update Status of driver route in the database

                                from db_driver_routes import update_driver_assigned_route_chatbot
                                route_id = get_gp_routes(sender).get('gp_status_route_id')
                                print(f"Updating driver route with id {route_id} for user {sender} with new status {get_gp_routes(sender).get('gp_status')}")
                                update_result, message = update_driver_assigned_route_chatbot(route_id, get_gp_routes(sender).get('gp_status'))

                                if not update_result:
                                    if message == "route_not_found":
                                        text = "❌ Route introuvable. Veuillez réessayer ou contacter le support client si le problème persiste."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        clear_state(sender)

                                        send_whatsapp_message(sender, payload, headers, url)
                                        return "ok", 200

                                    elif message == "deduction_failed":
                                        text = "❌ Désolé, une erreur est survenue lors de la mise à jour de votre statut. Veuillez réessayer ou contacter le support client si le problème persiste."

                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        clear_state(sender)

                                        send_whatsapp_message(sender, payload, headers, url)
                                        return "ok", 200
                                    
                                    elif message == "insufficient_credits":
                                        text = "❌ Désolé, vous n'avez pas assez de crédits pour effectuer cette action. Veuillez acheter des crédits pour continuer :\n\n👉 https://jokko-ai.sn/"
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        clear_state(sender)

                                        send_whatsapp_message(sender, payload, headers, url)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Désolé, une erreur est survenue lors de la mise à jour de votre statut. Veuillez réessayer ou contacter le support client si le problème persiste."

                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        clear_state(sender)

                                        send_whatsapp_message(sender, payload, headers, url)
                                        return "ok", 200

                                text = "📩 Merci, votre demande a bien été prise en compte.\n\n🙏 Merci de nous avoir fait confiance.\nÀ très bientôt pour un nouveau service !"
                                
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)

                                return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            return "ok", 200


                    ########################### Driver Status Flow Steps ###########################
                    #######################################  ENDS HERE #####################################
                            

                    ##########################################################################################
                    ################################### Client ###############################################
                    ########################### Parcel Request Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "shipment_country_selected":
                        # clear_data(sender)  # clearing any previously stored data to avoid conflicts and ensure clean state for new request
                        # clear_state(sender) # clearing state to avoid conflicts and ensure clean state for new request, we will set the correct state at the end of this block based on user selection
                        # return "ok", 200
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                professional_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_data(sender, 'departure_country_id', country_id)
                                update_data(sender, 'departure_country', country)
                            
                            set_state(sender, "departure_city_selected")
                            
                            send_city_selection_msg(sender, headers, url, get_data(sender).get('departure_country_id'))

                            return "ok", 200
                        
                        else:

                            send_whatsapp_message(sender, payload, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif city_id == "700":
                                # Store service type
                                update_data(sender, 'service_type', 'Envoyer un colis')

                                set_state(sender, "shipment_country_selected")

                                driver_send_welcome_msg(sender, headers, url)
                                
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                # send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200


                            # Store departure city
                            city = text_body
                            if city:
                                update_data(sender, 'departure_city_id', city_id)
                                update_data(sender, 'departure_city', city)

                            countries, count = get_countries()
                            rows = []
                            for c in countries:
                                rows.append({
                                    "id": f"list_country_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_country_701", "title": "Menu principal"})
                            text = f"🌍 Dans quel pays allez-vous envoyer le colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir le pays",
                                        "sections": [
                                            {
                                                "title": "Pays",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "destination_country_selected")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "destination_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "700":
                                
                                set_state(sender, "departure_city_selected")
                            
                                send_city_selection_msg(sender, headers, url, get_data(sender).get('departure_country_id'))

                                return "ok", 200

                            # Store destination country
                            country = text_body
                            if country:
                                update_data(sender, 'destination_country_id', country_id)
                                update_data(sender, 'destination_country', country)

                            cities = get_cities_by_country(get_data(sender).get('destination_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})
                            
                            text = f"📍 Dans quelle ville allez-vous envoyer le colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la ville",
                                        "sections": [
                                            {
                                                "title": "Villes",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }

                            set_state(sender, "destination_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "text",
                                "text": {
                                    "body": text.strip()
                                }
                            }
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in destination country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "destination_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.split("_")[-1]

                            # Store destination city
                            city = text_body
                            if city:
                                update_data(sender, 'destination_city_id', city_id)
                                update_data(sender, 'destination_city', city)

                            if list_msg_id == "list_city_701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif list_msg_id == "list_city_700":
                                
                                # Update state for next step

                                countries, count = get_countries()
                                rows = []
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})
                                text = f"🌍 Dans quel pays allez-vous envoyer le colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "destination_country_selected")

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            text = "📅 Quand souhaitez-vous envoyer votre colis / document ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir la date",
                                        "sections": [
                                            {
                                                "title": "Date d'envoi",
                                                "rows": [
                                                    {
                                                        "id": "send_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "send_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "send_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "send_date_other",
                                                        "title": "Une date ultérieure"
                                                    },
                                                    {
                                                        "id": "send_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "send_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                },
                            }
                            set_state(sender, "send_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                                
                            print("⚠️ Unexpected message type or list selection in destination city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "send_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("send_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            send_date_option = list_msg_id.replace("send_date_", "")

                            if send_date_option == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif send_date_option == "700":
                                # Update state for next step

                                cities = get_cities_by_country(get_data(sender).get('destination_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})
                                
                                text = f"📍 Dans quelle ville allez-vous envoyer le colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la ville",
                                            "sections": [
                                                {
                                                    "title": "Villes",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }

                                set_state(sender, "destination_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            # Store send date
                            update_data(sender, 'send_date', text_body)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = f"📦 Quel est le type d'envoi ?"

                            # List of shipping types - you can replace with actual types from your database
                            shipping_types = [
                                {"id": "shipping_type_documents", "title": "Documents"},
                                {"id": "shipping_type_petit_colis", "title": "Petit colis"},
                                {"id": "shipping_type_moyen_colis", "title": "Moyen colis"},
                                {"id": "shipping_type_grand_colis", "title": "Grand colis"},
                                {"id": "shipping_type_mixte", "title": "Mixte petit/moyen colis"},
                                {"id": "shipping_type_mixte_tous", "title": "Mixte tous types colis"},
                                {"id": "shipping_type_700", "title": "Menu précédent"},
                                {"id": "shipping_type_701", "title": "Menu principal"}
                            ]

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "button": "Choix type colis ?",
                                        "sections": [
                                            {
                                                "title": "Types d'envoi",
                                                "rows": shipping_types
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "shipping_type_selected")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in send date selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "shipping_type_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("shipping_type_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            shipping_type_id = list_msg_id.replace("shipping_type_", "")

                            if shipping_type_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif shipping_type_id == "700":
                                # Update state for next step

                                text = f"📅 Quand souhaitez-vous envoyer votre colis / document ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir la date",
                                            "sections": [
                                                {
                                                    "title": "Date d'envoi",
                                                    "rows": [
                                                        {
                                                            "id": "send_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "send_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "send_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "send_date_other",
                                                            "title": "Une date ultérieure"
                                                        },
                                                        {
                                                            "id": "send_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "send_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    },
                                }
                                set_state(sender, "send_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200


                            # Store shipping type
                            update_data(sender, 'shipping_type', text_body)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            # Build and send summary
                            text = build_summary(sender)
                            ## You can build a nice summary of the collected info here to show to the user before confirming the request
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "parcel_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                            
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            
                            set_state(sender, "request_confirmation")
                            
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)

                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            print("⚠️ Unexpected message type or list selection in shipping type selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "request_confirmation":
                        if msg_type == "interactive_button_reply" and button_msg_id in ["parcel_req_Oui", "parcel_req_700", "parcel_req_701"]:
                            # resetting error count on valid selection
                            clear_error_count(sender)


                            if button_msg_id == "parcel_req_701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_msg_id == "parcel_req_700":
                                # Update state for next step

                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = f"📦 Quel est le type d'envoi ?"

                                # List of shipping types - you can replace with actual types from your database
                                shipping_types = [
                                    {"id": "shipping_type_documents", "title": "Documents"},
                                    {"id": "shipping_type_petit_colis", "title": "Petit colis"},
                                    {"id": "shipping_type_moyen_colis", "title": "Moyen colis"},
                                    {"id": "shipping_type_grand_colis", "title": "Grand colis"},
                                    {"id": "shipping_type_mixte", "title": "Mixte petit/moyen colis"},
                                    {"id": "shipping_type_mixte_tous", "title": "Mixte tous types colis"},
                                    {"id": "shipping_type_700", "title": "Menu précédent"},
                                    {"id": "shipping_type_701", "title": "Menu principal"}
                                ]

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {
                                            "text": text.strip()
                                        },
                                        "action": {
                                            "button": "Choix type colis ?",
                                            "sections": [
                                                {
                                                    "title": "Types d'envoi",
                                                    "rows": shipping_types
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "shipping_type_selected")

                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200

                            elif button_msg_id == "parcel_req_Oui":

                                # Create Parcel event
                                payload = {"from_country_id": get_data(sender).get('departure_country_id'),
                                           "to_country_id": get_data(sender).get('destination_country_id'),
                                           "from_city_id": get_data(sender).get('departure_city_id'),
                                           "to_city_id": get_data(sender).get('destination_city_id'),
                                           "travel_period": get_data(sender).get('send_date'),
                                           "shipment_type": get_data(sender).get('shipping_type')}

                                new_parcel_event, message = create_parcel_event_chatbot(sender, payload)
                                if not new_parcel_event:
                                    
                                    if message == "pending_event_exists":
                                        text = "⚠️ Vous avez déjà une demande en cours de traitement. Veuillez patienter ou créer une nouvelle demande ultérieurement."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        clear_data(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Oups, une erreur est survenue lors de la création de votre demande. Veuillez réessayer ultérieurement."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        clear_data(sender)
                                        return "ok", 200

                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un GP disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                # Here you would typically save the confirmed request to your database and/or trigger the next steps of your flow
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                send_whatsapp_message(sender, payload, headers, url)

                                clear_state(sender)
                                clear_data(sender)
                                return "ok", 200
                            
                            else:
                                send_error_message(sender, headers, url)
                                
                                increment_error_count(sender)
                                if get_error_count_exceeds_3(sender):
                                    clear_all(sender)
                                    clear_error_count(sender)
                                    print("⚠️ Too many errors. Resetting conversation.")

                                return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")

                            return "ok", 200
                    
                    ########################### Parcel Request Flow Steps ###########################
                    #######################################  ENDS HERE #####################################


                    ##########################################################################################
                    ########################### Get Ride to Airport Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)
                                clear_data(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_to_airport_data(sender, 'departure_country_id', country_id)
                                update_to_airport_data(sender, 'departure_country', country)
                            
                            
                            airports = get_airports_by_country(get_to_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for a in airports:
                                rows.append({
                                    "id": f"list_airport_{a['id']}",
                                    "title": a['name']
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                            print(f"Available airports for country_id {country_id}:", rows)

                            text = "✈️ Quel est l'aéroport de départ ?"

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                        "sections": [
                                            {
                                                "title": "and",
                                                "rows": rows
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "departure_airport_selected")

                            # clear_state(sender)

                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "departure_airport_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_airport_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            airport_id = list_msg_id.replace("list_airport_", "")
                            if airport_id == "700":
                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                                rows = []
                                countries = get_countries_with_airports()
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})


                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "to_airport_country_selected")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif airport_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure airport
                            airport = text_body
                            if airport:
                                update_to_airport_data(sender, 'departure_airport_id', airport_id)
                                update_to_airport_data(sender, 'departure_airport', airport)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = "📍 D’où partez-vous ?"

                            cities = get_cities_by_country(get_to_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Ville de départ",
                                        "sections": [
                                            {
                                                "title": "Ville de départ",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                            
                            # clear_state(sender) 
                            set_state(sender, "to_airport_departure_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in airport selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "700":
                                airports = get_airports_by_country(get_to_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for a in airports:
                                    rows.append({
                                        "id": f"list_airport_{a['id']}",
                                        "title": a['name']
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                                print(f"Available airports for country_id {country_id}:", rows)

                                text = "✈️ Quel est l'aéroport de départ ?"

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                            "sections": [
                                                {
                                                    "title": "and",
                                                    "rows": rows
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "departure_airport_selected")

                                # clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # Store departure city
                            city = text_body
                            if city:
                                update_to_airport_data(sender, 'departure_city_id', city_id)
                                update_to_airport_data(sender, 'departure_city', city)

                            

                            text = "📅 Quand souhaitez-vous partir ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Date de départ",
                                        "sections": [
                                            {
                                                "title": "Date de départ",
                                                "rows": [
                                                    {
                                                        "id": "dep_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "dep_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "dep_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "dep_date_other",
                                                        "title": "Autre période"
                                                    },
                                                    {
                                                        "id": "dep_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "dep_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)  
                            set_state(sender, "to_airport_departure_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_departure_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("dep_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            dep_date_id = list_msg_id.replace("dep_date_", "")

                            if dep_date_id == "700":
                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = "📍 D’où partez-vous ?"

                                cities = get_cities_by_country(get_to_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Ville de départ",
                                            "sections": [
                                                {
                                                    "title": "Ville de départ",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                
                                # clear_state(sender) 
                                set_state(sender, "to_airport_departure_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif dep_date_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure date preference
                            dep_date_pref = text_body
                            if dep_date_pref:
                                update_to_airport_data(sender, 'departure_date_preference', dep_date_pref)

                            
                            
                            text = "👥 Quel est le nombre de voyageurs ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nombre de voyageurs",
                                        "sections": [
                                            {
                                                "title": "Nombre de voyageurs",
                                                "rows": [
                                                    {
                                                        "id": "num_travelers_1",
                                                        "title": "1️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_travelers_3",
                                                        "title": "2️⃣ 3 ou 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_4",
                                                        "title": "Plus de 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_travelers_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_travelers_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in departure date selection step.")
                            return "ok", 200                        

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_travelers_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_travelers_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_travelers_id = list_msg_id.replace("num_travelers_", "")

                            if num_travelers_id == "700":
                                text = "📅 Quand souhaitez-vous partir ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Date de départ",
                                            "sections": [
                                                {
                                                    "title": "Date de départ",
                                                    "rows": [
                                                        {
                                                            "id": "dep_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "dep_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "dep_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "dep_date_other",
                                                            "title": "Autre période"
                                                        },
                                                        {
                                                            "id": "dep_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "dep_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)  
                                set_state(sender, "to_airport_departure_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_travelers_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of travelers preference
                            num_travelers_pref = text_body
                            if num_travelers_pref:
                                update_to_airport_data(sender, 'num_travelers_preference', num_travelers_pref)
                            
                            # Here you would typically
                            text = "🧳 Combien de petites valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb petites valises",
                                        "sections": [
                                            {
                                                "title": "Nb petites valises",
                                                "rows": [
                                                    {
                                                        "id": "num_small_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_small_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_small_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_small_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_small_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of travelers selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_small_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_small_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_small_cases_id = list_msg_id.replace("num_small_cases_", "")

                            if num_small_cases_id == "700":
                                text = "👥 Quel est le nombre de voyageurs ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "NB de voyageurs",
                                            "sections": [
                                                {
                                                    "title": "NB de voyageurs",
                                                    "rows": [
                                                        {
                                                            "id": "num_travelers_1",
                                                            "title": "1️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_travelers_3",
                                                            "title": "2️⃣ 3 ou 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_4",
                                                            "title": "Plus de 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_travelers_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_travelers_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_small_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of small cases preference
                            num_small_cases_pref = text_body
                            if num_small_cases_pref:
                                update_to_airport_data(sender, 'num_small_cases_preference', num_small_cases_pref)

                            
                            
                            # Here you would
                            text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb valises moyennes",
                                        "sections": [
                                            {
                                                "title": "Nb valises moyennes",
                                                "rows": [
                                                    {
                                                        "id": "num_medium_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_medium_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_medium_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_medium_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_medium_cases_id = list_msg_id.replace("num_medium_cases_", "")

                            if num_medium_cases_id == "700":
                                text = "🧳 Combien de petites valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb petites valises",
                                            "sections": [
                                                {
                                                    "title": "Nb petites valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_small_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_small_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_small_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_small_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_small_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_medium_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of medium cases preference
                            num_medium_cases_pref = text_body
                            if num_medium_cases_pref:
                                update_to_airport_data(sender, 'num_medium_cases_preference', num_medium_cases_pref)

                            # Here you
                            text = "🧳 Combien de grandes valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb grandes valises",
                                        "sections": [
                                            {
                                                "title": "Nb grandes valises",
                                                "rows": [
                                                    {
                                                        "id": "num_big_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_big_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_big_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_big_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_num_big_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_num_big_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_big_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_big_cases_id = list_msg_id.replace("num_big_cases_", "")

                            if num_big_cases_id == "700":
                                text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb valises moyennes",
                                            "sections": [
                                                {
                                                    "title": "Nb valises moyennes",
                                                    "rows": [
                                                        {
                                                            "id": "num_medium_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_medium_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_big_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")
                                # Send main menu message
                                driver_send_welcome_msg(sender, headers, url)
                                return "ok", 200
                            
                            # Store number of big cases preference
                            num_big_cases_pref = text_body
                            if num_big_cases_pref:
                                update_to_airport_data(sender, 'num_big_cases_preference', num_big_cases_pref)

                            # Here you would
                            text = build_to_airport_summary(sender)
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "to_air_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "to_airport_summary")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of big cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "to_airport_summary":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("to_air_req_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            button_id = button_msg_id.replace("to_air_req_", "")

                            if button_id == "700":
                                # User wants to go back to previous menu (number of big cases)
                                text = "🧳 Combien de grandes valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb grandes valises",
                                            "sections": [
                                                {
                                                    "title": "Nb grandes valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_big_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_big_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_big_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_big_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "to_airport_num_big_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_to_airport_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_id == "Oui":

                                # Create Driver Pickup event in database with collected data
                                payload = {
                                    "from_country_id": get_to_airport_data(sender).get('departure_country_id'),
                                    "from_airport_id": get_to_airport_data(sender).get('departure_airport_id'),
                                    "from_city_id": get_to_airport_data(sender).get('departure_city_id'),
                                    "travel_period": get_to_airport_data(sender).get('departure_date_preference'),
                                    "num_of_people": get_to_airport_data(sender).get('num_travelers_preference'),
                                    "num_of_small_cases": get_to_airport_data(sender).get('num_small_cases_preference'),
                                    "num_of_med_cases": get_to_airport_data(sender).get('num_medium_cases_preference'),
                                    "num_of_large_cases": get_to_airport_data(sender).get('num_big_cases_preference')
                                }
                                pickup_creation , message = create_pickup_event_chatbot(sender, payload, "Ride to Airport")

                                if not pickup_creation:
                                    if message == "event_already_exists":
                                        text = "⚠️ Vous avez déjà une demande de transport en cours pour ce trajet. Nous vous invitons à patienter le temps que nous trouvions un transporteur correspondant à votre demande ou à créer une nouvelle demande pour un autre trajet."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Une erreur est survenue lors de la création de votre demande. Veuillez réessayer dans quelques instants."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200

                                # Here you would typically trigger the actual service request based on collected data
                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un Transporteur disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                clear_state(sender)
                                clear_to_airport_data(sender)
                                # set_state(sender, "to_airport_request_submitted")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            else:
                                send_error_message(sender, headers, url)
                                increment_error_count(sender)
                                if get_error_count_exceeds_3(sender):
                                    clear_all(sender)
                                    clear_error_count(sender)
                                    print("⚠️ Too many errors. Resetting conversation.")
                                print("⚠️ Unexpected button selection in summary step.")
                                return "ok", 200
                    
                    ########################### Get Ride to Airport Flow Steps ###########################
                    #######################################  ENDS HERE ###################################


                    ##########################################################################################
                    ########################### Get Ride from Airport Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_country_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            country_id = list_msg_id.replace("list_country_", "")

                            if country_id == "700":
                                # User wants to go back to previous menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif country_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure country
                            country = text_body
                            if country:
                                update_from_airport_data(sender, 'departure_country_id', country_id)
                                update_from_airport_data(sender, 'departure_country', country)

                            airports = get_airports_by_country(get_from_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for a in airports:
                                rows.append({
                                    "id": f"list_airport_{a['id']}",
                                    "title": a['name']
                                })

                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                            print(f"Available airports for country_id {country_id}:", rows)

                            text = "✈️ Quel est l’aéroport d’arrivée ?"

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                        "sections": [
                                            {
                                                "title": "and",
                                                "rows": rows
                                            }
                                        ]
                                    }
                                }
                            }

                            set_state(sender, "departure_from_airport_selected")

                            # clear_state(sender)

                            send_whatsapp_message(sender, payload, headers, url)

                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in country selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "departure_from_airport_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_airport_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            airport_id = list_msg_id.replace("list_airport_", "")
                            if airport_id == "700":
                                text = f"🙏 Super, merci pour votre choix !\nNous allons maintenant vous guider étape par étape pour finaliser votre demande.\n\n🌍 Dans quel pays se trouve l’aéroport ?"

                                rows = []
                                countries = get_countries_with_airports()
                                for c in countries:
                                    rows.append({
                                        "id": f"list_country_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_country_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_country_701", "title": "Menu principal"})


                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir le pays",
                                            "sections": [
                                                {
                                                    "title": "Pays",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                            
                                set_state(sender, "from_airport_country_selected")
                                # clear_state(sender)  # clearing state to reuse same flow functions as for parcel request
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif airport_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure airport
                            airport = text_body
                            if airport:
                                update_from_airport_data(sender, 'departure_airport_id', airport_id)
                                update_from_airport_data(sender, 'departure_airport', airport)

                            # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                            text = "📍 Dans quelle ville souhaitez-vous aller ?"

                            cities = get_cities_by_country(get_from_airport_data(sender).get('departure_country_id'))
                            rows = []
                            for c in cities:
                                rows.append({
                                    "id": f"list_city_{c['id']}",
                                    "title": c['name']
                                })
                            # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                            rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                            rows.append({"id": f"list_city_701", "title": "Menu principal"})

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Ville de départ",
                                        "sections": [
                                            {
                                                "title": "Ville de départ",
                                                "rows": rows
                                            }
                                        ]
                                    },
                                },
                            }
                            
                            # clear_state(sender) 
                            set_state(sender, "from_airport_departure_city_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in airport selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "from_airport_departure_city_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            city_id = list_msg_id.replace("list_city_", "")

                            if city_id == "700":
                                airports = get_airports_by_country(get_from_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for a in airports:
                                    rows.append({
                                        "id": f"list_airport_{a['id']}",
                                        "title": a['name']
                                    })

                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_airport_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_airport_701", "title": "Menu principal"})

                                print(f"Available airports for country_id {country_id}:", rows)

                                text = "✈️ Quel est l’aéroport d’arrivée ?"

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Choisir l'aéroport", #Choisir l'aéroport"
                                            "sections": [
                                                {
                                                    "title": "and",
                                                    "rows": rows
                                                }
                                            ]
                                        }
                                    }
                                }

                                set_state(sender, "departure_from_airport_selected")

                                # clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "ok", 200
                            
                            elif city_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # Store departure city
                            city = text_body
                            if city:
                                update_from_airport_data(sender, 'departure_city_id', city_id)
                                update_from_airport_data(sender, 'departure_city', city)

                            text = "📅 Quand arrivez-vous ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Date de départ",
                                        "sections": [
                                            {
                                                "title": "Date de départ",
                                                "rows": [
                                                    {
                                                        "id": "dep_date_72h",
                                                        "title": "Dans moins de 72 heures"
                                                    },
                                                    {
                                                        "id": "dep_date_this_week",
                                                        "title": "Cette semaine"
                                                    },
                                                    {
                                                        "id": "dep_date_next_week",
                                                        "title": "La semaine prochaine"
                                                    },
                                                    {
                                                        "id": "dep_date_other",
                                                        "title": "Autre période"
                                                    },
                                                    {
                                                        "id": "dep_date_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "dep_date_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)  
                            set_state(sender, "from_airport_departure_date_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in city selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_departure_date_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("dep_date_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            dep_date_id = list_msg_id.replace("dep_date_", "")

                            if dep_date_id == "700":
                                # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                                text = "📍 Dans quelle ville souhaitez-vous aller ?"

                                cities = get_cities_by_country(get_from_airport_data(sender).get('departure_country_id'))
                                rows = []
                                for c in cities:
                                    rows.append({
                                        "id": f"list_city_{c['id']}",
                                        "title": c['name']
                                    })
                                # Adding options to go back to menu or restart flow in case of wrong selection or change of mind
                                rows.append({"id": f"list_city_700", "title": "Menu précédent"})
                                rows.append({"id": f"list_city_701", "title": "Menu principal"})

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Ville de départ",
                                            "sections": [
                                                {
                                                    "title": "Ville de départ",
                                                    "rows": rows
                                                }
                                            ]
                                        },
                                    },
                                }
                                
                                # clear_state(sender) 
                                set_state(sender, "from_airport_departure_city_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif dep_date_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store departure date preference
                            dep_date_pref = text_body
                            if dep_date_pref:
                                update_from_airport_data(sender, 'departure_date_preference', dep_date_pref)

                            
                            
                            text = "👥 Quel est le nombre de voyageurs ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nombre de voyageurs",
                                        "sections": [
                                            {
                                                "title": "Nombre de voyageurs",
                                                "rows": [
                                                    {
                                                        "id": "num_travelers_1",
                                                        "title": "1️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_travelers_3",
                                                        "title": "2️⃣ 3 ou 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_4",
                                                        "title": "Plus de 4"
                                                    },
                                                    {
                                                        "id": "num_travelers_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_travelers_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_travelers_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in departure date selection step.")
                            return "ok", 200 

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_travelers_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_travelers_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_travelers_id = list_msg_id.replace("num_travelers_", "")

                            if num_travelers_id == "700":
                                text = "📅 Quand arrivez-vous ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Date de départ",
                                            "sections": [
                                                {
                                                    "title": "Date de départ",
                                                    "rows": [
                                                        {
                                                            "id": "dep_date_72h",
                                                            "title": "Dans moins de 72 heures"
                                                        },
                                                        {
                                                            "id": "dep_date_this_week",
                                                            "title": "Cette semaine"
                                                        },
                                                        {
                                                            "id": "dep_date_next_week",
                                                            "title": "La semaine prochaine"
                                                        },
                                                        {
                                                            "id": "dep_date_other",
                                                            "title": "Autre période"
                                                        },
                                                        {
                                                            "id": "dep_date_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "dep_date_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)  
                                set_state(sender, "from_airport_departure_date_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_travelers_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)
                                clear_data(sender)
                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of travelers preference
                            num_travelers_pref = text_body
                            if num_travelers_pref:
                                update_from_airport_data(sender, 'num_travelers_preference', num_travelers_pref)


                            # Here you would typically
                            text = "🧳 Combien de petites valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb petites valises",
                                        "sections": [
                                            {
                                                "title": "Nb petites valises",
                                                "rows": [
                                                    {
                                                        "id": "num_small_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_small_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_small_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_small_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_small_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_small_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of travelers selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_small_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_small_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_small_cases_id = list_msg_id.replace("num_small_cases_", "")

                            if num_small_cases_id == "700":
                                text = "👥 Quel est le nombre de voyageurs ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "NB de voyageurs",
                                            "sections": [
                                                {
                                                    "title": "NB de voyageurs",
                                                    "rows": [
                                                        {
                                                            "id": "num_travelers_1",
                                                            "title": "1️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_travelers_3",
                                                            "title": "2️⃣ 3 ou 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_4",
                                                            "title": "Plus de 4"
                                                        },
                                                        {
                                                            "id": "num_travelers_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_travelers_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_travelers_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_small_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of small cases preference
                            num_small_cases_pref = text_body
                            if num_small_cases_pref:
                                update_from_airport_data(sender, 'num_small_cases_preference', num_small_cases_pref)

                            # Here you would
                            text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb valises moyennes",
                                        "sections": [
                                            {
                                                "title": "Nb valises moyennes",
                                                "rows": [
                                                    {
                                                        "id": "num_medium_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_medium_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_medium_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200

                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_medium_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_medium_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_medium_cases_id = list_msg_id.replace("num_medium_cases_", "")

                            if num_medium_cases_id == "700":
                                text = "🧳 Combien de petites valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb petites valises",
                                            "sections": [
                                                {
                                                    "title": "Nb petites valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_small_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_small_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_small_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_small_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_small_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_small_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_medium_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            # Store number of medium cases preference
                            num_medium_cases_pref = text_body
                            if num_medium_cases_pref:
                                update_from_airport_data(sender, 'num_medium_cases_preference', num_medium_cases_pref)

                            # Here you
                            text = "🧳 Combien de grandes valises y a-t-il ?"
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    "action": {
                                        "button": "Nb grandes valises",
                                        "sections": [
                                            {
                                                "title": "Nb grandes valises",
                                                "rows": [
                                                    {
                                                        "id": "num_big_cases_0",
                                                        "title": "1️⃣ Aucune"
                                                    },
                                                    {
                                                        "id": "num_big_cases_1",
                                                        "title": "2️⃣ 1 ou 2"
                                                    },
                                                    {
                                                        "id": "num_big_cases_3",
                                                        "title": "3️⃣ 3 à 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_6",
                                                        "title": "4️⃣ Plus de 5"
                                                    },
                                                    {
                                                        "id": "num_big_cases_700",
                                                        "title": "Menu précédent"
                                                    },
                                                    {
                                                        "id": "num_big_cases_701",
                                                        "title": "Menu principal"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_num_big_cases_selected")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of small cases selection step.")
                            return "ok", 200
                    
                    # ✅✅✅
                    elif get_state(sender) == "from_airport_num_big_cases_selected":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("num_big_cases_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            num_big_cases_id = list_msg_id.replace("num_big_cases_", "")

                            if num_big_cases_id == "700":
                                text = "🧳 Combien de valises de taille moyenne y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb valises moyennes",
                                            "sections": [
                                                {
                                                    "title": "Nb valises moyennes",
                                                    "rows": [
                                                        {
                                                            "id": "num_medium_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_medium_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_medium_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif num_big_cases_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")
                                # Send main menu message
                                driver_send_welcome_msg(sender, headers, url)
                                return "ok", 200
                            
                            # Store number of big cases preference
                            num_big_cases_pref = text_body
                            if num_big_cases_pref:
                                update_from_airport_data(sender, 'num_big_cases_preference', num_big_cases_pref)

                            # Here you would
                            text = build_from_airport_summary(sender)
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "button",
                                    "body": {
                                        "text": text.strip()
                                    },
                                    "action": {
                                        "buttons": [
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_Oui",
                                                    "title": "Oui"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_700",
                                                    "title": "Menu précédent"
                                                }
                                            },
                                            {
                                                "type": "reply",
                                                "reply": {
                                                    "id": "from_air_req_701",
                                                    "title": "Menu principal"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }

                            # clear_state(sender)
                            set_state(sender, "from_airport_summary")
                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            return "ok", 200
                        
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            print("⚠️ Unexpected message type or list selection in number of big cases selection step.")
                            return "ok", 200

                    # ✅✅✅
                    elif get_state(sender) == "from_airport_summary":
                        if msg_type == "interactive_button_reply" and button_msg_id and button_msg_id.startswith("from_air_req_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            button_id = button_msg_id.replace("from_air_req_", "")

                            if button_id == "700":
                                # User wants to go back to previous menu (number of big cases)
                                text = "🧳 Combien de grandes valises y a-t-il ?"
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "body": {"text": text.strip()},
                                        "action": {
                                            "button": "Nb grandes valises",
                                            "sections": [
                                                {
                                                    "title": "Nb grandes valises",
                                                    "rows": [
                                                        {
                                                            "id": "num_big_cases_0",
                                                            "title": "1️⃣ Aucune"
                                                        },
                                                        {
                                                            "id": "num_big_cases_1",
                                                            "title": "2️⃣ 1 ou 2"
                                                        },
                                                        {
                                                            "id": "num_big_cases_3",
                                                            "title": "3️⃣ 3 à 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_6",
                                                            "title": "4️⃣ Plus de 5"
                                                        },
                                                        {
                                                            "id": "num_big_cases_700",
                                                            "title": "Menu précédent"
                                                        },
                                                        {
                                                            "id": "num_big_cases_701",
                                                            "title": "Menu principal"
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                }

                                # clear_state(sender)
                                set_state(sender, "from_airport_num_big_cases_selected")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200

                            elif button_id == "701":
                                # User wants to go back to main menu
                                clear_state(sender)

                                # Update state for next step
                                set_state(sender, "service_selected")
                                clear_from_airport_data(sender)

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200

                            elif button_id == "Oui":
                                # Create Driver Pickup event in database with collected data
                                payload = {
                                    "from_country_id": get_to_airport_data(sender).get('departure_country_id'),
                                    "from_airport_id": get_to_airport_data(sender).get('departure_airport_id'),
                                    "from_city_id": get_to_airport_data(sender).get('departure_city_id'),
                                    "travel_period": get_to_airport_data(sender).get('departure_date_preference'),
                                    "num_of_people": get_to_airport_data(sender).get('num_travelers_preference'),
                                    "num_of_small_cases": get_to_airport_data(sender).get('num_small_cases_preference'),
                                    "num_of_med_cases": get_to_airport_data(sender).get('num_medium_cases_preference'),
                                    "num_of_large_cases": get_to_airport_data(sender).get('num_big_cases_preference')
                                }
                                pickup_creation , message = create_pickup_event_chatbot(sender, payload, "Airport Pickup")

                                if not pickup_creation:
                                    if message == "event_already_exists":
                                        text = "⚠️ Vous avez déjà une demande de transport en cours pour ce trajet. Nous vous invitons à patienter le temps que nous trouvions un transporteur correspondant à votre demande ou à créer une nouvelle demande pour un autre trajet."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                    
                                    else:
                                        text = "❌ Une erreur est survenue lors de la création de votre demande. Veuillez réessayer dans quelques instants."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        # Send message to WhatsApp (sync httpx client for Flask route)
                                        send_whatsapp_message(sender, payload, headers, url)

                                        clear_state(sender)
                                        return "ok", 200
                                # Here you would typically trigger the actual service request based on collected data
                                text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un Transporteur disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }
                                clear_state(sender)
                                clear_from_airport_data(sender)
                                # set_state(sender, "to_airport_request_submitted")
                                # Send message to WhatsApp (sync httpx client for Flask route)
                                send_whatsapp_message(sender, payload, headers, url)
                                return "ok", 200
                            
                            else:
                                send_error_message(sender, headers, url)
                                increment_error_count(sender)
                                if get_error_count_exceeds_3(sender):
                                    clear_all(sender)
                                    clear_error_count(sender)
                                    print("⚠️ Too many errors. Resetting conversation.")
                                print("⚠️ Unexpected button selection in summary step.")
                                return "ok", 200


                    ########################### Get Ride from Airport Flow Steps ###########################
                    #######################################  ENDS HERE ###################################

                    ##########################################################################################
                    ########################### Professional Others Flow Steps ###########################
                    #######################################  STARTS HERE #####################################
                    ##########################################################################################

                    # ✅✅✅
                    elif get_state(sender) == "pro_others":
                        if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("other_"):
                            # resetting error count on valid selection
                            clear_error_count(sender)

                            list_msg_id = list_msg_id.replace("other_", "")

                            if list_msg_id == "700":

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            elif list_msg_id == "701":

                                # Update state for next step
                                set_state(sender, "service_selected")

                                driver_send_welcome_msg(sender, headers, url)

                                return "ok", 200
                            
                            # ✅✅✅
                            elif list_msg_id == "r_cred":
                                
                                # Get remaining credits for professional
                                from db_credits import get_user_credit_balance_chatbot
                                credit_balance = get_user_credit_balance_chatbot(sender)
                                if credit_balance is None:
                                    text = "💳 Impossible de récupérer votre solde de crédits pour le moment."
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": sender,
                                        "type": "text",
                                        "text": {
                                            "body": text.strip()
                                        }
                                    }
                                    
                                    clear_state(sender)

                                    send_whatsapp_message(sender, payload, headers, url)
                                    return "Okay", 200

                                text = f"💳 Il vous reste actuellement {credit_balance} crédits disponibles."

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                # Update state for next step
                                clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "Okay", 200
                            
                            # ✅✅✅
                            elif list_msg_id == "pur_li":
                                text = "🛒 Pour acheter des crédits 💰, cliquez sur le lien 🔗 ci-dessous :\n\n👉 https://jokko-ai.sn/"

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "Okay", 200

                            elif list_msg_id == "contact":

                                # Uploading contact request in the database
                                
                                create_req, message = create_contact_request_chatbot(sender)
                                if not create_req:
                                    if message == "open_request_exists":
                                        text = "Vous avez déjà une demande de contact en cours. Veuillez patienter jusqu'à sa clôture. Merci !"
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        clear_state(sender)

                                        send_whatsapp_message(sender, payload, headers, url)

                                        return "Okay", 200
                                    else:
                                        text = "❌ Une erreur est survenue lors de la création de votre demande de contact. Veuillez réessayer ultérieurement."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": sender,
                                            "type": "text",
                                            "text": {
                                                "body": text.strip()
                                            }
                                        }

                                        clear_state(sender)

                                        send_whatsapp_message(sender, payload, headers, url)

                                        return "Okay", 200                                


                                text = "📩 Votre demande a bien été prise en compte.\nNotre équipe vous contactera très rapidement sur WhatsApp."

                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": sender,
                                    "type": "text",
                                    "text": {
                                        "body": text.strip()
                                    }
                                }

                                clear_state(sender)

                                send_whatsapp_message(sender, payload, headers, url)

                                return "Okay", 200
                            
                        else:
                            send_error_message(sender, headers, url)
                            increment_error_count(sender)
                            if get_error_count_exceeds_3(sender):
                                clear_all(sender)
                                clear_error_count(sender)
                                print("⚠️ Too many errors. Resetting conversation.")
                            
                            print("tghgh5⚠️ Unexpected button selection in summary step.")
                            return "ok", 200

                    
                    ########################### Client Others Flow Steps #################################
                    #######################################  ENDS HERE ###################################
                    else:
                        print("⚠️ Message received in unknown state. Resetting conversation.")
                        clear_all(sender)
                        return "ok", 200



    except httpx.HTTPStatusError as e:
        # Graph API returned non-2xx
        print("❌ WhatsApp API error:", str(e))
        return "ok", 500

    except Exception as e:
        print("❌ Error:", str(e))
        return "ok", 500

