from mongoengine import *
from datetime import datetime, timezone
from db_user import User
# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)

class ContactRequest(Document):
    id = SequenceField(primary_key = True)
    user_id = IntField(required=True)
    status = StringField(required=True, choices=['pending', 'in_review', 'closed'], default='pending')
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())

    meta = {
        'indexes': [
            'user_id',  # Index for faster queries by user_id
            'status',   # Index for faster queries by status
        ]
    }

    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)


def create_contact_request(user_id):
    # First, check if the user exists
    user = User.objects(id=user_id).first()
    if user is None:
        print(f"No user found with id {user_id}. Cannot create contact request.")
        return False, "user_not_found"

    # Then check if there's already an open contact request for this user
    existing_request = ContactRequest.objects(user_id=user_id, status__in=['pending', 'in_review']).first()
    if existing_request:
        print(f"User with id {user_id} already has an open contact request with status '{existing_request.status}'.")
        return False, "open_request_exists"
    contact_request = ContactRequest(
        user_id=user_id,
        status='pending'
    )
    contact_request.save()
    return contact_request, "okay"


def get_all_contact_requests():
    try:
        requests = ContactRequest.objects().order_by('-updated_at')
        result = []

        for item in requests:
            user = User.objects(id=item.user_id).first()

            result.append({
                "id": item.id,
                "user_id": item.user_id,
                "user_wp_number": user.wp_number if user else "Unknown",
                "user_role": user.user_type if user else "Unknown",
                "status": item.status,
                "created_at": item.created_at,
                "updated_at": item.updated_at
            })

        return result, len(result)
    except Exception as e:
        print(f"Error retrieving contact requests: {e}")
        return [], 0


def update_contact_request_status(request_id, new_status):
    try:
        if new_status not in ['pending', 'in_review', 'closed']:
            print(f"Invalid status: {new_status}")
            return False, "invalid_status"

        contact_request = ContactRequest.objects(id=request_id).first()
        if not contact_request:
            print(f"Contact request with id {request_id} not found.")
            return False, "not_found"

        contact_request.status = new_status
        contact_request.save()
        return contact_request, "okay"
    except Exception as e:
        print(f"Error updating contact request status: {e}")
        return False, "error"


def get_contact_request_by_id(request_id):
    try:
        return ContactRequest.objects(id=request_id).first()
    except Exception as e:
        print(f"Error retrieving contact request by id: {e}")
        return None



# Chatbot functions

def create_contact_request_chatbot(whatsApp):
    # First, check if the user exists
    user = User.objects(wp_number=whatsApp).first()
    if user is None:
        print(f"No user found with WhatsApp number {whatsApp}. Cannot create contact request.")
        return False, "user_not_found"

    # Then check if there's already an open contact request for this user
    existing_request = ContactRequest.objects(user_id=user.id, status__in=['pending', 'in_review']).first()
    if existing_request:
        print(f"User with id {user.id} already has an open contact request with status '{existing_request.status}'.")
        return False, "open_request_exists"
    contact_request = ContactRequest(
        user_id=user.id,
        status='pending'
    )
    contact_request.save()
    return contact_request, "okay"
