from mongoengine import *
from datetime import datetime
from db_country import Country

# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0")

class City(Document):
    id = SequenceField(primary_key = True)
    name = StringField(required=True)
    country = ReferenceField(Country, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'indexes': [
            'country',  # Index for faster queries by country
        ]
    }