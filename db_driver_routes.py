from mongoengine import *
from datetime import datetime, timezone
from db_airport import Airport
from db_city import City
from db_user import User
from db_available_driver_routes import AvailableDriverRoutes
# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)


class DriverRoutes(Document):
    id = SequenceField(primary_key = True)
    driver = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    route = ReferenceField(AvailableDriverRoutes, required=True, reverse_delete_rule=CASCADE)
    status = StringField(choices=["Active", "Deactive"], default="Active")
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())
    
    meta = {
        'indexes': [
            'route',  # Index for faster queries by route
        ]
    }


    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)


def create_driver_route(driver_user_id, available_route_id):

    # First check if all data have been given
    if not driver_user_id or not available_route_id:
        print(f"All necessary data should be given")
        return False

    # Then check if there exist any user with this id, and it's user_type = driver
    driver = User.objects(id=driver_user_id, user_type="driver").first()

    if not driver:
        print(f"Driver with user_id {driver_user_id} not found.")
        return False

    # Check if the available route exists
    available_route = AvailableDriverRoutes.objects(id=available_route_id).first()
    if not available_route:
        print(f"Available route with id {available_route_id} not found.")
        return False
    
    
    # Check if a route with the same from_city_id and to_airport_id already exists
    existing_route = DriverRoutes.objects(driver = driver, route=available_route).first()
    if existing_route:
        print(f"Route already exists for Driver user id #{driver_user_id}")
        return existing_route  # Optionally return the existing route instead of creating a new one

    # If both city and airport exist, create the new route
    new_route = DriverRoutes(driver = driver, route=available_route)
    new_route.save()
    print("New route created successfully.")
    return new_route

def get_all_driver_routes_for_a_driver(driver_user_id):
    # Return with City and airport names
    try:
        drivers = User.objects(id = driver_user_id, user_type = "driver")
        if drivers.count() < 1:
            print("No driver founds")
            return [], 0
        
        
        result = []
        for driver in drivers:
            driver_routes = DriverRoutes.objects(driver=driver)
            for route in driver_routes:
                available_route = route.route
                from_city = City.objects(id=available_route.from_city_id).first()
                to_airport = Airport.objects(id=available_route.to_airport_id).first()
                result.append({
                    "id": route.id,
                    "from_city": from_city.name if from_city else "Unknown",
                    "to_airport": to_airport.name if to_airport else "Unknown",
                    "status": route.status,
                    "created_at": route.created_at,
                    "updated_at": route.updated_at
                })
        return result, len(result)
    except Exception as e:
        print(f"❌ Error fetching driver routes: {e}")
        return [], 0


def get_all_assigned_driver_routes():
    try:
        driver_routes = DriverRoutes.objects().order_by('-updated_at')

        result = []
        for item in driver_routes:
            driver = item.driver
            available_route = item.route

            from_city = City.objects(id=available_route.from_city_id).first() if available_route else None
            to_airport = Airport.objects(id=available_route.to_airport_id).first() if available_route else None

            result.append({
                "id": item.id,
                "driver_user_id": driver.id if driver else None,
                "driver_wp_number": driver.wp_number if driver else "Unknown",
                "available_route_id": available_route.id if available_route else None,
                "from_city": from_city.name if from_city else "Unknown",
                "to_airport": to_airport.name if to_airport else "Unknown",
                "status": item.status,
                "updated_at": item.updated_at
            })

        return result, len(result)
    except Exception as e:
        print(f"❌ Error fetching all assigned driver routes: {e}")
        return [], 0


def update_driver_assigned_route(route_id, driver_user_id, available_route_id, status):
    try:
        driver_route = DriverRoutes.objects(id=route_id).first()
        if not driver_route:
            print(f"Driver route with id {route_id} not found.")
            return False

        driver = User.objects(id=driver_user_id, user_type="driver").first()
        if not driver:
            print(f"Driver with id {driver_user_id} not found.")
            return False

        available_route = AvailableDriverRoutes.objects(id=available_route_id).first()
        if not available_route:
            print(f"Available route with id {available_route_id} not found.")
            return False

        if status not in ["Active", "Deactive"]:
            print(f"Invalid status: {status}")
            return False

        existing = DriverRoutes.objects(
            id__ne=route_id,
            driver=driver,
            route=available_route
        ).first()
        if existing:
            print("This assigned route already exists for this driver.")
            return False

        driver_route.driver = driver
        driver_route.route = available_route
        driver_route.status = status
        driver_route.save()

        return driver_route
    except Exception as e:
        print(f"❌ Error updating assigned driver route: {e}")
        return False


def delete_driver_assigned_route(route_id):
    try:
        driver_route = DriverRoutes.objects(id=route_id).first()
        if not driver_route:
            print(f"Driver route with id {route_id} not found.")
            return False

        driver_route.delete()
        return True
    except Exception as e:
        print(f"❌ Error deleting assigned driver route: {e}")
        return False


## Chatbot functions
def get_all_driver_routes_for_a_driver_chatbot(whatsapp):
    # Return with City and airport names
    try:
        drivers = User.objects(wp_number=whatsapp, user_type="driver")
        if drivers.count() < 1:
            print("No driver founds")
            return []
        
        
        result = []
        for driver in drivers:
            driver_routes = DriverRoutes.objects(driver=driver)
            for route in driver_routes:
                available_route = route.route
                from_city = City.objects(id=available_route.from_city_id).first()
                to_airport = Airport.objects(id=available_route.to_airport_id).first()
                result.append({
                    "id": route.id,
                    "from_city": from_city.name if from_city else "Unknown",
                    "to_airport": to_airport.name if to_airport else "Unknown",
                    "status": route.status,
                    "created_at": route.created_at,
                    "updated_at": route.updated_at
                })
        return result
    except Exception as e:
        print(f"❌ Error fetching driver routes: {e}")
        return []



def update_driver_assigned_route_chatbot(route_id, status):
    try:
        driver_route = DriverRoutes.objects(id=route_id).first()
        if not driver_route:
            print(f"Driver route with id {route_id} not found.")
            return False, "route_not_found"

        available_route = AvailableDriverRoutes.objects(id=driver_route.route.id).first()
        if not available_route:
            print(f"Available route with id {driver_route.route.id} not found.")
            return False, "route_not_found"
        
        if status not in ["Disponible", "Indisponible"]:
            print(f"Invalid status: {status}")
            return False, "deduction_failed"
        
        if driver_route.status == status:
            print(f"Route status is already '{status}'. No update needed.")
            return driver_route, "no_update_needed"
        
        # Check if the user has enough credits to change the status if they are trying to set it to "Disponible"
        from utils_db import deduct_credits_for_action
        deduction_result, message = deduct_credits_for_action(driver_route.driver.wp_number, "Driver status change")
        if not deduction_result:
            if message == "insufficient_credits":
                print(f"User with WhatsApp number '{driver_route.driver.wp_number}' does not have enough credits to change route status to 'Disponible'.")
                return False, "insufficient_credits"
            else:
                print(f"Failed to deduct credits for user with WhatsApp number '{driver_route.driver.wp_number}' when changing route status.")
                return False, "deduction_failed"

        if status == "Disponible":
            status = "Active"
        else:
            status = "Deactive"

        driver_route.status = status
        driver_route.save()

        return driver_route, "update_successful"
    except Exception as e:
        print(f"❌ Error updating assigned driver route: {e}")
        return False, "deduction_failed"