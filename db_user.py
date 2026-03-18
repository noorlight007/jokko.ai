from mongoengine import *
from datetime import datetime, timezone

# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)

class User(Document):
    id = SequenceField(primary_key = True)
    wp_profile_name = StringField(strip=True)
    wp_number = StringField(
        required=True,
        unique=True,          # likely you don't want duplicates
        min_length=3,
        max_length=32,
        strip=True,
    )
    user_type = StringField(
        required=True,
        choices=("client", "professional", "driver"),
    )
    joined_at = DateTimeField(default=utcnow)  # set on first save
    updated_at = DateTimeField(default=utcnow) # updated on every save

    meta = {
        "collection": "users",
        "indexes": [
            {"fields": ["wp_number"], "unique": True},
            "user_type",
            "-updated_at",
        ],
    }

def create_or_get_user(sender, wp_profile_name):
    try:
        wp_number = sender.replace(" ", "").strip() if isinstance(sender, str) else sender
        user = User.objects(wp_number=wp_number).first()
        if user:
            return user
        new_user = User(wp_profile_name=wp_profile_name, wp_number=wp_number, user_type="client")
        new_user.save()

        # Credit adding for new user
        from db_credits import create_or_update_user_credit_balance
        from db_credits_deduction import get_credit_allowance

        credit_allowance = get_credit_allowance()
        credits_to_add = credit_allowance if credit_allowance is not None else 0

        create_or_update_user_credit_balance(
            user_id=new_user.id,
            credits_to_add=credits_to_add
        )
        return new_user
    except Exception as e:
        print(f"❌ Error in create_or_get_user: {e}")
        return None

def set_user_role(sender, new_role):
    wp_number = sender.replace(" ", "").strip() if isinstance(sender, str) else sender
    if new_role not in {"client", "professional", "driver"}:
        raise ValueError("Invalid user role")
    updated = User.objects(wp_number=wp_number).update_one(
        set__user_type=new_role,
        set__updated_at=utcnow(),
    )
    return bool(updated)

def get_user_by_user_id(user_id):
    try:
        user = User.objects(id=user_id).first()
        if user:
            return user
        else:
            print(f"User with id {user_id} not found.")
            return None
    except Exception as e:
        print(f"Error retrieving user by id: {e}")
        return None


def get_user_by_wp_number(wp_number):
    try:
        user = User.objects(wp_number=wp_number).first()
        if user:
            return user
        else:
            print(f"User with WhatsApp number {wp_number} not found.")
            return None
    except Exception as e:
        print(f"Error retrieving user by WhatsApp number: {e}")
        return None

# Get all users
def get_all_users():
    return list(User.objects)

# if __name__ == "__main__":
#     # Example usage
#     print(set_user_role("33605809702", "driver"))