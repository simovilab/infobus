from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.gis.geos import Point

from gtfs.models import Feed, Stop


FUSEKI_URL = os.environ.get("FUSEKI_TEST_URL", "http://fuseki:3030")
DATASET = os.environ.get("FUSEKI_TEST_DATASET", "dataset")
SPARQL_ENDPOINT = f"{FUSEKI_URL}/{DATASET}/sparql"
DATA_ENDPOINT = f"{FUSEKI_URL}/{DATASET}/data?default"


class FusekiScheduleIntegrationTests(APITestCase):
    @override_settings(FUSEKI_ENABLED=True, FUSEKI_ENDPOINT=SPARQL_ENDPOINT)
    def test_fuseki_departures_via_dal(self):
        # Ensure DB has feed and stop for validation in API view
        feed = Feed.objects.create(feed_id="TEST", is_current=True)
        Stop.objects.create(feed=feed, stop_id="S1", stop_name="Stop 1", stop_point=Point(0.0, 0.0))

        # Wait for Fuseki to be ready
        self._wait_for_fuseki_ready()

        # Load tiny TTL into dataset (default graph)
        ttl_path = Path(__file__).parent / "data" / "fuseki_sample.ttl"
        with open(ttl_path, "rb") as f:
            r = requests.post(DATA_ENDPOINT, data=f.read(), headers={"Content-Type": "text/turtle"}, timeout=10, auth=("admin", "admin"))
            # Some images allow anonymous writes; if 401, try again without auth
            if r.status_code == 401:
                r = requests.post(DATA_ENDPOINT, data=open(ttl_path, "rb").read(), headers={"Content-Type": "text/turtle"}, timeout=10)
            r.raise_for_status()

        # Call the API endpoint; service_date in TTL is far future (2099-01-01), so pass date to match
        url = "/api/schedule/departures/?feed_id=TEST&stop_id=S1&date=2099-01-01&time=08:00:00&limit=1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        data = resp.json()
        self.assertEqual(data["feed_id"], "TEST")
        self.assertEqual(data["stop_id"], "S1")
        self.assertEqual(data["limit"], 1)
        self.assertEqual(len(data["departures"]), 1)
        item = data["departures"][0]
        # Validate enriched fields
        self.assertEqual(item["route_id"], "R1")
        self.assertEqual(item["route_short_name"], "R1")
        self.assertEqual(item["route_long_name"], "Ruta 1")
        self.assertEqual(item["trip_id"], "T1")
        self.assertEqual(item["arrival_time"], "08:05:00")
        self.assertEqual(item["departure_time"], "08:06:00")

    def _wait_for_fuseki_ready(self, timeout_seconds: int = 20):
        start = time.time()
        while time.time() - start < timeout_seconds:
            try:
                # ASK {} to ensure SPARQL endpoint is responsive
                r = requests.post(SPARQL_ENDPOINT, data=b"ASK {}", headers={"Content-Type": "application/sparql-query"}, timeout=3)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError("Fuseki SPARQL endpoint did not become ready in time")
