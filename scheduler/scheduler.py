import os
from celery import Celery
from datetime import timedelta

rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
rabbitmq_pass = os.getenv("RABBITMQ_PASS", "guest")
rabbitmq_host = os.getenv("RABBITMQ_HOST", "message-broker")
rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")

broker_url = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"

app = Celery("scheduler", broker=broker_url)

app.conf.beat_schedule = {
    "get-vehicle-positions-every-15s": {
        "task": "tasks.get_vehicle_positions",
        "schedule": timedelta(seconds=15),
    },
    "get-trip-updates-every-15s": {
        "task": "tasks.get_trip_updates",
        "schedule": timedelta(seconds=15),
    },
}
