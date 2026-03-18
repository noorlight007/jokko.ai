from mongoengine import *
from datetime import datetime, timezone

# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)

class CreditAllowance(Document):
    id = SequenceField(primary_key = True)
    credits_allowance_value = IntField(required=True)
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())
    meta = {
        'indexes': [
            'credits_allowance_value',  # Index for faster queries by credits_allowance_value
        ]
    }

    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)

def create_or_update_credit_allowance(allowance_value):
    try:
        # Check if a credit allowance record already exists
        credit_allowance = CreditAllowance.objects().first()
        
        if credit_allowance:
            # If it exists, update the existing record
            credit_allowance.credits_allowance_value = allowance_value
            credit_allowance.save()
            print(f"Updated credit allowance to {allowance_value}.")
            return True
        else:
            # If it doesn't exist, create a new record
            new_credit_allowance = CreditAllowance(
                credits_allowance_value=allowance_value
            )
            new_credit_allowance.save()
            print(f"Created credit allowance with value {allowance_value}.")
            return True
    
    except Exception as e:
        print(f"Error creating/updating credit allowance: {e}")
        return False

def get_credit_allowance():
    try:
        credit_allowance = CreditAllowance.objects().first()
        if credit_allowance:
            return credit_allowance.credits_allowance_value
        else:
            print("No credit allowance found.")
            return None
    except Exception as e:
        print(f"Error retrieving credit allowance: {e}")
        return None


DEFAULT_CREDIT_ACTIONS = [
    "GP Publish tour",
    "GP status change",
    "Driver status change",
    "GP accept parcel request",
    "GP reject parcel request",
    "GP ignore parcel request",
    "Driver accept Pickup request",
    "Driver reject Pickup request",
    "Driver ignore Pickup request",
]

class CreditDeduction(Document):
    id = SequenceField(primary_key = True)
    actions = StringField(required=True, choices=DEFAULT_CREDIT_ACTIONS)
    credits_deduction_value = IntField(required=True)
    created_at = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())
    meta = {
        'indexes': [
            'actions',  # Index for faster queries by actions
        ]
    }

    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)


def create_or_update_credit_deduction(action, deduction_value):
    try:
        # Check if a credit deduction record for the action already exists
        credit_deduction = CreditDeduction.objects(actions=action).first()
        
        if credit_deduction:
            # If it exists, update the existing record
            credit_deduction.credits_deduction_value = deduction_value
            credit_deduction.save()
            print(f"Updated credit deduction for action '{action}' to {deduction_value}.")
            return True
        else:
            # If it doesn't exist, create a new record
            new_credit_deduction = CreditDeduction(
                actions=action,
                credits_deduction_value=deduction_value
            )
            new_credit_deduction.save()
            print(f"Created credit deduction for action '{action}' with value {deduction_value}.")
            return True
    
    except Exception as e:
        print(f"Error creating/updating credit deduction for action '{action}': {e}")
        return False






def get_all_credit_deductions():
    try:
        credit_deductions = CreditDeduction.objects()
        return credit_deductions
    except Exception as e:
        print(f"Error retrieving credit deductions: {e}")
        return None


def ensure_default_credit_deductions():
    try:
        for action in DEFAULT_CREDIT_ACTIONS:
            existing = CreditDeduction.objects(actions=action).first()
            if not existing:
                CreditDeduction(
                    actions=action,
                    credits_deduction_value=0
                ).save()
                print(f"Created default credit deduction action: {action}")
        return True
    except Exception as e:
        print(f"Error ensuring default credit deductions: {e}")
        return False


def get_credit_deduction_by_action(action):
    try:
        return CreditDeduction.objects(actions=action).first()
    except Exception as e:
        print(f"Error retrieving credit deduction for action '{action}': {e}")
        return None
# Get all
# def get_all_credit_deductions():
#     try:
#         credit_deductions = CreditDeduction.objects()
#         return credit_deductions
#     except Exception as e:
#         print(f"Error retrieving credit deductions: {e}")
#         return None

# if __name__ == "__main__":
#     # Example usage
#     ensure_default_credit_deductions()