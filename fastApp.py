import os, json, asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from typing import Any, Dict, Optional
from pathlib import Path
from datetime import datetime, timezone, timedelta


from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Query, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
import httpx
import logging
from pydantic import BaseModel

from db_user import create_or_get_user

from tasks import process_webhook  # your Celery task

import redis
import secrets

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

SESSION_COOKIE_NAME = "admin_session"
SESSION_EXPIRE_SECONDS = 60 * 60 * 12  # 12 hours

redis_client: Optional[redis.Redis] = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-bot")

# ==================== ENV / CONFIG ====================

WHATSAPP_PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

VERIFY_TOKEN = "6984125oO!?"  # keep exactly as your Flask code

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


app = FastAPI()

# Mount static (optional, but common in FastAPI template apps)
STATIC_DIR.mkdir(exist_ok=True)


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Optional: shared async client (only if you need it later)
http_client: httpx.AsyncClient | None = None

class UpdateUserRolePayload(BaseModel):
    wp_number: str
    new_role: str

class CountryPayload(BaseModel):
    name: str


class CityPayload(BaseModel):
    name: str
    country_id: int


class AirportPayload(BaseModel):
    name: str
    country_id: int


class GpRoutePayload(BaseModel):
    from_city_id: int
    to_city_id: int


class DriverRoutePayload(BaseModel):
    from_city_id: int
    to_airport_id: int

class CreditAllowancePayload(BaseModel):
    credits_allowance_value: int


class CreditDeductionPayload(BaseModel):
    actions: str
    credits_deduction_value: int

class ClientCreditBalancePayload(BaseModel):
    user_id: int
    credits_balance: int

class AvailableDriverRoutePayload(BaseModel):
    from_city_id: int
    to_airport_id: int


class AssignedDriverRoutePayload(BaseModel):
    driver_user_id: int
    available_route_id: int
    status: str


class ProfessionalRoutePayload(BaseModel):
    professional_user_id: int
    from_country_id: int
    to_country_id: int
    from_city_id: int
    to_city_id: int
    travel_period: str
    shipment_type: str
    status: str

class ContactRequestCreatePayload(BaseModel):
    user_id: int


class ContactRequestStatusPayload(BaseModel):
    status: str

class ParcelEventCreatePayload(BaseModel):
    created_by_user_id: int
    from_country_id: int
    to_country_id: int
    from_city_id: int
    to_city_id: int
    travel_period: str
    shipment_type: str
    event_status: str = "waiting"


class ParcelEventStatusPayload(BaseModel):
    event_status: str

class PickupEventCreatePayload(BaseModel):
    created_by_user_id: int
    context: str
    from_country_id: int
    from_airport_id: int
    from_city_id: int
    travel_period: str | None = None
    num_of_people: str | None = None
    num_of_small_cases: str | None = None
    num_of_med_cases: str | None = None
    num_of_large_cases: str | None = None
    event_status: str = "waiting"


class PickupEventStatusPayload(BaseModel):
    event_status: str

class RegistrationRequestActionPayload(BaseModel):
    action: str

class RegistrationRequestCreatePayload(BaseModel):
    user_id: int
    requested_role: str

@app.on_event("startup")
async def startup():
    global http_client, redis_client
    http_client = httpx.AsyncClient(timeout=30)

    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )

    try:
        redis_client.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.error("❌ Redis connection failed: %s", str(e))
        raise

    logger.info("✅ FastAPI startup complete")


@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()
        logger.info("🛑 http_client closed")


# ==================== HELPERS ====================

def is_inbound_message_event(data: dict) -> bool:
    """
    Same logic as your Flask version:
    if payload has 'statuses' under entry[0].changes[0].value -> not inbound message
    """
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    if "statuses" in value:
        return False
    return True


def utcnow():
    return datetime.now(timezone.utc)


def build_session_key(session_id: str) -> str:
    return f"admin_session:{session_id}"


def create_admin_session(admin):
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized")

    session_id = secrets.token_urlsafe(32)
    session_key = build_session_key(session_id)

    session_data = {
        "admin_id": str(admin.id),
        "email": admin.email,
        "firstName": admin.firstName or "",
        "lastName": admin.lastName or "",
        "created_at": utcnow().isoformat()
    }

    redis_client.hset(session_key, mapping=session_data)
    redis_client.expire(session_key, SESSION_EXPIRE_SECONDS)

    return session_id


def get_admin_session(request: Request):
    if redis_client is None:
        return None

    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None

    session_key = build_session_key(session_id)
    session_data = redis_client.hgetall(session_key)

    if not session_data:
        return None

    redis_client.expire(session_key, SESSION_EXPIRE_SECONDS)
    return {
        "session_id": session_id,
        **session_data
    }


def destroy_admin_session(request: Request):
    if redis_client is None:
        return

    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return

    session_key = build_session_key(session_id)
    redis_client.delete(session_key)


def require_admin_session(request: Request):
    session = get_admin_session(request)
    if not session:
        return None
    return session


# ==================== ROUTES ====================


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    session = get_admin_session(request)
    if session:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": None
        }
    )


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    from db_admins import login_admin

    admin = login_admin(email=email.strip(), password=password)

    if not admin:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid email or password."
            },
            status_code=401
        )

    session_id = create_admin_session(admin)

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_EXPIRE_SECONDS,
        httponly=True,
        secure=False,      # set True if using HTTPS
        samesite="lax"
    )
    return response


@app.get("/logout")
async def logout(request: Request):
    destroy_admin_session(request)

    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request, "admin_session": session})

@app.get("/users", response_class=HTMLResponse)
async def users(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_user import get_all_users
    from db_credits import get_user_credit_balance

    users = get_all_users()
    result = []

    for user in users:
        user_credit_balance = get_user_credit_balance(user_id=user["id"])
        result.append({
            "id": user["id"],
            "wp_profile_name": user["wp_profile_name"],
            "wp_number": user["wp_number"],
            "user_type": user["user_type"],
            "joined_at": user["joined_at"].strftime("%B %d, %Y %I:%M %p") if user["joined_at"] else "-",
            "updated_at": user["updated_at"].strftime("%B %d, %Y %I:%M %p") if user["updated_at"] else "-",
            "credit_balance": user_credit_balance
        })

    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": result,
            "admin_session": session,
        }
    )


@app.get("/entities", response_class=HTMLResponse)
async def entities(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import get_countries, get_cities, get_airports

    countries, total_country = get_countries()
    cities, total_cities = get_cities()
    airports, total_airports = get_airports()

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
        }
    }

    return templates.TemplateResponse(
        "entities.html",
        {
            "request": request,
            "result": result,
            "country_options": countries,
            "admin_session": session,
        }
    )



@app.get("/credits", response_class=HTMLResponse)
async def credits_page(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_credits_deduction import (
        get_credit_allowance,
        get_all_credit_deductions,
        ensure_default_credit_deductions
    )
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_user import get_all_users
    from db_credits import get_user_credit_balance_record

    ensure_default_credit_deductions()

    credit_allowance = get_credit_allowance()
    credit_deductions = get_all_credit_deductions() or []

    users = get_all_users()
    user_credit_balances = []

    for user in users:
        credit_record = get_user_credit_balance_record(user["id"])

        user_credit_balances.append({
            "user_id": user["id"],
            "wp_number": user["wp_number"],
            "user_type": user["user_type"],
            "credits_balance": credit_record.credits_balance if credit_record else 0,
            "updated_at": credit_record.updated_at if credit_record else None
        })

    return templates.TemplateResponse(
        "credits.html",
        {
            "request": request,
            "credit_allowance": credit_allowance,
            "credit_deductions": credit_deductions,
            "user_credit_balances": user_credit_balances,
            "admin_session": session
        }
    )


@app.get("/driver-routes", response_class=HTMLResponse)
async def driver_routes_page(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_available_driver_routes import get_all_available_driver_routes
    from db_driver_routes import get_all_assigned_driver_routes
    from location_manage import get_cities, get_airports
    from db_user import get_all_users

    available_driver_routes, total_available_driver_routes = get_all_available_driver_routes()
    assigned_driver_routes, total_assigned_driver_routes = get_all_assigned_driver_routes()
    cities, _ = get_cities()
    airports, _ = get_airports()

    users = get_all_users()
    driver_options = [user for user in users if user["user_type"] == "driver"]

    return templates.TemplateResponse(
        "driver_routes.html",
        {
            "request": request,
            "available_driver_routes": {
                "total": total_available_driver_routes,
                "data": available_driver_routes
            },
            "assigned_driver_routes": {
                "total": total_assigned_driver_routes,
                "data": assigned_driver_routes
            },
            "city_options": cities,
            "airport_options": airports,
            "driver_options": driver_options,
            "admin_session": session
        }
    )


@app.get("/professional-routes", response_class=HTMLResponse)
async def professional_routes_page(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_gp_routes import get_all_professional_routes
    from db_user import get_all_users
    from location_manage import get_countries, get_cities

    professional_routes, total_professional_routes = get_all_professional_routes()
    users = get_all_users()
    professional_options = [user for user in users if user["user_type"] == "professional"]
    countries, _ = get_countries()
    cities, _ = get_cities()

    return templates.TemplateResponse(
        "professional_routes.html",
        {
            "request": request,
            "professional_routes": {
                "total": total_professional_routes,
                "data": professional_routes
            },
            "professional_options": professional_options,
            "country_options": countries,
            "city_options": cities,
            "admin_session": session

        }
    )


@app.get("/parcel-events", response_class=HTMLResponse)
async def parcel_events_page(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_parcel_events import get_all_parcel_events
    from db_user import get_all_users
    from location_manage import get_countries, get_cities

    parcel_events, total_parcel_events = get_all_parcel_events()
    users = get_all_users()
    countries, _ = get_countries()
    cities, _ = get_cities()

    return templates.TemplateResponse(
        "parcel_events.html",
        {
            "request": request,
            "parcel_events": {
                "total": total_parcel_events,
                "data": parcel_events
            },
            "user_options": users,
            "country_options": countries,
            "city_options": cities,
            "admin_session": session
        }
    )


@app.get("/contact-requests", response_class=HTMLResponse)
async def contact_requests_page(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_contact_req import get_all_contact_requests
    from db_user import get_all_users

    contact_requests, total_contact_requests = get_all_contact_requests()
    users = get_all_users()

    return templates.TemplateResponse(
        "contact_request.html",
        {
            "request": request,
            "contact_requests": {
                "total": total_contact_requests,
                "data": contact_requests
            },
            "user_options": users,
            "admin_session": session

        }
    )

@app.get("/registration-requests", response_class=HTMLResponse)
async def registration_requests_page(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_reg_request import get_all_registration_requests, get_registration_request_stats
    from db_user import get_all_users

    registration_requests, total_registration_requests = get_all_registration_requests()
    stats = get_registration_request_stats()
    users = get_all_users()

    return templates.TemplateResponse(
        "registration_req.html",
        {
            "request": request,
            "registration_requests": {
                "total": total_registration_requests,
                "data": registration_requests
            },
            "stats": stats,
            "user_options": users,
            "admin_session": session

        }
    )


@app.get("/pickup-events", response_class=HTMLResponse)
async def pickup_events_page(request: Request):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_pickup_events import get_all_pickup_events
    from db_user import get_all_users
    from location_manage import get_countries_with_airports

    pickup_events, total_pickup_events = get_all_pickup_events()
    users = get_all_users()
    country_options = get_countries_with_airports()

    return templates.TemplateResponse(
        "pickup_events.html",
        {
            "request": request,
            "pickup_events": {
                "total": total_pickup_events,
                "data": pickup_events
            },
            "user_options": users,
            "country_options": country_options,
            "admin_session": session

        }
    )


@app.post("/api/credits/allowance")
async def create_or_update_credit_allowance_api(request: Request, payload: CreditAllowancePayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_credits_deduction import create_or_update_credit_allowance

    try:
        if payload.credits_allowance_value < 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Allowance cannot be negative."}
            )

        ok = create_or_update_credit_allowance(payload.credits_allowance_value)

        if ok:
            return {
                "success": True,
                "message": "Credit allowance updated successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to update credit allowance."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.post("/api/credits/deduction")
async def create_or_update_credit_deduction_api(request: Request, payload: CreditDeductionPayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_credits_deduction import create_or_update_credit_deduction

    try:
        allowed_actions = {
            "GP Publish tour",
            "GP status change",
            "Driver status change",
            "GP accept parcel request",
            "GP reject parcel request",
            "GP ignore parcel request",
            "Driver accept Pickup request",
            "Driver reject Pickup request",
            "Driver ignore Pickup request",
        }

        if payload.actions not in allowed_actions:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid action selected."}
            )

        if payload.credits_deduction_value < 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Deduction value cannot be negative."}
            )

        ok = create_or_update_credit_deduction(
            action=payload.actions,
            deduction_value=payload.credits_deduction_value
        )

        if ok:
            return {
                "success": True,
                "message": "Credit deduction updated successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to update credit deduction."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.post("/api/credits/client-balance")
async def update_client_credit_balance_api(payload: ClientCreditBalancePayload):
    from db_credits import set_user_credit_balance

    try:
        if payload.credits_balance < 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Credit balance cannot be negative."}
            )

        ok = set_user_credit_balance(
            user_id=payload.user_id,
            new_balance=payload.credits_balance
        )

        if ok:
            return {
                "success": True,
                "message": "Client credit balance updated successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to update client credit balance."}
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.post("/api/users/change-role")
async def change_user_role_api(request: Request, payload: UpdateUserRolePayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from db_user import set_user_role

    try:
        wp_number = (payload.wp_number or "").strip()
        new_role = (payload.new_role or "").strip().lower()

        if not wp_number:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "WhatsApp number is required."}
            )

        if new_role not in {"client", "professional", "driver"}:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid role selected."}
            )

        updated = set_user_role(wp_number, new_role)

        if updated:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "User role updated successfully."}
            )

        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "User not found or role not updated."}
        )

    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e)}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.post("/api/entities/countries")
async def create_country_api(request: Request, payload: CountryPayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import create_country
    country = create_country(payload.name.strip())
    if country:
        return {"success": True, "message": "Country created successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to create country."})


@app.put("/api/entities/countries/{country_id}")
async def update_country_api(request: Request, country_id: int, payload: CountryPayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import update_country
    country = update_country(country_id=country_id, new_name=payload.name.strip())
    if country:
        return {"success": True, "message": "Country updated successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to update country."})


@app.delete("/api/entities/countries/{country_id}")
async def delete_country_api(request: Request, country_id: int):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import delete_country
    ok = delete_country(country_id=country_id)
    if ok:
        return {"success": True, "message": "Country deleted successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to delete country."})


@app.post("/api/entities/cities")
async def create_city_api(request: Request, payload: CityPayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import create_city
    city = create_city(name=payload.name.strip(), country_id=payload.country_id)
    if city:
        return {"success": True, "message": "City created successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to create city."})


@app.put("/api/entities/cities/{city_id}")
async def update_city_api(request: Request, city_id: int, payload: CityPayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import update_city
    city = update_city(city_id=city_id, new_name=payload.name.strip(), new_country_id=payload.country_id)
    if city:
        return {"success": True, "message": "City updated successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to update city."})


@app.delete("/api/entities/cities/{city_id}")
async def delete_city_api(request: Request, city_id: int):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import delete_city
    ok = delete_city(city_id=city_id)
    if ok:
        return {"success": True, "message": "City deleted successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to delete city."})


@app.post("/api/entities/airports")
async def create_airport_api(request: Request, payload: AirportPayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import create_airport
    airport = create_airport(name=payload.name.strip(), country_id=payload.country_id)
    if airport:
        return {"success": True, "message": "Airport created successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to create airport."})


@app.put("/api/entities/airports/{airport_id}")
async def update_airport_api(request: Request, airport_id: int, payload: AirportPayload):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import update_airport
    airport = update_airport(airport_id=airport_id, new_name=payload.name.strip(), new_country_id=payload.country_id)
    if airport:
        return {"success": True, "message": "Airport updated successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to update airport."})


@app.delete("/api/entities/airports/{airport_id}")
async def delete_airport_api(request: Request, airport_id: int):
    session = require_admin_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)
    from location_manage import delete_airport
    ok = delete_airport(airport_id=airport_id)
    if ok:
        return {"success": True, "message": "Airport deleted successfully."}
    return JSONResponse(status_code=400, content={"success": False, "message": "Failed to delete airport."})


@app.post("/api/available-driver-routes")
async def create_available_driver_route_api(payload: AvailableDriverRoutePayload):
    from db_available_driver_routes import create_available_driver_route

    try:
        route = create_available_driver_route(
            from_city_id=payload.from_city_id,
            to_airport_id=payload.to_airport_id
        )

        if route:
            return {
                "success": True,
                "message": "Available driver route created successfully."
            }

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Failed to create available driver route."
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Server error: {str(e)}"
            }
        )


@app.put("/api/available-driver-routes/{route_id}")
async def update_available_driver_route_api(route_id: int, payload: AvailableDriverRoutePayload):
    from db_available_driver_routes import update_available_driver_route

    try:
        route = update_available_driver_route(
            route_id=route_id,
            new_from_city_id=payload.from_city_id,
            new_to_airport_id=payload.to_airport_id
        )

        if route:
            return {
                "success": True,
                "message": "Available driver route updated successfully."
            }

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Failed to update available driver route."
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Server error: {str(e)}"
            }
        )


@app.delete("/api/available-driver-routes/{route_id}")
async def delete_available_driver_route_api(route_id: int):
    from db_available_driver_routes import delete_available_driver_route

    try:
        ok = delete_available_driver_route(route_id=route_id)

        if ok:
            return {
                "success": True,
                "message": "Available driver route deleted successfully."
            }

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Failed to delete available driver route."
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Server error: {str(e)}"
            }
        )

@app.post("/api/driver-assigned-routes")
async def create_driver_assigned_route_api(payload: AssignedDriverRoutePayload):
    from db_driver_routes import create_driver_route

    try:
        if payload.status not in ["Active", "Deactive"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid status selected."}
            )

        route = create_driver_route(
            driver_user_id=payload.driver_user_id,
            available_route_id=payload.available_route_id
        )

        if not route:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Failed to assign route to driver."}
            )

        if route.status != payload.status:
            route.status = payload.status
            route.save()

        return {
            "success": True,
            "message": "Driver route assigned successfully."
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.put("/api/driver-assigned-routes/{route_id}")
async def update_driver_assigned_route_api(route_id: int, payload: AssignedDriverRoutePayload):
    from db_driver_routes import update_driver_assigned_route

    try:
        route = update_driver_assigned_route(
            route_id=route_id,
            driver_user_id=payload.driver_user_id,
            available_route_id=payload.available_route_id,
            status=payload.status
        )

        if route:
            return {
                "success": True,
                "message": "Assigned driver route updated successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to update assigned driver route."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.delete("/api/driver-assigned-routes/{route_id}")
async def delete_driver_assigned_route_api(route_id: int):
    from db_driver_routes import delete_driver_assigned_route

    try:
        ok = delete_driver_assigned_route(route_id)

        if ok:
            return {
                "success": True,
                "message": "Assigned driver route deleted successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to delete assigned driver route."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.post("/api/professional-routes")
async def create_professional_route_api(payload: ProfessionalRoutePayload):
    from db_gp_routes import create_route_for_professional

    try:
        route_data = {
            "from_country_id": payload.from_country_id,
            "to_country_id": payload.to_country_id,
            "from_city_id": payload.from_city_id,
            "to_city_id": payload.to_city_id,
            "travel_period": payload.travel_period,
            "shipment_type": payload.shipment_type
        }

        route = create_route_for_professional(
            professional_user_id=payload.professional_user_id,
            route_data=route_data
        )

        if not route:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Failed to create professional route."}
            )

        if route.status != payload.status:
            route.status = payload.status
            route.save()

        return {
            "success": True,
            "message": "Professional route created successfully."
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.put("/api/professional-routes/{route_id}")
async def update_professional_route_api(route_id: int, payload: ProfessionalRoutePayload):
    from db_gp_routes import update_professional_route

    try:
        route_data = {
            "from_country_id": payload.from_country_id,
            "to_country_id": payload.to_country_id,
            "from_city_id": payload.from_city_id,
            "to_city_id": payload.to_city_id,
            "travel_period": payload.travel_period,
            "shipment_type": payload.shipment_type,
            "status": payload.status
        }

        route = update_professional_route(
            route_id=route_id,
            professional_user_id=payload.professional_user_id,
            route_data=route_data
        )

        if route:
            return {
                "success": True,
                "message": "Professional route updated successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to update professional route."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.delete("/api/professional-routes/{route_id}")
async def delete_professional_route_api(route_id: int):
    from db_gp_routes import delete_professional_route

    try:
        ok = delete_professional_route(route_id)

        if ok:
            return {
                "success": True,
                "message": "Professional route deleted successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to delete professional route."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.post("/api/contact-requests")
async def create_contact_request_api(payload: ContactRequestCreatePayload):
    from db_contact_req import create_contact_request

    try:
        contact_request, result_code = create_contact_request(payload.user_id)

        if result_code == "okay":
            return {
                "success": True,
                "message": "Contact request created successfully."
            }

        if result_code == "user_not_found":
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "User not found."}
            )

        if result_code == "open_request_exists":
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "This user already has an open contact request."}
            )

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to create contact request."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.put("/api/contact-requests/{request_id}/status")
async def update_contact_request_status_api(request_id: int, payload: ContactRequestStatusPayload):
    from db_contact_req import update_contact_request_status

    try:
        contact_request, result_code = update_contact_request_status(
            request_id=request_id,
            new_status=payload.status
        )

        if result_code == "okay":
            return {
                "success": True,
                "message": "Contact request status updated successfully."
            }

        if result_code == "invalid_status":
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid status selected."}
            )

        if result_code == "not_found":
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Contact request not found."}
            )

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to update contact request status."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.post("/api/parcel-events")
async def create_parcel_event_api(payload: ParcelEventCreatePayload):
    from db_parcel_events import create_parcel_event

    try:
        event = create_parcel_event({
            "created_by_user_id": payload.created_by_user_id,
            "from_country_id": payload.from_country_id,
            "to_country_id": payload.to_country_id,
            "from_city_id": payload.from_city_id,
            "to_city_id": payload.to_city_id,
            "travel_period": payload.travel_period,
            "shipment_type": payload.shipment_type,
            "event_status": payload.event_status
        })

        if event:
            return {
                "success": True,
                "message": "Parcel event created successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to create parcel event."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.put("/api/parcel-events/{event_id}/status")
async def update_parcel_event_status_api(event_id: int, payload: ParcelEventStatusPayload):
    from db_parcel_events import update_parcel_event_status

    try:
        event, result_code = update_parcel_event_status(
            event_id=event_id,
            new_status=payload.event_status
        )

        if result_code == "okay":
            return {
                "success": True,
                "message": "Parcel event status updated successfully."
            }

        if result_code == "invalid_status":
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid event status selected."}
            )

        if result_code == "not_found":
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Parcel event not found."}
            )

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to update parcel event status."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.delete("/api/parcel-events/{event_id}")
async def delete_parcel_event_api(event_id: int):
    from db_parcel_events import delete_parcel_event

    try:
        ok = delete_parcel_event(event_id)

        if ok:
            return {
                "success": True,
                "message": "Parcel event deleted successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to delete parcel event."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.get("/api/location/countries-with-airports")
async def countries_with_airports_api():
    from location_manage import get_countries_with_airports

    try:
        countries = get_countries_with_airports()
        return {
            "success": True,
            "data": [
                {"id": country.id, "name": country.name}
                for country in countries
            ]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.get("/api/location/airports-by-country/{country_id}")
async def airports_by_country_api(country_id: int):
    from location_manage import get_airports_by_country

    try:
        airports = get_airports_by_country(country_id=country_id)
        return {
            "success": True,
            "data": [
                {"id": airport.id, "name": airport.name}
                for airport in airports
            ]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.get("/api/location/cities-by-country/{country_id}")
async def cities_by_country_api(country_id: int):
    from location_manage import get_cities_by_country

    try:
        cities = get_cities_by_country(country_id=country_id)
        return {
            "success": True,
            "data": [
                {"id": city.id, "name": city.name}
                for city in cities
            ]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.post("/api/pickup-events")
async def create_pickup_event_api(payload: PickupEventCreatePayload):
    from db_pickup_events import create_pickup_event

    try:
        event = create_pickup_event({
            "created_by_user_id": payload.created_by_user_id,
            "context": payload.context,
            "from_country_id": payload.from_country_id,
            "from_airport_id": payload.from_airport_id,
            "from_city_id": payload.from_city_id,
            "travel_period": payload.travel_period,
            "num_of_people": payload.num_of_people,
            "num_of_small_cases": payload.num_of_small_cases,
            "num_of_med_cases": payload.num_of_med_cases,
            "num_of_large_cases": payload.num_of_large_cases,
            "event_status": payload.event_status
        })

        if event:
            return {
                "success": True,
                "message": "Pickup event created successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to create pickup event."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.put("/api/pickup-events/{event_id}/status")
async def update_pickup_event_status_api(event_id: int, payload: PickupEventStatusPayload):
    from db_pickup_events import update_pickup_event_status

    try:
        event, result_code = update_pickup_event_status(
            event_id=event_id,
            new_status=payload.event_status
        )

        if result_code == "okay":
            return {
                "success": True,
                "message": "Pickup event status updated successfully."
            }

        if result_code == "invalid_status":
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid event status selected."}
            )

        if result_code == "not_found":
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Pickup event not found."}
            )

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to update pickup event status."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.delete("/api/pickup-events/{event_id}")
async def delete_pickup_event_api(event_id: int):
    from db_pickup_events import delete_pickup_event

    try:
        ok = delete_pickup_event(event_id)

        if ok:
            return {
                "success": True,
                "message": "Pickup event deleted successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to delete pickup event."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )

@app.post("/api/pickup-events")
async def create_pickup_event_api(payload: PickupEventCreatePayload):
    from db_pickup_events import create_pickup_event

    try:
        event = create_pickup_event({
            "created_by_user_id": payload.created_by_user_id,
            "context": payload.context,
            "from_country_id": payload.from_country_id,
            "from_airport_id": payload.from_airport_id,
            "from_city_id": payload.from_city_id,
            "travel_period": payload.travel_period,
            "num_of_people": payload.num_of_people,
            "num_of_small_cases": payload.num_of_small_cases,
            "num_of_med_cases": payload.num_of_med_cases,
            "num_of_large_cases": payload.num_of_large_cases,
            "event_status": payload.event_status
        })

        if event:
            return {
                "success": True,
                "message": "Pickup event created successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to create pickup event."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse("privacy_policy.html", {"request": request})


@app.post("/api/registration-requests")
async def create_registration_request_api(payload: RegistrationRequestCreatePayload):
    from db_reg_request import create_registration_request

    try:
        registration_request, result_code = create_registration_request(
            user_id=payload.user_id,
            requested_role=payload.requested_role
        )

        if result_code == "created":
            return {
                "success": True,
                "message": "Registration request created successfully."
            }

        if result_code == "invalid_role":
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid requested role."}
            )

        if result_code == "user_not_found":
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "User not found."}
            )

        if result_code == "pending_exists":
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "A pending request for this role already exists for this user."}
            )

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to create registration request."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.put("/api/registration-requests/{request_id}/approve")
async def approve_registration_request_api(request_id: int):
    from db_reg_request import approve_registration_request

    try:
        ok, result_code = approve_registration_request(request_id)

        if ok and result_code == "approved":
            return {
                "success": True,
                "message": "Registration request approved successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to approve registration request."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.put("/api/registration-requests/{request_id}/reject")
async def reject_registration_request_api(request_id: int):
    from db_reg_request import reject_registration_request

    try:
        ok, result_code = reject_registration_request(request_id)

        if ok and result_code == "rejected":
            return {
                "success": True,
                "message": "Registration request rejected successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to reject registration request."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )


@app.delete("/api/registration-requests/{request_id}")
async def delete_registration_request_api(request_id: int):
    from db_reg_request import delete_registration_request

    try:
        ok = delete_registration_request(request_id)

        if ok:
            return {
                "success": True,
                "message": "Registration request deleted successfully."
            }

        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to delete registration request."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Server error: {str(e)}"}
        )







@app.get("/terms-of-service", response_class=HTMLResponse)
async def terms_of_service(request: Request):
    return templates.TemplateResponse("terms_of_service.html", {"request": request})


@app.get("/get_or_create_user/{sender}/{profile_name}")
async def get_or_create_user(sender: str, profile_name: str):
    user = create_or_get_user(sender, profile_name)

    if user is None:
        return {"user": None}

    return {
        "user": {
            "id": user.id,
            "wp_profile_name": user.wp_profile_name,
            "wp_number": user.wp_number,
            "user_type": user.user_type,
            "joined_at": user.joined_at.isoformat() if user.joined_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
    }


@app.get("/webhookone")
async def verify(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
):
    logger.info(
        "VERIFY hit mode=%s token_received=%s token_expected=%s",
        mode,
        repr(token),
        repr(VERIFY_TOKEN),
    )

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(content=challenge or "", status_code=200)

    return PlainTextResponse(content="Forbidden", status_code=403)


@app.post("/webhookone")
async def receive(request: Request):
    logger.info("POST /webhookone hit. headers=%s", dict(request.headers))

    try:
        data: Dict[str, Any] = await request.json()
    except Exception:
        data = {}

    # print(data)

    try:
        if not is_inbound_message_event(data):
            logger.info("Not a valid message event (likely statuses).")
            return PlainTextResponse(content="ok", status_code=200)

        # Keep your Celery async processing
        process_webhook.delay(data)

        return PlainTextResponse(content="okay", status_code=200)

    except Exception as e:
        logger.exception("Error processing webhook: %s", str(e))
        return PlainTextResponse(content="okay", status_code=500)



# ==================== LOCAL RUN ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastApp:app", host="0.0.0.0", port=8000, reload=True)

