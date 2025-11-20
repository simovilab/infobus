"""
GraphQL types for Infobús project using Strawberry.
"""
import strawberry
from strawberry import auto
from strawberry_django import type
from decimal import Decimal
from typing import Optional, List, Generic, TypeVar
from django.db.models import QuerySet
from django.core.paginator import Paginator

from gtfs.models import (
    Agency, Stop, GTFSProvider, Route, Trip, StopTime, 
    Calendar, Shape, GeoShape
)


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
    stop_timezone: auto
    wheelchair_boarding: auto
    platform_code: auto
    shelter: auto
    bench: auto
    lit: auto
    bay: auto
    device_charging_station: auto
    
    # Relationships
    @strawberry.field
    def stop_times(self) -> List['StopTimeType']:
        """Get all stop times for this stop"""
        return self.stoptime_set.all()
    
    @strawberry.field
    def routes(self) -> List['RouteType']:
        """Get all routes that serve this stop"""
        # Get routes through stop_times -> trips -> routes
        route_ids = StopTime.objects.filter(
            _stop=self
        ).values_list('_trip___route', flat=True).distinct()
        return Route.objects.filter(id__in=route_ids)


@type(Route)
class RouteType:
    id: auto
    route_id: auto
    agency_id: auto
    route_short_name: auto
    route_long_name: auto
    route_desc: auto
    route_type: auto
    route_url: auto
    route_color: auto
    route_text_color: auto
    route_sort_order: auto
    
    # Relationships
    @strawberry.field
    def agency(self) -> Optional['AgencyType']:
        """Get the agency that operates this route"""
        return self._agency
    
    @strawberry.field
    def trips(self) -> List['TripType']:
        """Get all trips for this route"""
        return self.trip_set.all()
    
    @strawberry.field
    def stops(self) -> List['StopType']:
        """Get all stops served by this route"""
        # Get stops through trips -> stop_times -> stops
        stop_ids = StopTime.objects.filter(
            _trip___route=self
        ).values_list('_stop', flat=True).distinct()
        return Stop.objects.filter(id__in=stop_ids)


@type(Trip)
class TripType:
    id: auto
    trip_id: auto
    service_id: auto
    trip_headsign: auto
    trip_short_name: auto
    direction_id: auto
    block_id: auto
    shape_id: auto
    wheelchair_accessible: auto
    bikes_allowed: auto
    
    # Relationships
    @strawberry.field
    def route(self) -> Optional['RouteType']:
        """Get the route for this trip"""
        return self._route
    
    @strawberry.field
    def service(self) -> Optional['CalendarType']:
        """Get the service calendar for this trip"""
        return self._service
    
    @strawberry.field
    def stop_times(self) -> List['StopTimeType']:
        """Get all stop times for this trip ordered by sequence"""
        return self.stoptime_set.all().order_by('stop_sequence')
    
    @strawberry.field
    def stops(self) -> List['StopType']:
        """Get all stops for this trip in sequence order"""
        stop_times = self.stoptime_set.all().order_by('stop_sequence')
        return [st._stop for st in stop_times if st._stop]
    
    @strawberry.field
    def geoshape(self) -> Optional['GeoShapeType']:
        """Get the geographic shape for this trip"""
        return self.geoshape


@type(StopTime)
class StopTimeType:
    id: auto
    trip_id: auto
    arrival_time: auto
    departure_time: auto
    stop_id: auto
    stop_sequence: auto
    stop_headsign: auto
    pickup_type: auto
    drop_off_type: auto
    shape_dist_traveled: auto
    timepoint: auto
    
    # Relationships
    @strawberry.field
    def trip(self) -> Optional['TripType']:
        """Get the trip for this stop time"""
        return self._trip
    
    @strawberry.field
    def stop(self) -> Optional['StopType']:
        """Get the stop for this stop time"""
        return self._stop


@type(Calendar)
class CalendarType:
    id: auto
    service_id: auto
    monday: auto
    tuesday: auto
    wednesday: auto
    thursday: auto
    friday: auto
    saturday: auto
    sunday: auto
    start_date: auto
    end_date: auto
    
    # Relationships
    @strawberry.field
    def trips(self) -> List['TripType']:
        """Get all trips that use this service calendar"""
        return self.trip_set.all()


@type(GeoShape)
class GeoShapeType:
    id: auto
    shape_id: auto
    shape_name: auto
    shape_desc: auto
    shape_from: auto
    shape_to: auto
    has_altitude: auto
    # Note: geometry field excluded as it's complex geometric data
    
    # Relationships
    @strawberry.field
    def trips(self) -> List['TripType']:
        """Get all trips that use this geographic shape"""
        return self.trip_set.all()


# Pagination Types
@strawberry.type
class PageInfo:
    """Information about pagination in a connection"""
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None
    total_count: int
    page_number: int
    num_pages: int


# Generic paginated response types
T = TypeVar('T')

@strawberry.type
class StopConnection:
    """A connection to a list of stops"""
    edges: List[StopType]
    page_info: PageInfo

@strawberry.type
class RouteConnection:
    """A connection to a list of routes"""
    edges: List[RouteType]
    page_info: PageInfo

@strawberry.type
class TripConnection:
    """A connection to a list of trips"""
    edges: List[TripType]
    page_info: PageInfo

@strawberry.type
class StopTimeConnection:
    """A connection to a list of stop times"""
    edges: List[StopTimeType]
    page_info: PageInfo

@strawberry.type
class AgencyConnection:
    """A connection to a list of agencies"""
    edges: List[AgencyType]
    page_info: PageInfo
