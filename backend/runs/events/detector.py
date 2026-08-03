from .types import (
    CurrentStopSequenceChanged,
    StopIDChanged,
    CurrentStatusChanged,
    CongestionLevelChanged,
    OccupancyStatusChanged,
    OccupancyPercentageChanged,
)


class EventDetector:
    @staticmethod
    def current_stop_sequence(feed_publisher, run_id, previous_state, current_state):
        """
        Detects if the current stop sequence has changed for a given run.
        """
        if previous_state is None or previous_state != current_state:
            return CurrentStopSequenceChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def stop_id(feed_publisher, run_id, previous_state, current_state):
        """
        Detects if the stop ID has changed for a given run.
        """
        if previous_state is None or previous_state != current_state:
            return StopIDChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def current_status(feed_publisher, run_id, previous_state, current_state):
        if previous_state is None or previous_state != current_state:
            return CurrentStatusChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def congestion_level(feed_publisher, run_id, previous_state, current_state):
        if previous_state is None or previous_state != current_state:
            return CongestionLevelChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def occupancy_status(feed_publisher, run_id, previous_state, current_state):
        if previous_state is None or previous_state != current_state:
            return OccupancyStatusChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None

    @staticmethod
    def occupancy_percentage(feed_publisher, run_id, previous_state, current_state):
        if previous_state is None or previous_state != current_state:
            return OccupancyPercentageChanged(
                transit_system=feed_publisher.transit_system.code,
                run_id=run_id,
                previous_state=previous_state,
                current_state=current_state,
            ).redis_fields()
        return None
