"""
Django management command to simulate live WebSocket broadcasts.

Simulates bus movement by updating trip/route data and broadcasting to connected clients.
Supports both trip-level and route-level broadcasts.
"""

import asyncio
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from channels.layers import get_channel_layer
from gtfs.models import TripUpdate, VehiclePosition
from websocket.serializers.gtfs import serialize_trip_update


class Command(BaseCommand):
    help = 'Simulate real-time WebSocket broadcasts for demo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='trip',
            choices=['trip', 'route'],
            help='Type of broadcast: trip or route (default: trip)'
        )
        parser.add_argument(
            '--trip-id',
            type=str,
            default='DEMO_SJ_HEREDIA_001',
            help='Trip ID to broadcast updates for (when --type=trip)'
        )
        parser.add_argument(
            '--route-id',
            type=str,
            default='DEMO_ROUTE_001',
            help='Route ID to broadcast updates for (when --type=route)'
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
        broadcast_type = options['type']
        trip_id = options['trip_id']
        route_id = options['route_id']
        interval = options['interval']
        count = options['count']

        self.stdout.write(self.style.SUCCESS('\n🚀 Starting WebSocket Broadcast Simulator\n'))
        self.stdout.write(f'   Type: {broadcast_type}')
        
        if broadcast_type == 'trip':
            self.stdout.write(f'   Trip ID: {trip_id}')
        else:
            self.stdout.write(f'   Route ID: {route_id}')
            
        self.stdout.write(f'   Interval: {interval}s')
        self.stdout.write(f'   Updates: {"∞" if count == 0 else count}')
        self.stdout.write('\n' + '='*60)
        
        # Run async loop
        if broadcast_type == 'trip':
            asyncio.run(self.broadcast_trip_loop(trip_id, interval, count))
        else:
            asyncio.run(self.broadcast_route_loop(route_id, interval, count))

    async def broadcast_trip_loop(self, trip_id, interval, count):
        """Async loop to broadcast trip updates."""
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
    
    async def broadcast_route_loop(self, route_id, interval, count):
        """Async loop to broadcast route updates."""
        channel_layer = get_channel_layer()
        iteration = 0
        
        try:
            while count == 0 or iteration < count:
                iteration += 1
                
                # Get vehicles for this route
                vehicles = await self.get_route_vehicles(route_id)
                
                if not vehicles:
                    self.stdout.write(self.style.ERROR(f'\n❌ No vehicles found for route {route_id}!'))
                    self.stdout.write(f'   Run: python manage.py demo_route_data --route {route_id}')
                    return
                
                # Update each vehicle position slightly
                updated_count = await self.update_vehicle_positions(vehicles)
                
                # Broadcast to all route groups (both directions + combined)
                groups = [
                    f'route_{route_id}',
                    f'route_{route_id}_dir_0',
                    f'route_{route_id}_dir_1',
                ]
                
                for group_name in groups:
                    await channel_layer.group_send(
                        group_name,
                        {
                            'type': 'route.update',
                            'route_id': route_id,
                        }
                    )
                
                # Log
                self.stdout.write(
                    f'🚌 [{iteration:3d}] Broadcast: route={route_id} | '
                    f'vehicles={len(vehicles)} | updated={updated_count} | '
                    f'timestamp={timezone.now().strftime("%H:%M:%S")}'
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
    
    async def get_route_vehicles(self, route_id):
        """Get all vehicles for a route (async)."""
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def _get():
            return list(VehiclePosition.objects.filter(
                vehicle_trip_route_id=route_id
            ).select_related('feed_message'))
        
        return await _get()
    
    async def update_vehicle_positions(self, vehicles):
        """Update vehicle positions with small random changes (async)."""
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def _update():
            updated = 0
            for vehicle in vehicles:
                # Small random movement (max ~200m)
                lat_change = random.uniform(-0.002, 0.002)
                lng_change = random.uniform(-0.002, 0.002)
                
                vehicle.vehicle_position_latitude += lat_change
                vehicle.vehicle_position_longitude += lng_change
                
                # Update bearing and speed
                bearing_change = random.uniform(-15, 15)
                vehicle.vehicle_position_bearing = (
                    (vehicle.vehicle_position_bearing or 0) + bearing_change
                ) % 360
                
                speed_change = random.uniform(-5, 5)
                vehicle.vehicle_position_speed = max(
                    0, 
                    min(80, (vehicle.vehicle_position_speed or 30) + speed_change)
                )
                
                vehicle.vehicle_timestamp = timezone.now()
                vehicle.save()
                updated += 1
            
            return updated
        
        return await _update()
