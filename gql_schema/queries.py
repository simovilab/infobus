"""
GraphQL queries for Infobús project.
"""
import strawberry
from typing import List, Optional
from strawberry_django import field
from django.core.paginator import Paginator

from gtfs.models import (
    Agency, Stop, GTFSProvider, Route, Trip, StopTime, Calendar
)
from .types import (
    HelloType, AgencyType, StopType, GTFSProviderType,
    RouteType, TripType, StopTimeType, CalendarType, GeoShapeType,
    StopConnection, RouteConnection, TripConnection, 
    StopTimeConnection, AgencyConnection, PageInfo
)


def create_page_info(paginator, page) -> PageInfo:
    """Helper function to create PageInfo from Django paginator"""
    return PageInfo(
        has_next_page=page.has_next(),
        has_previous_page=page.has_previous(),
        start_cursor=str(page.start_index()) if page.object_list else None,
        end_cursor=str(page.end_index()) if page.object_list else None,
        total_count=paginator.count,
        page_number=page.number,
        num_pages=paginator.num_pages
    )


@strawberry.type
class Query:
    
    @strawberry.field
    def hello(self) -> HelloType:
        """Simple hello query for testing GraphQL setup"""
        return HelloType(message="¡Hola desde GraphQL de Infobús!")
    
    # Agency Queries
    @field
    def agencies(self, page: int = 1, page_size: int = 20) -> AgencyConnection:
        """Get all agencies with pagination"""
        queryset = Agency.objects.all().order_by('agency_name')
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return AgencyConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    @field
    def agency(self, id: int) -> AgencyType:
        """Get a specific agency by ID"""
        return Agency.objects.get(id=id)
    
    @field
    def agency_by_code(self, agency_id: str, feed_id: str) -> Optional[AgencyType]:
        """Get agency by GTFS agency_id and feed_id"""
        try:
            return Agency.objects.get(agency_id=agency_id, feed__feed_id=feed_id)
        except Agency.DoesNotExist:
            return None
    
    # Stop Queries
    @field
    def stops(self, page: int = 1, page_size: int = 50) -> StopConnection:
        """Get all stops with pagination"""
        queryset = Stop.objects.all().order_by('stop_name')
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return StopConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    @field
    def stop(self, id: int) -> StopType:
        """Get a specific stop by ID"""
        return Stop.objects.get(id=id)
    
    @field
    def stop_by_code(self, stop_id: str, feed_id: str) -> Optional[StopType]:
        """Get stop by GTFS stop_id and feed_id"""
        try:
            return Stop.objects.get(stop_id=stop_id, feed__feed_id=feed_id)
        except Stop.DoesNotExist:
            return None
    
    @field
    def stops_near(self, lat: float, lon: float, radius_km: float = 1.0, 
                   page: int = 1, page_size: int = 20) -> StopConnection:
        """Find stops within radius of given coordinates"""
        from django.contrib.gis.geos import Point
        from django.contrib.gis.measure import Distance
        
        location = Point(lon, lat, srid=4326)
        queryset = Stop.objects.filter(
            stop_point__distance_lt=(location, Distance(km=radius_km))
        ).order_by('stop_name')
        
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return StopConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    # Route Queries
    @field
    def routes(self, page: int = 1, page_size: int = 20) -> RouteConnection:
        """Get all routes with pagination"""
        queryset = Route.objects.all().select_related('_agency').order_by('route_short_name')
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return RouteConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    @field
    def route(self, id: int) -> RouteType:
        """Get a specific route by ID"""
        return Route.objects.select_related('_agency').get(id=id)
    
    @field
    def route_by_code(self, route_id: str, feed_id: str) -> Optional[RouteType]:
        """Get route by GTFS route_id and feed_id"""
        try:
            return Route.objects.select_related('_agency').get(
                route_id=route_id, feed__feed_id=feed_id
            )
        except Route.DoesNotExist:
            return None
    
    @field
    def routes_by_agency(self, agency_id: int, page: int = 1, page_size: int = 20) -> RouteConnection:
        """Get routes operated by a specific agency"""
        queryset = Route.objects.filter(_agency_id=agency_id).select_related('_agency')
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return RouteConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    # Trip Queries
    @field
    def trips(self, page: int = 1, page_size: int = 50) -> TripConnection:
        """Get all trips with pagination"""
        queryset = Trip.objects.all().select_related('_route', '_service').order_by('trip_id')
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return TripConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    @field
    def trip(self, id: int) -> TripType:
        """Get a specific trip by ID"""
        return Trip.objects.select_related('_route', '_service', 'geoshape').get(id=id)
    
    @field
    def trip_by_code(self, trip_id: str, feed_id: str) -> Optional[TripType]:
        """Get trip by GTFS trip_id and feed_id"""
        try:
            return Trip.objects.select_related('_route', '_service', 'geoshape').get(
                trip_id=trip_id, feed__feed_id=feed_id
            )
        except Trip.DoesNotExist:
            return None
    
    @field
    def trips_by_route(self, route_id: int, page: int = 1, page_size: int = 20) -> TripConnection:
        """Get trips for a specific route"""
        queryset = Trip.objects.filter(_route_id=route_id).select_related(
            '_route', '_service', 'geoshape'
        ).order_by('trip_id')
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return TripConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    # StopTime Queries
    @field
    def stop_times(self, page: int = 1, page_size: int = 100) -> StopTimeConnection:
        """Get all stop times with pagination"""
        queryset = StopTime.objects.all().select_related('_trip', '_stop').order_by(
            'trip_id', 'stop_sequence'
        )
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return StopTimeConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    @field
    def stop_times_by_trip(self, trip_id: int, page: int = 1, page_size: int = 50) -> StopTimeConnection:
        """Get stop times for a specific trip in sequence order"""
        queryset = StopTime.objects.filter(_trip_id=trip_id).select_related(
            '_trip', '_stop'
        ).order_by('stop_sequence')
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return StopTimeConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    @field
    def stop_times_by_stop(self, stop_id: int, page: int = 1, page_size: int = 50) -> StopTimeConnection:
        """Get stop times for a specific stop"""
        queryset = StopTime.objects.filter(_stop_id=stop_id).select_related(
            '_trip', '_stop'
        ).order_by('arrival_time')
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return StopTimeConnection(
            edges=list(page_obj.object_list),
            page_info=create_page_info(paginator, page_obj)
        )
    
    # GTFS Provider Queries
    @field
    def gtfs_providers(self) -> List[GTFSProviderType]:
        """Get all GTFS providers"""
        return GTFSProvider.objects.all().order_by('name')
    
    @field
    def gtfs_provider(self, provider_id: int) -> GTFSProviderType:
        """Get a specific GTFS provider by ID"""
        return GTFSProvider.objects.get(provider_id=provider_id)
    
    # Nested Queries Examples
    @field
    def route_with_trips_and_stops(self, route_id: int) -> Optional[RouteType]:
        """Get a route with its trips and all stops served (demonstrates nested queries)"""
        try:
            return Route.objects.prefetch_related(
                '_route_set___trip_set',  # trips -> stop_times
                '_route_set___trip_set___stop'  # -> stops
            ).select_related('_agency').get(id=route_id)
        except Route.DoesNotExist:
            return None
