import os
from celery import Celery

rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
rabbitmq_pass = os.getenv("RABBITMQ_PASS", "guest")
rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")

broker_url = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"

app = Celery("tasks", broker=broker_url)


@app.task
def get_vehicle_positions():
    return "Vehicle positions task executed"


@app.task
def get_trip_updates():
    return "Trip updates task executed"
