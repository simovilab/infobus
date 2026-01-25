"""
Django management command to create demo data for WebSocket testing.

Creates a simulated trip with realistic Costa Rica locations.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from gtfs.models import GTFSProvider, FeedMessage, TripUpdate
from datetime import timedelta


class Command(BaseCommand):
    help = 'Create demo data for WebSocket testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n🚀 Creating WebSocket Demo Data...\n'))

        # Create or get provider
        provider, created = GTFSProvider.objects.get_or_create(
            code='DEMO',
            defaults={
                'name': 'Demo Transit Provider',
                'timezone': 'America/Costa_Rica',
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created provider: {provider.name}'))
        else:
            self.stdout.write(f'  Using existing provider: {provider.name}')

        # Create feed message
        feed_msg = FeedMessage.objects.create(
            provider=provider,
            entity_type='trip_update',
            feed_message_id=f'demo_{timezone.now().timestamp()}',
            incrementality=0,
            gtfs_realtime_version='2.0',
            timestamp=timezone.now()
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created feed message: {feed_msg.feed_message_id}'))

        # Create demo trip - San José to Heredia route
        now = timezone.now()
        trip = TripUpdate.objects.create(
            feed_message=feed_msg,
            trip_trip_id='DEMO_SJ_HEREDIA_001',
            trip_route_id='ROUTE_001',
            trip_direction_id=0,
            trip_start_time='06:00:00',
            trip_start_date=now.date(),
            vehicle_id='BUS_123',
            vehicle_label='Rápido 123',
            vehicle_license_plate='SJ-12345',
            timestamp=now,
            delay=120,  # 2 minutes delay
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created trip: {trip.trip_trip_id}'))
        
        # Display connection info
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('✅ Demo data created successfully!'))
        self.stdout.write('='*60)
        self.stdout.write('\n📡 WebSocket Connection Info:')
        self.stdout.write(f'   URL: ws://localhost:8000/ws/trips/{trip.trip_trip_id}')
        self.stdout.write(f'   Trip ID: {trip.trip_trip_id}')
        self.stdout.write(f'   Route ID: {trip.trip_route_id}')
        self.stdout.write(f'   Vehicle: {trip.vehicle_label} ({trip.vehicle_license_plate})')
        self.stdout.write(f'   Delay: {trip.delay} seconds')
        
        self.stdout.write('\n🧪 Test Commands:')
        self.stdout.write('   1. Start server: docker-compose up -d web')
        self.stdout.write('   2. Open: http://localhost:8000/websocket/demo/trip/')
        self.stdout.write('   3. Run broadcast test: python manage.py test_broadcast')
        
        self.stdout.write('\n')
