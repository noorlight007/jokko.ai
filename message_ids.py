from mongoengine import *
from datetime import datetime
from db_country import Country

# Connection url with Mongodb database
connect(host = "mongodb://127.0.0.1:27017/pape?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.7.0")

class MessageIds(Document):
    msg_id = StringField(required = True)



def add_message_id(msg_id):

    check_msg_id_exist = MessageIds.objects(msg_id = str(msg_id)).first()
    
    if check_msg_id_exist:
        return False
    
    else:
        MessageIds(
            msg_id = str(msg_id)
        ).save()

        return True