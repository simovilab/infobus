"""
GraphQL types for Infobús project using Strawberry.
"""
import strawberry
from strawberry import auto
from strawberry_django import type
from decimal import Decimal
from typing import Optional

from gtfs.models import Agency, Stop, GTFSProvider


@strawberry.type
class HelloType:
    message: str


@type(GTFSProvider)
class GTFSProviderType:
    provider_id: auto
    code: auto
    name: auto
    description: auto
    website: auto
    timezone: auto
    is_active: auto


@type(Agency)
class AgencyType:
    id: auto
    agency_id: auto
    agency_name: auto
    agency_url: auto
    agency_timezone: auto
    agency_lang: auto
    agency_phone: auto
    agency_fare_url: auto
    agency_email: auto


@type(Stop)
class StopType:
    id: auto
    stop_id: auto
    stop_code: auto
    stop_name: auto
    stop_heading: auto
    stop_desc: auto
    stop_lat: auto
    stop_lon: auto
    zone_id: auto
    stop_url: auto
    location_type: auto
    parent_station: auto