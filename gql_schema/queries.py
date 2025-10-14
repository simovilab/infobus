"""
GraphQL queries for Infobús project.
"""
import strawberry
from typing import List
from strawberry_django import field

from gtfs.models import Agency, Stop, GTFSProvider
from .types import HelloType, AgencyType, StopType, GTFSProviderType


@strawberry.type
class Query:
    
    @strawberry.field
    def hello(self) -> HelloType:
        """Simple hello query for testing GraphQL setup"""
        return HelloType(message="¡Hola desde GraphQL de Infobús!")
    
    @field
    def agencies(self) -> List[AgencyType]:
        """Get all agencies"""
        return Agency.objects.all()
    
    @field
    def agency(self, id: int) -> AgencyType:
        """Get a specific agency by ID"""
        return Agency.objects.get(id=id)
    
    @field
    def stops(self) -> List[StopType]:
        """Get all stops (limited to first 100 for performance)"""
        return Stop.objects.all()[:100]
    
    @field
    def stop(self, id: int) -> StopType:
        """Get a specific stop by ID"""
        return Stop.objects.get(id=id)
    
    @field
    def gtfs_providers(self) -> List[GTFSProviderType]:
        """Get all GTFS providers"""
        return GTFSProvider.objects.all()
    
    @field
    def gtfs_provider(self, provider_id: int) -> GTFSProviderType:
        """Get a specific GTFS provider by ID"""
        return GTFSProvider.objects.get(provider_id=provider_id)