"""
Management command to load MBTA routes from real-time feed into database.

Creates Route objects from VehiclePositions protobuf feed without requiring
full GTFS Schedule import.

Usage:
    python manage.py load_mbta_routes
"""

from django.core.management.base import BaseCommand
from gtfs.models import Route, Feed, Agency, GTFSProvider
import requests
from google.transit import gtfs_realtime_pb2


class Command(BaseCommand):
    help = 'Load MBTA routes from real-time feed into database'

    def handle(self, *args, **options):
        self.stdout.write('Loading MBTA routes from VehiclePositions feed...')

        # Get or create MBTA provider
        provider, _ = GTFSProvider.objects.get_or_create(
            code='MBTA',
            defaults={'name': 'Massachusetts Bay Transportation Authority'}
        )
        self.stdout.write(f'Using provider: {provider.name}')

        # Get or create MBTA feed
        feed, created = Feed.objects.get_or_create(
            feed_id='MBTA_FEED',
            defaults={'gtfs_provider': provider}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created feed: {feed.feed_id}'))

        # Get or create MBTA agency
        agency, created = Agency.objects.get_or_create(
            feed=feed,
            agency_id='MBTA',
            defaults={
                'agency_name': 'Massachusetts Bay Transportation Authority',
                'agency_url': 'https://www.mbta.com',
                'agency_timezone': 'America/New_York'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created agency: {agency.agency_id}'))

        # Fetch VehiclePositions protobuf
        url = 'https://cdn.mbta.com/realtime/VehiclePositions.pb'
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch MBTA feed: {e}'))
            return

        # Parse protobuf
        feed_message = gtfs_realtime_pb2.FeedMessage()
        feed_message.ParseFromString(response.content)

        # Extract unique route_ids
        route_ids = set()
        for entity in feed_message.entity:
            if entity.HasField('vehicle'):
                vehicle = entity.vehicle
                if vehicle.HasField('trip') and vehicle.trip.route_id:
                    route_ids.add(vehicle.trip.route_id)

        self.stdout.write(f'Found {len(route_ids)} unique routes: {sorted(route_ids)}')

        # Create Route objects
        created_count = 0
        updated_count = 0

        # MBTA route metadata (partial list - add more as needed)
        route_metadata = {
            'Red': {'short_name': 'Red Line', 'long_name': 'Red Line', 'type': 1},
            'Blue': {'short_name': 'Blue Line', 'long_name': 'Blue Line', 'type': 1},
            'Orange': {'short_name': 'Orange Line', 'long_name': 'Orange Line', 'type': 1},
            'Green-B': {'short_name': 'Green Line B', 'long_name': 'Green Line B Branch', 'type': 0},
            'Green-C': {'short_name': 'Green Line C', 'long_name': 'Green Line C Branch', 'type': 0},
            'Green-D': {'short_name': 'Green Line D', 'long_name': 'Green Line D Branch', 'type': 0},
            'Green-E': {'short_name': 'Green Line E', 'long_name': 'Green Line E Branch', 'type': 0},
        }

        for route_id in sorted(route_ids):
            metadata = route_metadata.get(route_id, {
                'short_name': route_id,
                'long_name': f'Route {route_id}',
                'type': 3  # Default to bus
            })

            route, created = Route.objects.get_or_create(
                feed=feed,
                route_id=route_id,
                defaults={
                    'route_short_name': metadata['short_name'],
                    'route_long_name': metadata['long_name'],
                    'route_type': metadata['type'],
                    'agency_id': agency.agency_id,
                    '_agency': agency
                }
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {route_id} ({metadata["short_name"]})'))
            else:
                updated_count += 1
                self.stdout.write(f'  - Exists: {route_id}')

        self.stdout.write(self.style.SUCCESS(f'\nSummary:'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count} routes'))
        self.stdout.write(f'  Already existed: {updated_count} routes')
        self.stdout.write(self.style.SUCCESS(f'  Total: {len(route_ids)} routes'))
