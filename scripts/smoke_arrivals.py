#!/usr/bin/env python3
import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Configure Django
import sys
import pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "datahub.settings")
os.environ.setdefault("ETAS_API_URL", "http://127.0.0.1:8765/")
# Ensure DEBUG parses correctly even if .env has inline comments
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,testserver")

import django
from django.conf import settings

django.setup()

# Simple mock ETAs upstream server (Project 4 replacement for local testing)
class MockETAsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        stop_id = qs.get("stop_id", ["UNKNOWN"])[0]
        limit = int(qs.get("limit", ["2"])[0])
        # Minimal items matching NextTripSerializer's next_arrivals items
        base_item = {
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
        data = [base_item for _ in range(limit)]
        payload = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        # Silence server logs in test output
        return


def run_mock_server():
    httpd = HTTPServer(("127.0.0.1", 8765), MockETAsHandler)
    httpd.serve_forever()

# Start mock ETAs upstream in a background thread
thread = threading.Thread(target=run_mock_server, daemon=True)
thread.start()

# Now call the Django endpoint in-process using DRF's APIClient
from rest_framework.test import APIClient

client = APIClient()
resp = client.get("/api/arrivals/", {"stop_id": "S1", "limit": 2}, format="json")
print("STATUS:", resp.status_code)
try:
    print("JSON:", json.dumps(resp.json(), ensure_ascii=False))
except Exception as e:
    print("ERROR reading JSON:", e, "\nRaw:", getattr(resp, 'content', b'')[:500])
