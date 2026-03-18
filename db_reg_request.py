from mongoengine import *
from datetime import datetime, timezone
from db_user import User
# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)

class Registration_request(Document):
    id = SequenceField(primary_key = True)
    created_by_user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    requested_role = StringField(choices=["driver", "professional"], required=True)
    approve_status = StringField(choices=["pending", "approved", "rejected"], default="pending")
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField()

    meta = {
        'collection': 'registration_requests',
        'indexes': [
            'created_by_user',  # Index for faster queries by user
            'approve_status',
            '-updated_at',  # Index for sorting by most recently updated
        ]
    }

    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)

# Chatbot function
def send_registration_request(whatsapp, requested_role):
    try:
        user = User.objects.get(wp_number=whatsapp).first()
        if not user:
            return False, "error"  # User not found, cannot create registration request
        existing_request = Registration_request.objects(created_by_user=user, approve_status="pending").first()
        if existing_request:
            return False, "pending_request"  # Return the existing pending request instead of creating a new one
        new_request = Registration_request(created_by_user=user, requested_role=requested_role)
        new_request.save()
        return True, "okay"
    except DoesNotExist:
        return False, "error"  # User not found, cannot create registration request
    

def approve_registration_request(request_id):
    try:
        request = Registration_request.objects.get(id=request_id)
        requested_user = request.created_by_user
        requested_user.role = request.requested_role  # Update the user's role based on the registration
        requested_user.save()
        request.approve_status = "approved"
        request.save()
        return True, "approved"
    except DoesNotExist:
        return False, "error"  # Registration request not found, cannot approve


def get_all_registration_requests():
    try:
        requests = Registration_request.objects().order_by('-updated_at')
        result = []

        for item in requests:
            user = item.created_by_user

            result.append({
                "id": item.id,
                "user_id": user.id if user else None,
                "user_wp_number": user.wp_number if user else "Unknown",
                "requested_role": item.requested_role,
                "approve_status": item.approve_status,
                "created_at": item.created_at,
                "updated_at": item.updated_at
            })

        return result, len(result)
    except Exception as e:
        print(f"Error retrieving registration requests: {e}")
        return [], 0


def approve_registration_request(request_id):
    try:
        request = Registration_request.objects.get(id=request_id)
        requested_user = request.created_by_user

        requested_user.user_type = request.requested_role
        requested_user.save()

        request.approve_status = "approved"
        request.save()
        return True, "approved"
    except DoesNotExist:
        return False, "error"
    except Exception as e:
        print(f"Error approving registration request: {e}")
        return False, "error"


def reject_registration_request(request_id):
    try:
        request = Registration_request.objects.get(id=request_id)
        request.approve_status = "rejected"
        request.save()
        return True, "rejected"
    except DoesNotExist:
        return False, "error"
    except Exception as e:
        print(f"Error rejecting registration request: {e}")
        return False, "error"


def delete_registration_request(request_id):
    try:
        request = Registration_request.objects.get(id=request_id)
        request.delete()
        return True
    except DoesNotExist:
        return False
    except Exception as e:
        print(f"Error deleting registration request: {e}")
        return False


def get_registration_request_stats():
    try:
        total_requests = Registration_request.objects.count()
        approved_requests = Registration_request.objects(approve_status="approved").count()
        rejected_requests = Registration_request.objects(approve_status="rejected").count()
        pending_requests = Registration_request.objects(approve_status="pending").count()

        return {
            "total": total_requests,
            "approved": approved_requests,
            "rejected": rejected_requests,
            "pending": pending_requests
        }
    except Exception as e:
        print(f"Error getting registration request stats: {e}")
        return {
            "total": 0,
            "approved": 0,
            "rejected": 0,
            "pending": 0
        }

def create_registration_request(user_id, requested_role):
    try:
        if requested_role not in ["driver", "professional"]:
            return False, "invalid_role"

        user = User.objects(id=user_id).first()
        if not user:
            return False, "user_not_found"

        existing_pending = Registration_request.objects(
            created_by_user=user,
            requested_role=requested_role,
            approve_status="pending"
        ).first()

        if existing_pending:
            return False, "pending_exists"

        new_request = Registration_request(
            created_by_user=user,
            requested_role=requested_role,
            approve_status="pending"
        )
        new_request.save()

        return new_request, "created"
    except Exception as e:
        print(f"Error creating registration request: {e}")
        return False, "error"