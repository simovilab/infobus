from __future__ import annotations

import re
from unittest.mock import patch, Mock

from rest_framework import status
from rest_framework.test import APITestCase
from django.test import override_settings


class ArrivalsEndpointTests(APITestCase):
    @override_settings(ETAS_API_URL="http://project4.example/etas")
    @patch("api.views.requests.get")
    def test_arrivals_returns_expected_shape(self, mock_get: Mock):
        # Mock upstream Project 4 response
        upstream_payload = [
            {
                "trip_id": "T1",
                "route_id": "R1",
                "route_short_name": "R1",
                "route_long_name": "Ruta 1",
                "trip_headsign": "Terminal",
                "wheelchair_accessible": "UNKNOWN",
                "arrival_time": "08:05:00",
                "departure_time": "08:06:00",
                "in_progress": False,
                "progression": None,
            },
            {
                "trip_id": "T2",
                "route_id": "R2",
                "route_short_name": "R2",
                "route_long_name": "Ruta 2",
                "trip_headsign": "Terminal 2",
                "wheelchair_accessible": "UNKNOWN",
                "arrival_time": "09:05:00",
                "departure_time": "09:06:00",
                "in_progress": False,
                "progression": None,
            },
        ]
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = upstream_payload
        mock_get.return_value = mock_resp

        url = "/api/arrivals/?stop_id=S1&limit=2"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        # Top-level keys
        for key in ["stop_id", "timestamp", "next_arrivals"]:
            self.assertIn(key, data)

        self.assertIsInstance(data["next_arrivals"], list)
        self.assertEqual(len(data["next_arrivals"]), 2)

        item = data["next_arrivals"][0]
        for key in [
            "trip_id",
            "route_id",
            "route_short_name",
            "route_long_name",
            "trip_headsign",
            "wheelchair_accessible",
            "arrival_time",
            "departure_time",
            "in_progress",
        ]:
            self.assertIn(key, item)

        # Time fields formatted HH:MM:SS
        time_pattern = re.compile(r"^\d{2}:\d{2}:\d{2}$")
        if item["arrival_time"] is not None:
            self.assertRegex(item["arrival_time"], time_pattern)
        if item["departure_time"] is not None:
            self.assertRegex(item["departure_time"], time_pattern)

    @override_settings(ETAS_API_URL="http://project4.example/etas")
    @patch("api.views.requests.get")
    def test_arrivals_propagates_upstream_error(self, mock_get: Mock):
        mock_resp = Mock()
        mock_resp.status_code = 503
        mock_resp.json.return_value = {"error": "down"}
        mock_get.return_value = mock_resp

        url = "/api/arrivals/?stop_id=S1&limit=2"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_arrivals_requires_stop_id(self):
        url = "/api/arrivals/?limit=2"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(ETAS_API_URL="http://project4.example/etas")
    @patch("api.views.requests.get")
    def test_arrivals_accepts_wrapped_results_object(self, mock_get: Mock):
        # Upstream returns a dict with results: []
        upstream_payload = {
            "results": [
                {
                    "trip_id": "T1",
                    "route_id": "R1",
                    "route_short_name": "R1",
                    "route_long_name": "Ruta 1",
                    "trip_headsign": "Terminal",
                    "wheelchair_accessible": "UNKNOWN",
                    "arrival_time": "08:05:00",
                    "departure_time": "08:06:00",
                    "in_progress": False,
                    "progression": None,
                }
            ]
        }
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = upstream_payload
        mock_get.return_value = mock_resp

        resp = self.client.get("/api/arrivals/?stop_id=S1&limit=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data.get("next_arrivals", [])), 1)

    @override_settings(ETAS_API_URL="http://project4.example/etas")
    @patch("api.views.requests.get")
    def test_arrivals_handles_unexpected_upstream_structure_as_empty_list(self, mock_get: Mock):
        # Upstream returns an empty dict (no list)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp

        resp = self.client.get("/api/arrivals/?stop_id=S1&limit=5")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIsInstance(data.get("next_arrivals", None), list)
        self.assertEqual(len(data["next_arrivals"]), 0)

    @override_settings(ETAS_API_URL="http://project4.example/etas")
    def test_arrivals_limit_bounds_low(self):
        resp = self.client.get("/api/arrivals/?stop_id=S1&limit=0")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.json())

    @override_settings(ETAS_API_URL="http://project4.example/etas")
    def test_arrivals_limit_bounds_high(self):
        resp = self.client.get("/api/arrivals/?stop_id=S1&limit=101")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.json())

    @override_settings(ETAS_API_URL="http://project4.example/etas")
    def test_arrivals_limit_must_be_integer(self):
        resp = self.client.get("/api/arrivals/?stop_id=S1&limit=abc")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.json())

    def test_arrivals_returns_501_if_not_configured(self):
        # ETAS_API_URL not set; should return 501 when params are otherwise valid
        resp = self.client.get("/api/arrivals/?stop_id=S1&limit=2")
        self.assertEqual(resp.status_code, status.HTTP_501_NOT_IMPLEMENTED)
