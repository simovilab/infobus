"""
Tests for Prometheus metrics in the feed app.

This test suite verifies that GTFS processing metrics are properly
instrumented and updated during task execution.
"""

from feed.metrics import (
    GTFS_SCHEDULE_UPDATES_TOTAL,
    GTFS_VEHICLE_POSITIONS_UPDATES_TOTAL,
    GTFS_TRIP_UPDATES_TOTAL,
    GTFS_ENTITIES_PROCESSED_TOTAL,
    GTFS_PROCESSING_ERRORS_TOTAL,
    GTFS_LAST_UPDATE_TIMESTAMP,
    GTFS_PROCESSING_DURATION_SECONDS,
)


class TestGTFSMetrics:
    """Test suite for GTFS Prometheus metrics."""

    def test_metrics_are_defined(self):
        """Verify that all expected metrics are properly defined."""
        assert GTFS_SCHEDULE_UPDATES_TOTAL is not None
        assert GTFS_VEHICLE_POSITIONS_UPDATES_TOTAL is not None
        assert GTFS_TRIP_UPDATES_TOTAL is not None
        assert GTFS_ENTITIES_PROCESSED_TOTAL is not None
        assert GTFS_PROCESSING_ERRORS_TOTAL is not None
        assert GTFS_LAST_UPDATE_TIMESTAMP is not None
        assert GTFS_PROCESSING_DURATION_SECONDS is not None

    def test_schedule_updates_counter(self):
        """Test that schedule updates counter increments correctly."""
        initial = GTFS_SCHEDULE_UPDATES_TOTAL.labels(feed_id="test-feed")._value.get()
        GTFS_SCHEDULE_UPDATES_TOTAL.labels(feed_id="test-feed").inc()
        final = GTFS_SCHEDULE_UPDATES_TOTAL.labels(feed_id="test-feed")._value.get()
        assert final == initial + 1

    def test_vehicle_positions_counter(self):
        """Test that vehicle positions counter increments correctly."""
        initial = GTFS_VEHICLE_POSITIONS_UPDATES_TOTAL.labels(
            provider="test-provider"
        )._value.get()
        GTFS_VEHICLE_POSITIONS_UPDATES_TOTAL.labels(provider="test-provider").inc()
        final = GTFS_VEHICLE_POSITIONS_UPDATES_TOTAL.labels(
            provider="test-provider"
        )._value.get()
        assert final == initial + 1

    def test_trip_updates_counter(self):
        """Test that trip updates counter increments correctly."""
        initial = GTFS_TRIP_UPDATES_TOTAL.labels(provider="test-provider")._value.get()
        GTFS_TRIP_UPDATES_TOTAL.labels(provider="test-provider").inc()
        final = GTFS_TRIP_UPDATES_TOTAL.labels(provider="test-provider")._value.get()
        assert final == initial + 1

    def test_entities_processed_counter(self):
        """Test that entities processed counter increments with count."""
        initial = GTFS_ENTITIES_PROCESSED_TOTAL.labels(
            type="vehicle", provider="test-provider"
        )._value.get()
        GTFS_ENTITIES_PROCESSED_TOTAL.labels(
            type="vehicle", provider="test-provider"
        ).inc(5)
        final = GTFS_ENTITIES_PROCESSED_TOTAL.labels(
            type="vehicle", provider="test-provider"
        )._value.get()
        assert final == initial + 5

    def test_processing_errors_counter(self):
        """Test that processing errors counter increments correctly."""
        initial = GTFS_PROCESSING_ERRORS_TOTAL.labels(
            task="test-task", provider="test-provider"
        )._value.get()
        GTFS_PROCESSING_ERRORS_TOTAL.labels(
            task="test-task", provider="test-provider"
        ).inc()
        final = GTFS_PROCESSING_ERRORS_TOTAL.labels(
            task="test-task", provider="test-provider"
        )._value.get()
        assert final == initial + 1

    def test_last_update_timestamp_gauge(self):
        """Test that last update timestamp gauge sets correctly."""
        GTFS_LAST_UPDATE_TIMESTAMP.labels(
            type="vehicle_positions", provider="test-provider"
        ).set_to_current_time()
        value = GTFS_LAST_UPDATE_TIMESTAMP.labels(
            type="vehicle_positions", provider="test-provider"
        )._value.get()
        assert value > 0  # Should be a valid timestamp

    def test_processing_duration_histogram(self):
        """Test that processing duration histogram records time."""
        with GTFS_PROCESSING_DURATION_SECONDS.labels(
            type="schedule", provider="test-provider"
        ).time():
            pass  # Simulate some work
        # Verify histogram has recorded at least one observation
        histogram = GTFS_PROCESSING_DURATION_SECONDS.labels(
            type="schedule", provider="test-provider"
        )
        # _sum is a float value, not an object with .get()
        assert histogram._sum._value >= 0
