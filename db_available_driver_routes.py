from mongoengine import *
from datetime import datetime, timezone
from db_airport import Airport
from db_city import City
# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)


class AvailableDriverRoutes(Document):
    id = SequenceField(primary_key = True)
    from_city_id = IntField(required=True)
    to_airport_id = IntField(required=True)
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())


    meta = {
        'indexes': [
            'from_city_id',  # Index for faster queries by from_city_id
            'to_airport_id',  # Index for faster queries by to_airport_id
        ]
    }

    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)

def create_available_driver_route(from_city_id, to_airport_id):

    # First check if all data have been given
    if not from_city_id or not to_airport_id:
        print(f"All necessary data should be given")
        return False

    # Check if a route with the same from_city_id and to_airport_id already exists
    existing_route = AvailableDriverRoutes.objects(from_city_id=from_city_id, to_airport_id=to_airport_id).first()
    if existing_route:
        print(f"Route already exists for from_city_id {from_city_id} and to_airport_id {to_airport_id}")
        return existing_route  # Optionally return the existing route instead of creating a new one

    # then check if city and airport exist in their respective collections
    from_city = City.objects(id=from_city_id).first()
    to_airport = Airport.objects(id=to_airport_id).first()
    if not from_city:
        print(f"City with id {from_city_id} not found.")
        return False
    if not to_airport:
        print(f"Airport with id {to_airport_id} not found.")
        return False

    new_route = AvailableDriverRoutes(
        from_city_id=from_city_id,
        to_airport_id=to_airport_id
    )
    new_route.save()
    return new_route

def get_all_available_driver_routes():
    # Return with City and airport names
    try:
        routes = AvailableDriverRoutes.objects()
        if routes.count() < 1:
            print("No available driver routes found")
            return [], 0

        route_list = []
        for route in routes:
            from_city = City.objects(id=route.from_city_id).first()
            to_airport = Airport.objects(id=route.to_airport_id).first()
            route_list.append({
                "id": route.id,
                "from_city_id": route.from_city_id,
                "to_airport_id": route.to_airport_id,
                "from_city": from_city.name if from_city else "Unknown",
                "to_airport": to_airport.name if to_airport else "Unknown",
                "created_at": route.created_at,
                "updated_at": route.updated_at
            })

        return route_list, len(route_list)

    except Exception as e:
        print(f"Error retrieving available driver routes: {e}")
        return [], 0

# Update a route's from_city_id and to_airport_id by its id
def update_available_driver_route(route_id, new_from_city_id, new_to_airport_id):
    try:
        route = AvailableDriverRoutes.objects(id=route_id).first()
        if not route:
            print(f"Route with id {route_id} not found.")
            return False
        
        # Check if the new city and airport exist
        from_city = City.objects(id=new_from_city_id).first()
        to_airport = Airport.objects(id=new_to_airport_id).first()
        if not from_city:
            print(f"City with id {new_from_city_id} not found.")
            return False
        if not to_airport:
            print(f"Airport with id {new_to_airport_id} not found.")
            return False
        
        # Update the route's from_city_id and to_airport_id
        route.from_city_id = new_from_city_id
        route.to_airport_id = new_to_airport_id
        route.save()
        print(f"Route with id {route_id} updated successfully.")
        return route
    except Exception as e:
        print(f"Error updating route with id {route_id}: {e}")
        return False

# Delete a route by its id
def delete_available_driver_route(route_id):
    try:
        route = AvailableDriverRoutes.objects(id=route_id).first()
        if not route:
            print(f"Route with id {route_id} not found.")
            return False
        
        route.delete()
        print(f"Route with id {route_id} deleted successfully.")
        return True
    except Exception as e:
        print(f"Error deleting route with id {route_id}: {e}")
        return False