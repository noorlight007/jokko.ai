from mongoengine import *
from datetime import datetime, timezone

# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)

class Admin(Document):
    id = SequenceField(primary_key = True)
    firstName = StringField(strip=True)
    lastName = StringField(strip=True)
    email = StringField(
        required=True,
        unique=True,          # likely you don't want duplicates
        min_length=5,
        max_length=255,
        strip=True,
    )
    password = StringField(required=True, min_length=8)
    last_login = DateTimeField()
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())

    meta = {
        'collection': 'admins',
        'indexes': [
            {'fields': ['email'], 'unique': True},
        ]
    }


    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)

def create_admin(firstName, lastName, email, password):
    try:
        admin = Admin(
            firstName=firstName,
            lastName=lastName,
            email=email,
            password=password
        )
        admin.save()
        print(f"Admin {email} created successfully.")
        return admin
    except Exception as e:
        print(f"Error creating admin: {e}")
        return None

def get_admin_by_email(email):
    try:
        admin = Admin.objects(email=email).first()
        if admin:
            return admin
        else:
            print(f"No admin found with email: {email}")
            return None
    except Exception as e:
        print(f"Error retrieving admin: {e}")
        return None

def update_admin_password(email, new_password):
    try:
        admin = Admin.objects(email=email).first()
        if admin:
            admin.password = new_password
            admin.save()
            print(f"Admin {email} password updated successfully.")
            return True
        else:
            print(f"No admin found with email: {email}")
            return False
    except Exception as e:
        print(f"Error updating admin password: {e}")
        return False


# Get all admins
def get_all_admins():
    return list(Admin.objects)

# Login check
def check_admin_login(email, password):
    try:
        admin = Admin.objects(email=email).first()
        if admin and admin.password == password:
            admin.last_login = utcnow()
            admin.save()
            print(f"Admin {email} logged in successfully.")
            return True
        else:
            print(f"Invalid login attempt for email: {email}")
            return False
    except Exception as e:
        print(f"Error during login: {e}")
        return False

def login_admin(email, password):
    try:
        admin = Admin.objects(email=email).first()
        if admin and admin.password == password:
            admin.last_login = utcnow()
            admin.save()
            print(f"Admin {email} logged in successfully.")
            return admin
        else:
            print(f"Invalid login attempt for email: {email}")
            return None
    except Exception as e:
        print(f"Error during login: {e}")
        return None

if __name__ == "__main__":
    # Example usage
    create_admin("Jolof", "Studio", "jolof@gmail.com", "jolof123")