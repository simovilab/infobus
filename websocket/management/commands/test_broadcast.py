"""
Django management command to simulate live WebSocket broadcasts.

Simulates bus movement by updating trip data and broadcasting to connected clients.
"""

import asyncio
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from channels.layers import get_channel_layer
from gtfs.models import TripUpdate
from websocket.serializers.gtfs import serialize_trip_update


class Command(BaseCommand):
    help = 'Simulate real-time WebSocket broadcasts for demo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--trip-id',
            type=str,
            default='DEMO_SJ_HEREDIA_001',
            help='Trip ID to broadcast updates for'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Seconds between broadcasts'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of updates to send (0 = infinite)'
        )

    def handle(self, *args, **options):
        trip_id = options['trip_id']
        interval = options['interval']
        count = options['count']

        self.stdout.write(self.style.SUCCESS('\n🚀 Starting WebSocket Broadcast Simulator\n'))
        self.stdout.write(f'   Trip ID: {trip_id}')
        self.stdout.write(f'   Interval: {interval}s')
        self.stdout.write(f'   Updates: {"∞" if count == 0 else count}')
        self.stdout.write('\n' + '='*60)
        
        # Run async loop
        asyncio.run(self.broadcast_loop(trip_id, interval, count))

    async def broadcast_loop(self, trip_id, interval, count):
        """Async loop to broadcast updates."""
        channel_layer = get_channel_layer()
        iteration = 0
        
        try:
            while count == 0 or iteration < count:
                iteration += 1
                
                # Get trip from database
                try:
                    trip = await self.get_trip(trip_id)
                except TripUpdate.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'\n❌ Trip {trip_id} not found!'))
                    self.stdout.write('   Run: python manage.py demo_websocket_data')
                    return
                
                # Simulate movement: random delay changes
                old_delay = trip.delay or 0
                # Random change between -30s and +60s
                delay_change = random.randint(-30, 60)
                new_delay = max(0, old_delay + delay_change)
                
                # Update trip
                trip.delay = new_delay
                trip.timestamp = timezone.now()
                await self.save_trip(trip)
                
                # Serialize data (must be sync)
                data = await self.serialize_trip(trip)
                
                # Broadcast to WebSocket group
                group_name = f'trip_{trip_id}'
                await channel_layer.group_send(
                    group_name,
                    {
                        'type': 'trip.update',
                        'trip_id': trip_id,
                        'data': data,
                    }
                )
                
                # Log
                delay_emoji = '🟢' if new_delay < 60 else '🟡' if new_delay < 180 else '🔴'
                self.stdout.write(
                    f'{delay_emoji} [{iteration:3d}] Broadcast: delay={new_delay}s '
                    f'(Δ{delay_change:+3d}s) | timestamp={trip.timestamp.strftime("%H:%M:%S")}'
                )
                
                # Wait before next update
                if count == 0 or iteration < count:
                    await asyncio.sleep(interval)
                    
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n\n⏸️  Broadcast stopped by user'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n\n❌ Error: {e}'))
            raise
        finally:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS(f'✅ Sent {iteration} broadcasts\n'))
    
    async def get_trip(self, trip_id):
        """Get trip from database (async)."""
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def _get():
            return TripUpdate.objects.select_related('feed_message').get(
                trip_trip_id=trip_id
            )
        
        return await _get()
    
    async def save_trip(self, trip):
        """Save trip to database (async)."""
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def _save():
            trip.save()
        
        await _save()
    
    async def serialize_trip(self, trip):
        """Serialize trip data (async)."""
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def _serialize():
            return serialize_trip_update(trip, include_stops=True, include_shape=False)
        
        return await _serialize()
