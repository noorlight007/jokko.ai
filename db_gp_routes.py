from mongoengine import *
from datetime import datetime, timezone
from db_city import City
from db_country import Country
from db_user import User

# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)


class GpRoutes(Document):
    id = SequenceField(primary_key = True)
    professional = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    from_country_id = IntField(required=True)
    to_country_id = IntField(required=True)
    from_city_id = IntField(required=True)
    to_city_id = IntField(required=True)
    travel_period = StringField(choices=["Dans moins de 72 heures", "Cette semaine", "La semaine prochaine", "Une date ultérieure"], required=True)
    shipment_type = StringField(choices=["Documents", "Petit colis", "Moyen colis", "Grand colis", "Mixte petit/moyen colis", "Mixte tous types colis", ], required=True)
    status = StringField(choices=["Active", "Deactive"], default="Active")
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())
    
    meta = {
        'indexes': [
            'from_city_id',  # Index for faster queries by from_city_id
            'to_city_id',  # Index for faster queries by to_city_id
        ]
    }


    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)


def create_route_for_professional(professional_user_id, route_data):
    try:
        from_country_id = route_data['from_country_id']
        to_country_id = route_data['to_country_id']
        from_city_id = route_data['from_city_id']
        to_city_id = route_data['to_city_id']
        travel_period = route_data['travel_period']
        shipment_type = route_data['shipment_type']
        
        if not all([from_country_id, to_country_id, from_city_id, to_city_id, travel_period, shipment_type]):
            print("Missing route data. All fields are required.")
            return False

        professional = User.objects(id=professional_user_id, user_type="professional").first()

        if not professional:
            print(f"Professional with user_id {professional_user_id} not found.")
            return False
        
        existing_route = GpRoutes.objects(
            professional=professional,
            from_country_id=from_country_id,
            to_country_id=to_country_id,
            from_city_id=from_city_id,
            to_city_id=to_city_id,
            travel_period=travel_period,
            shipment_type=shipment_type
        ).first()
        if existing_route:
            print("Route already exists for this professional.")
            return False

        new_route = GpRoutes(
            professional=professional,
            from_country_id=from_country_id,
            to_country_id=to_country_id,
            from_city_id=from_city_id,
            to_city_id=to_city_id,
            travel_period=travel_period,
            shipment_type=shipment_type
        )
        new_route.save()

        print(f"Created new route for professional with user_id {professional_user_id}.")
        return new_route

    except Exception as e:
        print(f"Error creating route for professional: {e}")
        return False


# Get all gp routes for a professional user id
def get_gp_routes_for_professional(professional_user_id):
    try:
        professional = User.objects(id=professional_user_id, user_type="professional").first()
        if not professional:
            print(f"Professional with user_id {professional_user_id} not found.")
            return []
        routes = GpRoutes.objects(professional=professional)
        return list(routes)
    except Exception as e:
        print(f"Error fetching routes for professional: {e}")
        return []


def get_all_professional_routes():
    try:
        routes = GpRoutes.objects().order_by('-updated_at')
        result = []

        for route in routes:
            professional = route.professional

            from_country_id = getattr(route, "from_country_id", None)
            to_country_id = getattr(route, "to_country_id", None)
            from_city_id = getattr(route, "from_city_id", None)
            to_city_id = getattr(route, "to_city_id", None)

            from_country = Country.objects(id=from_country_id).first() if from_country_id is not None else None
            to_country = Country.objects(id=to_country_id).first() if to_country_id is not None else None
            from_city = City.objects(id=from_city_id).first() if from_city_id is not None else None
            to_city = City.objects(id=to_city_id).first() if to_city_id is not None else None

            result.append({
                "id": route.id,
                "professional_user_id": professional.id if professional else None,
                "professional_wp_number": professional.wp_number if professional else "Unknown",
                "from_country_id": from_country_id,
                "to_country_id": to_country_id,
                "from_city_id": from_city_id,
                "to_city_id": to_city_id,
                "from_country": from_country.name if from_country else "Unknown",
                "to_country": to_country.name if to_country else "Unknown",
                "from_city": from_city.name if from_city else "Unknown",
                "to_city": to_city.name if to_city else "Unknown",
                "travel_period": route.travel_period if getattr(route, "travel_period", None) else "",
                "shipment_type": route.shipment_type if getattr(route, "shipment_type", None) else "",
                "status": route.status if getattr(route, "status", None) else "Active",
                "created_at": route.created_at,
                "updated_at": route.updated_at
            })

        return result, len(result)

    except Exception as e:
        print(f"Error fetching all professional routes: {e}")
        return [], 0


def update_professional_route(route_id, professional_user_id, route_data):
    try:
        route = GpRoutes.objects(id=route_id).first()
        if not route:
            print(f"Route with id {route_id} not found.")
            return False

        professional = User.objects(id=professional_user_id, user_type="professional").first()
        if not professional:
            print(f"Professional with user_id {professional_user_id} not found.")
            return False

        from_country_id = route_data["from_country_id"]
        to_country_id = route_data["to_country_id"]
        from_city_id = route_data["from_city_id"]
        to_city_id = route_data["to_city_id"]
        travel_period = route_data["travel_period"]
        shipment_type = route_data["shipment_type"]
        status = route_data["status"]

        if status not in ["Active", "Deactive"]:
            print(f"Invalid status: {status}")
            return False

        existing_route = GpRoutes.objects(
            id__ne=route_id,
            professional=professional,
            from_country_id=from_country_id,
            to_country_id=to_country_id,
            from_city_id=from_city_id,
            to_city_id=to_city_id
            # travel_period=travel_period,
            # shipment_type=shipment_type
        ).first()
        if existing_route:
            print("Another identical route already exists for this professional.")
            return False

        route.professional = professional
        route.from_country_id = from_country_id
        route.to_country_id = to_country_id
        route.from_city_id = from_city_id
        route.to_city_id = to_city_id
        route.travel_period = travel_period
        route.shipment_type = shipment_type
        route.status = status
        route.save()

        return route
    except Exception as e:
        print(f"Error updating professional route: {e}")
        return False


def delete_professional_route(route_id):
    try:
        route = GpRoutes.objects(id=route_id).first()
        if not route:
            print(f"Route with id {route_id} not found.")
            return False

        route.delete()
        print(f"Professional route #{route_id} deleted successfully.")
        return True
    except Exception as e:
        print(f"Error deleting professional route: {e}")
        return False



#### Chatbot functions

def create_route_for_professional_chatbot(whatsapp, route_data):
    try:
        from utils_db import can_user_perform_action
        if not can_user_perform_action(whatsapp, "GP Publish tour"):
            print(f"User with WhatsApp number '{whatsapp}' cannot perform action 'GP Publish tour' due to insufficient credits or other issues.")
            return False, "insufficient_credits"

        from_country_id = route_data['from_country_id']
        to_country_id = route_data['to_country_id']
        from_city_id = route_data['from_city_id']
        to_city_id = route_data['to_city_id']
        travel_period = route_data['travel_period']
        shipment_type = route_data['shipment_type']
        

        if not all([from_country_id, to_country_id, from_city_id, to_city_id, travel_period, shipment_type]):
            print("Missing route data. All fields are required.")
            return False, "not_all_data"

        professional = User.objects(wp_number=whatsapp, user_type="professional").first()

        if not professional:
            print(f"Professional with WhatsApp number {whatsapp} not found.")
            return False, "no_user"
        
        existing_route = GpRoutes.objects(
            professional=professional,
            from_country_id=from_country_id,
            to_country_id=to_country_id,
            from_city_id=from_city_id,
            to_city_id=to_city_id,
            travel_period=travel_period,
            shipment_type=shipment_type
        ).first()
        if existing_route:
            print("Route already exists for this professional.")
            return False, "existing_route"

        new_route = GpRoutes(
            professional=professional,
            from_country_id=from_country_id,
            to_country_id=to_country_id,
            from_city_id=from_city_id,
            to_city_id=to_city_id,
            travel_period=travel_period,
            shipment_type=shipment_type
        )
        from utils_db import deduct_credits_for_action
        deduction_result, message = deduct_credits_for_action(whatsapp, "GP Publish tour")
        if not deduction_result:
            print(f"Failed to deduct credits for user with WhatsApp number '{whatsapp}' when creating route.")
            return False, "deduction_failed"
        new_route.save()

        print(f"Created new route for professional with route_id {new_route.id}.")
        
        # deduct credits for creating a route
        return new_route, "okay"

    except Exception as e:
        print(f"Error creating route for professional: {e}")
        return False, "exception"


# Get all gp routes for a professional user id
def get_gp_routes_for_professional_chatbot(whatsapp):
    try:
        professional = User.objects(wp_number=whatsapp, user_type="professional").first()
        if not professional:
            print(f"Professional with WhatsApp number {whatsapp} not found.")
            return []
        routes = GpRoutes.objects(professional=professional)
        result = []
        for route in routes:
            from_city = City.objects(id=route.from_city_id).first()
            to_city = City.objects(id=route.to_city_id).first()
            result.append({
                "id": route.id,
                "from_city": from_city.name if from_city else "Unknown",
                "to_city": to_city.name if to_city else "Unknown",
                "travel_period": route.travel_period if getattr(route, "travel_period", None) else "",
                "shipment_type": route.shipment_type if getattr(route, "shipment_type", None) else "",
                "status": route.status if getattr(route, "status", None) else "Active",
            })
        return result
    except Exception as e:
        print(f"Error fetching routes for professional: {e}")
        return []


def update_professional_route_status_chatbot(route_id, new_status):
    try:
        route = GpRoutes.objects(id=route_id).first()
        if not route:
            print(f"Route with id {route_id} not found.")
            return False, "deduction_failed"

        if not new_status:
            print("New status is required.")
            return False, "deduction_failed"

        if new_status not in ["Disponible", "Indisponible"]:
            print(f"Invalid status: {new_status}")
            return False, "deduction_failed"
    
        if route.status == new_status:
            print(f"Route is already in the status '{new_status}'. No update needed.")
            return False, "already_in_status"

        # Check if the user has enough credits to change the status if they are trying to set it to "Disponible"
        from utils_db import deduct_credits_for_action
        deduction_result, message = deduct_credits_for_action(route.professional.wp_number, "GP status change")
        if not deduction_result:
            if message == "insufficient_credits":
                print(f"User with WhatsApp number '{route.professional.wp_number}' does not have enough credits to change route status to 'Disponible'.")
                return False, "insufficient_credits"
            else:
                print(f"Failed to deduct credits for user with WhatsApp number '{route.professional.wp_number}' when changing route status.")
                return False, "deduction_failed"

        if new_status == "Disponible":
            new_status = "Active"
        elif new_status == "Indisponible":
            new_status = "Deactive"

        route.status = new_status
        route.save()

        return True, "okay"
    except Exception as e:
        print(f"Error updating professional route: {e}")
        return False, "deduction_failed"