from uuid import UUID

from feed.models import FeedPublisher

from .types import (
    CurrentStopSequenceChanged,
    StopIDChanged,
    CurrentStatusChanged,
    CongestionLevelChanged,
    OccupancyStatusChanged,
    OccupancyPercentageChanged,
)


class EventDetector:
    """Group stateless comparisons that emit serialized run-state change events."""

    @staticmethod
    def current_stop_sequence(
        feed_publisher: FeedPublisher,
        run_id: UUID,
        previous_state: int | None,
        current_state: int,
    ) -> dict[str, object] | None:
        """Emit a serialized event when a run's current stop sequence first appears or changes."""
        if previous_state is None or previous_state != current_state:
            return CurrentStopSequenceChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def stop_id(
        feed_publisher: FeedPublisher,
        run_id: UUID,
        previous_state: str | None,
        current_state: str,
    ) -> dict[str, object] | None:
        """Emit a serialized event when a run's stop identifier first appears or changes."""
        if previous_state is None or previous_state != current_state:
            return StopIDChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def current_status(
        feed_publisher: FeedPublisher,
        run_id: UUID,
        previous_state: int | None,
        current_state: int,
    ) -> dict[str, object] | None:
        """Emit a serialized event when a run's vehicle stop status first appears or changes."""
        if previous_state is None or previous_state != current_state:
            return CurrentStatusChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def congestion_level(
        feed_publisher: FeedPublisher,
        run_id: UUID,
        previous_state: int | None,
        current_state: int,
    ) -> dict[str, object] | None:
        """Emit a serialized event when a run's congestion level first appears or changes."""
        if previous_state is None or previous_state != current_state:
            return CongestionLevelChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def occupancy_status(
        feed_publisher: FeedPublisher,
        run_id: UUID,
        previous_state: int | None,
        current_state: int,
    ) -> dict[str, object] | None:
        """Emit a serialized event when a run's occupancy status first appears or changes."""
        if previous_state is None or previous_state != current_state:
            return OccupancyStatusChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def occupancy_percentage(
        feed_publisher: FeedPublisher,
        run_id: UUID,
        previous_state: int | None,
        current_state: int,
    ) -> dict[str, object] | None:
        """Emit a serialized event when a run's occupancy percentage first appears or changes."""
        if previous_state is None or previous_state != current_state:
            return OccupancyPercentageChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None
