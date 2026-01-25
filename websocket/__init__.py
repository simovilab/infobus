"""
WebSocket Module for GTFS-Realtime Broadcasting

This module provides WebSocket consumers and serializers for real-time
transit data broadcasting following the AsyncAPI 3.0 specification.

Components:
- consumers: WebSocket consumers for trip and route updates
- serializers: GTFS-Realtime model to JSON serializers
- tasks: Celery tasks for broadcasting updates
- routing: WebSocket URL routing configuration

Author: Brandon Trigueros Lara
Project: TCU - SIMOVI Lab, Universidad de Costa Rica
Date: January 2026
"""

__version__ = "1.0.0"
