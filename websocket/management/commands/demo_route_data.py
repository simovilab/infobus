"""
Management command to create demo data for route WebSocket testing.

Creates:
- Route in GTFS Schedule
- Multiple VehiclePosition objects for that route
- Both directions (0 and 1)
- Realistic positions in San José, Costa Rica

Usage:
    python manage.py demo_route_data
    python manage.py demo_route_data --route CUSTOM_001 --vehicles 8
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from gtfs.models import Route, VehiclePosition, FeedMessage, GTFSProvider, Feed, Agency


class Command(BaseCommand):
    help = 'Create demo route data for WebSocket testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--route',
            type=str,
            default='DEMO_ROUTE_001',
            help='Route ID to create (default: DEMO_ROUTE_001)'
        )
        parser.add_argument(
            '--vehicles',
            type=int,
            default=6,
            help='Number of vehicles to create (default: 6)'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Delete existing demo data first'
        )

    def handle(self, *args, **options):
        route_id = options['route']
        vehicle_count = options['vehicles']
        clean = options['clean']

        # Clean existing demo data if requested
        if clean:
            self.stdout.write('Cleaning existing demo data...')
            Route.objects.filter(route_id__startswith='DEMO_').delete()
            VehiclePosition.objects.filter(vehicle_trip_route_id__startswith='DEMO_').delete()
            FeedMessage.objects.filter(feed_message_id__startswith='DEMO_').delete()
            self.stdout.write(self.style.SUCCESS('✓ Cleaned'))

        # Get or create provider
        provider, _ = GTFSProvider.objects.get_or_create(
            code='DEMO',
            defaults={'name': 'Demo Provider'}
        )

        # Create or get feed
        feed, created_feed = Feed.objects.get_or_create(
            feed_id='DEMO_FEED',
            defaults={'gtfs_provider': provider}
        )
        if created_feed:
            self.stdout.write(f'Created feed: {feed.feed_id}')

        # Create or get agency
        agency, created_agency = Agency.objects.get_or_create(
            feed=feed,
            agency_id='DEMO_AGENCY',
            defaults={
                'agency_name': 'Demo Transit Agency',
                'agency_url': 'https://example.com',
                'agency_timezone': 'America/Costa_Rica'
            }
        )
        if created_agency:
            self.stdout.write(f'Created agency: {agency.agency_id}')

        # Create feed message
        feed_msg, created = FeedMessage.objects.get_or_create(
            feed_message_id=f'DEMO_FEED_{route_id}',
            defaults={
                'provider': provider,
                'entity_type': 'vehicle_position',
                'incrementality': 'FULL_DATASET',
                'gtfs_realtime_version': '2.0'
            }
        )
        if created:
            self.stdout.write(f'Created feed message: {feed_msg.feed_message_id}')

        # Create route in GTFS Schedule
        route, created = Route.objects.get_or_create(
            feed=feed,
            route_id=route_id,
            defaults={
                'agency_id': agency.agency_id,
                'route_short_name': route_id.replace('DEMO_ROUTE_', 'R'),
                'route_long_name': f'Demo Route {route_id}',
                'route_type': 3,  # Bus
                'route_color': '667eea',
                'route_text_color': 'ffffff'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created route: {route_id}'))
        else:
            self.stdout.write(f'Route already exists: {route_id}')

        # San José, Costa Rica - sample route coordinates
        # From Centro to Heredia (approximate)
        base_coords = [
            (9.9281, -84.0907),  # Centro San José
            (9.9325, -84.0850),
            (9.9370, -84.0800),
            (9.9400, -84.0750),
            (9.9435, -84.0700),
            (9.9470, -84.0650),  # Towards Heredia
        ]

        # Create vehicles
        created_count = 0
        now = timezone.now()

        for i in range(vehicle_count):
            direction_id = i % 2  # Alternate between directions
            
            # Pick a random position along the route
            base_idx = random.randint(0, len(base_coords) - 1)
            base_lat, base_lng = base_coords[base_idx]
            
            # Add small random offset
            lat = base_lat + random.uniform(-0.002, 0.002)
            lng = base_lng + random.uniform(-0.002, 0.002)
            
            # Random bearing based on direction
            if direction_id == 0:
                bearing = random.uniform(30, 60)  # NE direction
            else:
                bearing = random.uniform(210, 240)  # SW direction
            
            # Random speed
            speed = random.uniform(15, 45)  # km/h
            
            vehicle_id = f'DEMO_BUS_{route_id}_{i+1:03d}'
            trip_id = f'DEMO_TRIP_{route_id}_{i+1:03d}'
            
            vehicle_pos, created = VehiclePosition.objects.get_or_create(
                entity_id=f'DEMO_VP_{route_id}_{i+1:03d}',
                defaults={
                    'feed_message': feed_msg,
                    'vehicle_trip_route_id': route_id,
                    'vehicle_trip_trip_id': trip_id,
                    'vehicle_trip_direction_id': direction_id,
                    'vehicle_vehicle_id': vehicle_id,
                    'vehicle_vehicle_label': f'{100 + i}',
                    'vehicle_position_latitude': lat,
                    'vehicle_position_longitude': lng,
                    'vehicle_position_bearing': bearing,
                    'vehicle_position_speed': speed,
                    'vehicle_timestamp': now - timedelta(seconds=random.randint(0, 60)),
                    'vehicle_current_status': 'IN_TRANSIT_TO'
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    f'  ✓ Vehicle {i+1}/{vehicle_count}: {vehicle_id} '
                    f'(dir={direction_id}, lat={lat:.4f}, lng={lng:.4f})'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Demo route data created successfully!\n'
                f'   Route: {route_id}\n'
                f'   Vehicles: {created_count} created\n'
                f'   Direction 0: {vehicle_count // 2} vehicles\n'
                f'   Direction 1: {vehicle_count - vehicle_count // 2} vehicles\n'
            )
        )
        
        self.stdout.write('\nTest the WebSocket:')
        self.stdout.write(f'  All directions: ws://localhost:8000/ws/route/{route_id}/')
        self.stdout.write(f'  Direction 0:    ws://localhost:8000/ws/route/{route_id}/direction/0/')
        self.stdout.write(f'  Direction 1:    ws://localhost:8000/ws/route/{route_id}/direction/1/')
        
        self.stdout.write('\nView demo page:')
        self.stdout.write('  http://localhost:8000/websocket/demo/route/')
        
        self.stdout.write('\nSimulate broadcasts:')
        self.stdout.write(f'  python manage.py test_broadcast --type route --route_id {route_id}')
