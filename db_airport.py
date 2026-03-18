from mongoengine import *
from datetime import datetime

# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0") #This is a local database, that's why the string looks like this.

class Airport(Document):
    id = SequenceField(primary_key = True)
    name = StringField(required=True)
    country_id = IntField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'indexes': [
            'name',  # Index for faster queries by name
            'country_id',  # Index
        ]
    }