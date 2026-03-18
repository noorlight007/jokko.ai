from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from datetime import datetime, timedelta
import os, json
from dotenv import load_dotenv
load_dotenv()
from typing import Any, Dict, Optional, Tuple
import httpx
import logging
logging.basicConfig(level=logging.INFO)

from tasks import process_webhook

app = Flask(__name__)
app.config['secret_key'] = '5800d5d9e4405020d527f0587538abbe'


WHATSAPP_PHONE_NUMBER_ID=os.getenv("PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
VERIFY_TOKEN = "6984125oO!?"


# ==================== FLASK ROUTES ====================

@app.get("/")
def test():
    return render_template("index.html")

@app.get("/users")
def users():
    from db_user import get_all_users
    users = get_all_users()
    result = []
    for user in users:
        # print(f"User ID: {user.id}, WP Profile Name: {user.wp_profile_name}, WP Number: {user.wp_number}, User Type: {user.user_type}")
        user_credit_balance = None
        from db_credits import get_user_credit_balance
        user_credit_balance = get_user_credit_balance(user_id=user['id'])
        result.append({
            "id": user['id'],
            "wp_profile_name": user['wp_profile_name'],
            "wp_number": user['wp_number'],
            "user_type": user['user_type'],
            "credit_balance": user_credit_balance
        })

    return render_template("users.html", users=result)


@app.get("/entities")
def entities():
    # Here we will show Countries, Cities, Airports, GP routes and Driver routes in accordions
    from location_manage import get_countries, get_cities, get_airports, fetch_all_gp_routes
    from db_driver_routes import get_all_driver_routes

    # Countries
    countries, total_country = get_countries()

    # Cities
    cities, total_cities = get_cities()

    # airports
    airports, total_airports = get_airports()

    # GP routes
    gp_routes, total_gp_routes = fetch_all_gp_routes()

    # Driver routes
    driver_routes, total_driver_routes = get_all_driver_routes()

    result = {
        "countries": {
            "total": total_country,
            "data": countries
        },
        "cities": {
            "total": total_cities,
            "data": cities
        },
        "airports": {
            "total": total_airports,
            "data": airports
        },
        "gp_routes": {
            "total": total_gp_routes,
            "data": gp_routes
        },
        "driver_routes": {
            "total": total_driver_routes,
            "data": driver_routes
        }
    }

    return render_template("entities.html", result=result)


@app.get("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")

@app.get("/terms-of-service")
def terms_of_service():
    return render_template("terms_of_service.html")

def is_inbound_message_event(data: dict) -> bool:
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    if 'statuses' in value:
        return False
    return True

@app.get("/webhookone")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    app.logger.info("VERIFY hit mode=%s token_ok=%s", mode, token == VERIFY_TOKEN)
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Forbidden", 403


@app.post("/webhookone")
def receive():
    app.logger.info("POST /webhookone hit. headers=%s", dict(request.headers))
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    print(data)

    try:
        

        if not is_inbound_message_event(data):
            app.logger.info("Not a valid message", dict(request.headers))
            return "ok", 200
        process_webhook.delay(data)  # Process the webhook asynchronously with Celery
        return "okay", 200
    except Exception as e:
        print(str(e))
        return "okay", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)