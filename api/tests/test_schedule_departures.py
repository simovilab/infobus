from __future__ import annotations

import re
from typing import List

from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

from gtfs.models import Feed, Stop, StopTime


from django.contrib.gis.geos import Point
from datetime import time


class ScheduleDeparturesTests(APITestCase):
    def setUp(self):
        # Minimal dataset for the endpoint
        self.feed = Feed.objects.create(
            feed_id="TEST",
            is_current=True,
        )
        self.stop = Stop.objects.create(
            feed=self.feed,
            stop_id="S1",
            stop_name="Test Stop",
            stop_point=Point(0.0, 0.0),
        )
        # Create StopTime without triggering model save() logic that requires Trip
        StopTime.objects.bulk_create(
            [
                StopTime(
                    feed=self.feed,
                    trip_id="T1",
                    stop_id=self.stop.stop_id,
                    stop_sequence=1,
                    pickup_type=0,
                    drop_off_type=0,
                    arrival_time=time(8, 5, 0),
                    departure_time=time(8, 6, 0),
                )
            ]
        )

    def test_returns_404_when_stop_missing(self):
        url = "/api/schedule/departures/?stop_id=THIS_DOES_NOT_EXIST&limit=1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", resp.json())

    def test_returns_departures_with_expected_shape(self):
        feed = Feed.objects.filter(is_current=True).first() or Feed.objects.first()
        self.assertIsNotNone(feed, "Expected fixture to provide at least one feed")

        # Find a stop_id that actually has stoptimes
        st = StopTime.objects.filter(feed=feed).order_by("departure_time").first()
        self.assertIsNotNone(st, "Expected fixture to provide at least one StopTime")
        stop_id = st.stop_id

        url = f"/api/schedule/departures/?stop_id={stop_id}&time=08:00:00&limit=1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        # Top-level keys
        for key in ["feed_id", "stop_id", "service_date", "from_time", "limit", "departures"]:
            self.assertIn(key, data)

        self.assertIsInstance(data["departures"], list)
        self.assertGreaterEqual(len(data["departures"]), 1)

        item = data["departures"][0]
        for key in [
            "route_id",
            "route_short_name",
            "route_long_name",
            "trip_id",
            "stop_id",
            "headsign",
            "direction_id",
            "arrival_time",
            "departure_time",
        ]:
            self.assertIn(key, item)

        # Time fields formatted HH:MM:SS
        time_pattern = re.compile(r"^\d{2}:\d{2}:\d{2}$")
        if item["arrival_time"] is not None:
            self.assertRegex(item["arrival_time"], time_pattern)
        if item["departure_time"] is not None:
            self.assertRegex(item["departure_time"], time_pattern)

        # from_time string formatted HH:MM:SS
        self.assertRegex(data["from_time"], time_pattern)
