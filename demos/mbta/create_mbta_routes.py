#!/usr/bin/env python
"""Create MBTA routes in the database."""

import django
import os
import sys

# Add the project directory to the path
sys.path.insert(0, '/app')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datahub.settings')
django.setup()

from gtfs.models import Feed, Agency, Route

# First, ensure MBTA feed and agency exist
feed, feed_created = Feed.objects.get_or_create(
    feed_id='mbta',
    defaults={
        'is_current': True
    }
)

if feed_created:
    print('✓ Created Feed: mbta')
else:
    print('- Feed already exists: mbta')

agency, agency_created = Agency.objects.get_or_create(
    feed=feed,
    agency_id='1',
    defaults={
        'agency_name': 'Massachusetts Bay Transportation Authority',
        'agency_url': 'https://www.mbta.com',
        'agency_timezone': 'America/New_York',
        'agency_lang': 'en'
    }
)

if agency_created:
    print('✓ Created Agency: MBTA')
else:
    print('- Agency already exists: MBTA')

# Now create routes
# route_type: 0=Tram/Light rail, 1=Subway/Metro, 3=Bus
routes = [
    ('Red', 'Red Line', 'Red', 1),
    ('Blue', 'Blue Line', 'Blue', 1),
    ('Orange', 'Orange Line', 'Orange', 1),
    ('Green-B', 'Green Line B', 'Green-B', 0),
    ('Green-C', 'Green Line C', 'Green-C', 0),
    ('Green-D', 'Green Line D', 'Green-D', 0),
    ('Green-E', 'Green Line E', 'Green-E', 0),
    ('1', 'Route 1', '1', 3),
    ('28', 'Route 28', '28', 3),
    ('39', 'Route 39', '39', 3),
]

created = 0
updated = 0

for route_id, long_name, short_name, route_type in routes:
    route, is_new = Route.objects.get_or_create(
        feed=feed,
        route_id=route_id,
        defaults={
            'route_short_name': short_name,
            'route_long_name': long_name,
            'route_type': route_type,
            'agency_id': '1'
        }
    )
    
    if is_new:
        created += 1
        print(f'✓ Created: {route_id} - {long_name}')
    else:
        updated += 1
        print(f'- Already exists: {route_id} - {long_name}')

print(f'\n📊 Summary:')
print(f'   Created: {created}')
print(f'   Already existed: {updated}')
print(f'   Total routes: {len(routes)}')
