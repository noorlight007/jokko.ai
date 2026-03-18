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


class ParcelEvent(Document):
    id = SequenceField(primary_key = True)
    created_by_user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    from_country_id = IntField(required=True)
    to_country_id = IntField(required=True)
    from_city_id = IntField(required=True)
    to_city_id = IntField(required=True)
    travel_period = StringField(choices=["Dans moins de 72 heures", "Cette semaine", "La semaine prochaine", "Une date ultérieure"], required=True)
    shipment_type = StringField(choices=["Documents", "Petit colis", "Moyen colis", "Grand colis", "Mixte petit/moyen colis", "Mixte tous types colis", ], required=True)
    event_status = StringField(choices=["waiting", "accepted", "cancelled"], default="waiting")
    invitation_logs = EmbeddedDocumentListField(InvitationLog)
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())

    meta = {
        'collection': 'parcel_events',
        'indexes': [
            'created_by_user',  # Index for faster queries by user
            'from_country_id',
            'to_country_id',
            'from_city_id',
            'to_city_id',
            'travel_period',
            'shipment_type',
            'event_status',
            '-updated_at',  # Index for sorting by most recently updated
        ]
    }

    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)
    

def get_all_parcel_events():
    try:
        from db_country import Country
        from db_city import City

        events = ParcelEvent.objects().order_by('-updated_at')
        result = []

        for item in events:
            creator = item.created_by_user

            from_country = Country.objects(id=item.from_country_id).first() if item.from_country_id is not None else None
            to_country = Country.objects(id=item.to_country_id).first() if item.to_country_id is not None else None
            from_city = City.objects(id=item.from_city_id).first() if item.from_city_id is not None else None
            to_city = City.objects(id=item.to_city_id).first() if item.to_city_id is not None else None

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
                "from_country_id": item.from_country_id,
                "to_country_id": item.to_country_id,
                "from_city_id": item.from_city_id,
                "to_city_id": item.to_city_id,
                "from_country": from_country.name if from_country else "Unknown",
                "to_country": to_country.name if to_country else "Unknown",
                "from_city": from_city.name if from_city else "Unknown",
                "to_city": to_city.name if to_city else "Unknown",
                "travel_period": item.travel_period,
                "shipment_type": item.shipment_type,
                "event_status": item.event_status,
                "invitation_logs": invitation_logs,
                "created_at": item.created_at,
                "updated_at": item.updated_at
            })

        return result, len(result)
    except Exception as e:
        print(f"Error retrieving parcel events: {e}")
        return [], 0


def create_parcel_event(payload):
    try:
        required_fields = [
            "created_by_user_id",
            "from_country_id",
            "to_country_id",
            "from_city_id",
            "to_city_id",
            "travel_period",
            "shipment_type"
        ]

        for field in required_fields:
            if payload.get(field) in [None, ""]:
                print(f"Missing required field: {field}")
                return False

        creator = User.objects(id=payload["created_by_user_id"]).first()
        if not creator:
            print("Created by user not found.")
            return False

        event = ParcelEvent(
            created_by_user=creator,
            from_country_id=payload["from_country_id"],
            to_country_id=payload["to_country_id"],
            from_city_id=payload["from_city_id"],
            to_city_id=payload["to_city_id"],
            travel_period=payload["travel_period"],
            shipment_type=payload["shipment_type"],
            event_status=payload.get("event_status", "waiting")
        )
        event.save()
        return event
    except Exception as e:
        print(f"Error creating parcel event: {e}")
        return False


def update_parcel_event_status(event_id, new_status):
    try:
        if new_status not in ["waiting", "accepted", "cancelled"]:
            print(f"Invalid event status: {new_status}")
            return False, "invalid_status"

        event = ParcelEvent.objects(id=event_id).first()
        if not event:
            print(f"Parcel event #{event_id} not found.")
            return False, "not_found"

        event.event_status = new_status
        event.save()
        return event, "okay"
    except Exception as e:
        print(f"Error updating parcel event status: {e}")
        return False, "error"


def delete_parcel_event(event_id):
    try:
        event = ParcelEvent.objects(id=event_id).first()
        if not event:
            print(f"Parcel event #{event_id} not found.")
            return False

        event.delete()
        return True
    except Exception as e:
        print(f"Error deleting parcel event: {e}")
        return False


## Chatbot functions

def create_parcel_event_chatbot(whatsapp, payload):
    try:
        # Check if user exists
        user = User.objects(wp_number=whatsapp).first()
        if not user:
            print(f"User with WhatsApp number {whatsapp} not found.")
            return False, "user_not_found"
        required_fields = [
            "from_country_id",
            "to_country_id",
            "from_city_id",
            "to_city_id",
            "travel_period",
            "shipment_type"
        ]

        for field in required_fields:
            if payload.get(field) in [None, ""]:
                print(f"Missing required field: {field}")
                return False, f"missing_field"

        # Check if the user has any existing events with status "waiting"
        existing_events = ParcelEvent.objects(created_by_user=user, event_status="waiting")
        if existing_events:
            print(f"User with WhatsApp number {whatsapp} already has a pending event.")
            return False, "pending_event_exists"

        event = ParcelEvent(
            created_by_user=user,
            from_country_id=payload["from_country_id"],
            to_country_id=payload["to_country_id"],
            from_city_id=payload["from_city_id"],
            to_city_id=payload["to_city_id"],
            travel_period=payload["travel_period"],
            shipment_type=payload["shipment_type"],
            event_status=payload.get("event_status", "waiting")
        )
        event.save()
        return event, "okay"
    except Exception as e:
        print(f"Error creating parcel event: {e}")
        return False, "error"