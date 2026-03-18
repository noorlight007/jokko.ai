from mongoengine import *
from datetime import datetime, timezone
from db_user import User
# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)

# Embedding the event details in the ParcelEvent document for easier access and to avoid multiple lookups when retrieving events. This is a denormalization strategy that can improve read performance at the cost of some data redundancy.
class InvitationLog(EmbeddedDocument):
    invited_user_id = IntField(required=True)
    invitation_status = StringField(choices=["pending", "accepted", "declined"], default="pending")
    invited_at = DateTimeField(default=utcnow)
    responded_at = DateTimeField()  # This will be set when the user responds to the invitation


class DriverPickupEvent(Document):
    id = SequenceField(primary_key = True)
    created_by_user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    context = StringField(choices=["Airport Pickup", "Ride to Airport"], required=True)  # In case we want to add more contexts in the future
    from_country_id = IntField(required=True)
    from_airport_id = IntField(required=True)
    from_city_id = IntField(required=True)
    travel_period = StringField(choices=["Dans moins de 72 heures", "Cette semaine", "La semaine prochaine", "Une date ultérieure"])  # optional
    num_of_people = StringField(choices=["1 ou 2", "3 ou 4", "Plus de 4"])  # optional
    num_of_small_cases = StringField(choices=["Aucune", "1 or 2", "3 à 5", "Plus de 5"])  # optional
    num_of_med_cases = StringField(choices=["Aucune", "1 or 2", "3 à 5", "Plus de 5"])  # optional
    num_of_large_cases = StringField(choices=["Aucune", "1 or 2", "3 à 5", "Plus de 5"])  # optional
    event_status = StringField(choices=["waiting", "accepted", "cancelled"], default="waiting")  # optional
    invitation_logs = EmbeddedDocumentListField(InvitationLog)
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())

    meta = {
        'collection': 'driver_pickup_events',
        'indexes': [
            'created_by_user',  # Index for faster queries by user
            'context',
            'from_country_id',
            'from_airport_id',
            'from_city_id',
            'event_status',
            '-updated_at',  # Index for sorting by most recently updated
        ]
    }

    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)



def get_all_pickup_events():
    try:
        from db_country import Country
        from db_city import City
        from db_airport import Airport

        events = DriverPickupEvent.objects().order_by('-updated_at')
        result = []

        for item in events:
            creator = item.created_by_user

            from_country = Country.objects(id=item.from_country_id).first() if item.from_country_id is not None else None
            from_city = City.objects(id=item.from_city_id).first() if item.from_city_id is not None else None
            from_airport = Airport.objects(id=item.from_airport_id).first() if item.from_airport_id is not None else None

            invitation_logs = []
            if item.invitation_logs:
                for log in item.invitation_logs:
                    invited_user = User.objects(id=log.invited_user_id).first()
                    invitation_logs.append({
                        "invited_user_id": log.invited_user_id,
                        "invited_user_wp_number": invited_user.wp_number if invited_user else "Unknown",
                        "invitation_status": log.invitation_status,
                        "invited_at": log.invited_at,
                        "responded_at": log.responded_at
                    })

            result.append({
                "id": item.id,
                "created_by_user_id": creator.id if creator else None,
                "created_by_user_wp_number": creator.wp_number if creator else "Unknown",
                "context": item.context,
                "from_country_id": item.from_country_id,
                "from_airport_id": item.from_airport_id,
                "from_city_id": item.from_city_id,
                "from_country": from_country.name if from_country else "Unknown",
                "from_city": from_city.name if from_city else "Unknown",
                "from_airport": from_airport.name if from_airport else "Unknown",
                "travel_period": item.travel_period,
                "num_of_people": item.num_of_people,
                "num_of_small_cases": item.num_of_small_cases,
                "num_of_med_cases": item.num_of_med_cases,
                "num_of_large_cases": item.num_of_large_cases,
                "event_status": item.event_status,
                "invitation_logs": invitation_logs,
                "created_at": item.created_at,
                "updated_at": item.updated_at
            })

        return result, len(result)
    except Exception as e:
        print(f"Error retrieving pickup events: {e}")
        return [], 0


def create_pickup_event(payload):
    try:
        required_fields = [
            "created_by_user_id",
            "context",
            "from_country_id",
            "from_airport_id",
            "from_city_id",
        ]

        for field in required_fields:
            if payload.get(field) in [None, ""]:
                print(f"Missing required field: {field}")
                return False

        creator = User.objects(id=payload["created_by_user_id"]).first()
        if not creator:
            print("Created by user not found.")
            return False

        event = DriverPickupEvent(
            created_by_user=creator,
            context=payload["context"],
            from_country_id=payload["from_country_id"],
            from_airport_id=payload["from_airport_id"],
            from_city_id=payload["from_city_id"],
            travel_period=payload.get("travel_period"),
            num_of_people=payload.get("num_of_people"),
            num_of_small_cases=payload.get("num_of_small_cases"),
            num_of_med_cases=payload.get("num_of_med_cases"),
            num_of_large_cases=payload.get("num_of_large_cases"),
            event_status=payload.get("event_status", "waiting")
        )
        event.save()
        return event
    except Exception as e:
        print(f"Error creating pickup event: {e}")
        return False


def update_pickup_event_status(event_id, new_status):
    try:
        if new_status not in ["waiting", "accepted", "cancelled"]:
            print(f"Invalid event status: {new_status}")
            return False, "invalid_status"

        event = DriverPickupEvent.objects(id=event_id).first()
        if not event:
            print(f"Pickup event #{event_id} not found.")
            return False, "not_found"

        event.event_status = new_status
        event.save()
        return event, "okay"
    except Exception as e:
        print(f"Error updating pickup event status: {e}")
        return False, "error"


def delete_pickup_event(event_id):
    try:
        event = DriverPickupEvent.objects(id=event_id).first()
        if not event:
            print(f"Pickup event #{event_id} not found.")
            return False

        event.delete()
        return True
    except Exception as e:
        print(f"Error deleting pickup event: {e}")
        return False
    

# Chatbot route

def create_pickup_event_chatbot(whatsapp, payload, context):
    try:

        user = User.objects(wp_number = whatsapp).first()
        if not user:
            return False, "no_user_found"
        
        required_fields = [
            "from_country_id",
            "from_airport_id",
            "from_city_id",
            "travel_period",
            "num_of_people",
            "num_of_small_cases",
            "num_of_med_cases",
            "num_of_large_cases"
        ]

        for field in required_fields:
            if payload.get(field) in [None, ""]:
                print(f"Missing required field: {field}")
                return False, "missing_field"

        if not context:
            print("Missing required field: context")
            return False, "missing_field"
            
        # Check if the user has already a pickup event with the same context and from country, from aiport and from_city id that is still waiting
        existing_event = DriverPickupEvent.objects(
            created_by_user=user,
            event_status="waiting"
        ).first()

        if existing_event:
            return False, "event_already_exists"

        event = DriverPickupEvent(
            created_by_user=user,
            context=context,
            from_country_id=payload["from_country_id"],
            from_airport_id=payload["from_airport_id"],
            from_city_id=payload["from_city_id"],
            travel_period=payload.get("travel_period"),
            num_of_people=payload.get("num_of_people"),
            num_of_small_cases=payload.get("num_of_small_cases"),
            num_of_med_cases=payload.get("num_of_med_cases"),
            num_of_large_cases=payload.get("num_of_large_cases"),
            event_status=payload.get("event_status", "waiting")
        )
        event.save()
        return event, "okay"
    except Exception as e:
        print(f"Error creating pickup event: {e}")
        return False, "error"