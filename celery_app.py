import os
from celery import Celery

def make_celery(app_name: str):
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    celery = Celery(
        app_name,
        broker=redis_url,
        backend=redis_url,
        include=["tasks"],   # where your tasks live
    )

    # Good defaults
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )

    return celery

celery = make_celery("flask_whatsapp")
