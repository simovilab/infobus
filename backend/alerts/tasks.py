from celery import shared_task

from .models import *


@shared_task
def get_weather():
    return "Fetching Weather"


@shared_task
def get_social_feed():
    return "Fetching Social Feed"


@shared_task
def get_cap_alerts():
    return "Fetching CAP Alerts"
