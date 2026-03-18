from mongoengine import *
from datetime import datetime, timezone
from db_airport import Airport
from db_city import City
from db_user import User
# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)

class UserCreditBalance(Document):
    id = SequenceField(primary_key = True)
    user_id = IntField(required=True)
    credits_balance = IntField(required=True)
    last_recharge_date = DateTimeField(default=utcnow())
    updated_at = DateTimeField(default=utcnow())
    
    meta = {
        'indexes': [
            'user_id',  # Index for faster queries by user_id
            'credits_balance',  # Index for faster queries by credits_balance
        ]
    }


    def save(self, *args, **kwargs):
        # Ensure updated_at always bumps on save
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)

def create_or_update_user_credit_balance(user_id, credits_to_add):
    # Check if a credit balance record for the user already exists
    credit_balance = UserCreditBalance.objects(user_id=user_id).first()
    
    if credit_balance:
        # If it exists, update the existing record
        credit_balance.credits_balance += credits_to_add
        credit_balance.last_recharge_date = utcnow()
        credit_balance.save()
        print(f"Updated user {user_id} credit balance to {credit_balance.credits_balance}.")
    else:
        # If it doesn't exist, create a new record
        new_credit_balance = UserCreditBalance(
            user_id=user_id,
            credits_balance=credits_to_add,
            last_recharge_date=utcnow()
        )
        new_credit_balance.save()
        print(f"Created credit balance for user {user_id} with {credits_to_add} credits.")


def get_user_credit_balance(user_id):
    # Retrieve the credit balance for a specific user
    credit_balance = UserCreditBalance.objects(user_id=user_id).first()
    
    if credit_balance:
        return credit_balance.credits_balance
    else:
        print(f"No credit balance found for user {user_id}.")
        return None
    

# deduct credits when user uses a credit
def deduct_user_credits(user_id, credits_to_deduct):
    credit_balance = UserCreditBalance.objects(user_id=user_id).first()
    
    if credit_balance:
        if credit_balance.credits_balance >= credits_to_deduct:
            credit_balance.credits_balance -= credits_to_deduct
            credit_balance.save()
            print(f"Deducted {credits_to_deduct} credits from user {user_id}. New balance: {credit_balance.credits_balance}.")
            return {"success": True, "new_balance": credit_balance.credits_balance}
        else:
            print(f"User {user_id} does not have enough credits to deduct. Current balance: {credit_balance.credits_balance}.")
            return {"success": False, "message": "insufficient_credits"}
    else:
        print(f"No credit balance found for user {user_id}. Cannot deduct credits.")
        return {"success": False, "message": "no_credit_balance"}


def get_user_credit_balance_record(user_id):
    try:
        return UserCreditBalance.objects(user_id=user_id).first()
    except Exception as e:
        print(f"Error retrieving credit balance record for user {user_id}: {e}")
        return None


def set_user_credit_balance(user_id, new_balance):
    try:
        if new_balance < 0:
            print("Credit balance cannot be negative.")
            return False

        credit_balance = UserCreditBalance.objects(user_id=user_id).first()

        if credit_balance:
            credit_balance.credits_balance = new_balance
            credit_balance.last_recharge_date = utcnow()
            credit_balance.save()
            print(f"Set user {user_id} credit balance to {new_balance}.")
            return True
        else:
            new_credit_balance = UserCreditBalance(
                user_id=user_id,
                credits_balance=new_balance,
                last_recharge_date=utcnow()
            )
            new_credit_balance.save()
            print(f"Created credit balance for user {user_id} with {new_balance} credits.")
            return True

    except Exception as e:
        print(f"Error setting credit balance for user {user_id}: {e}")
        return False


def check_user_has_sufficient_credits(user_id, required_credits):
    credit_balance = get_user_credit_balance(user_id)
    
    if credit_balance is not None:
        return credit_balance >= required_credits
    else:
        return False


# For chatbot functions

def get_user_credit_balance_chatbot(whatsapp):
    user = User.objects(wp_number=whatsapp).first()
    if not user:
        print(f"No user found with WhatsApp number {whatsapp}.")
        return None
    # Retrieve the credit balance for a specific user
    credit_balance = UserCreditBalance.objects(user_id=user.id).first()
    
    if credit_balance:
        return credit_balance.credits_balance
    else:
        print(f"No credit balance found for user {user.id}.")
        return None