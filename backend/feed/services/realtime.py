from feed.models import (
    FeedPublisher,
    FeedMessage,
    VehiclePosition,
    TripUpdate,
    StopTimeUpdate,
    Alert,
    TimeRange,
    EntitySelector,
    TripDescriptor,
    ModifiedTripSelector,
    TranslatedString,
    Translation,
    TranslatedImage,
    LocalizedImage,
)
from google.protobuf.message import Message
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from gtfs.utils import gtfs_time, gtfs_date, gtfs_timestamp
import pytz
from django.contrib.gis.geos import Point
from django.db import transaction


def save_vehicle_positions_to_database(
    feed_publisher: FeedPublisher,
    vehicle_positions: gtfs_rt.FeedMessage,
) -> None:
    """Persist a GTFS Realtime vehicle-position feed message and its entities."""
    # Save FeedMessage object
    feed_message = FeedMessage(
        feed_message_id=f"{feed_publisher.code}-vehicle-{vehicle_positions.header.timestamp}",
        publisher=feed_publisher,
        entity_type="vehicle",
        timestamp=gtfs_timestamp(
            vehicle_positions.header.timestamp,
            timezone=pytz.timezone(feed_publisher.timezone),
        ),
        incrementality=vehicle_positions.header.incrementality,
        gtfs_realtime_version=vehicle_positions.header.gtfs_realtime_version,
    )
    feed_message.save()

    # Save VehiclePosition objects
    vehicle_positions_to_create = []
    entities = vehicle_positions.entity
    for entity in entities:
        v = entity.vehicle
        vehicle_positions_to_create.append(
            VehiclePosition(
                entity_id=entity.id,
                feed_message=feed_message,
                trip_trip_id=v.trip.trip_id if v.trip.HasField("trip_id") else None,
                trip_route_id=v.trip.route_id if v.trip.HasField("route_id") else None,
                trip_direction_id=v.trip.direction_id
                if v.trip.HasField("direction_id")
                else None,
                trip_start_time=gtfs_time(v.trip.start_time)
                if v.trip.HasField("start_time")
                else None,
                trip_start_date=gtfs_date(v.trip.start_date)
                if v.trip.HasField("start_date")
                else None,
                trip_schedule_relationship=v.trip.schedule_relationship
                if v.trip.HasField("schedule_relationship")
                else None,
                vehicle_id=v.vehicle.id if v.vehicle.HasField("id") else None,
                vehicle_label=v.vehicle.label if v.vehicle.HasField("label") else None,
                vehicle_license_plate=v.vehicle.license_plate
                if v.vehicle.HasField("license_plate")
                else None,
                position_latitude=v.position.latitude
                if v.position.HasField("latitude")
                else None,
                position_longitude=v.position.longitude
                if v.position.HasField("longitude")
                else None,
                position_point=Point(v.position.longitude, v.position.latitude)
                if v.position.HasField("longitude") and v.position.HasField("latitude")
                else None,
                position_bearing=v.position.bearing
                if v.position.HasField("bearing")
                else None,
                position_odometer=v.position.odometer
                if v.position.HasField("odometer")
                else None,
                position_speed=v.position.speed
                if v.position.HasField("speed")
                else None,
                current_stop_sequence=v.current_stop_sequence
                if v.current_stop_sequence is not None
                else None,
                stop_id=v.stop_id if v.stop_id is not None else None,
                current_status=v.current_status
                if v.current_status is not None
                else None,
                timestamp=gtfs_timestamp(v.timestamp)
                if v.HasField("timestamp")
                else None,
                congestion_level=v.congestion_level
                if v.HasField("congestion_level")
                else None,
                occupancy_status=v.occupancy_status
                if v.HasField("occupancy_status")
                else None,
                occupancy_percentage=v.occupancy_percentage
                if v.HasField("occupancy_percentage")
                else None,
            )
        )

    if vehicle_positions_to_create:
        VehiclePosition.objects.bulk_create(
            vehicle_positions_to_create,
            batch_size=1000,
        )


def save_trip_updates_to_database(
    feed_publisher: FeedPublisher,
    trip_updates: gtfs_rt.FeedMessage,
) -> None:
    """Persist a GTFS Realtime trip-update feed message with its stop-time updates."""
    # Save FeedMessage object
    feed_message = FeedMessage(
        feed_message_id=f"{feed_publisher.code}-trip_updates-{trip_updates.header.timestamp}",
        publisher=feed_publisher,
        entity_type="trip_update",
        timestamp=gtfs_timestamp(
            trip_updates.header.timestamp,
            timezone=pytz.timezone(feed_publisher.timezone),
        ),
        incrementality=trip_updates.header.incrementality,
        gtfs_realtime_version=trip_updates.header.gtfs_realtime_version,
    )
    feed_message.save()

    # Save TripUpdate entities and their related StopTimeUpdate objects
    trip_updates_to_create = []
    stop_time_updates_by_trip_index = []
    entities = trip_updates.entity
    for entity in entities:
        t = entity.trip_update
        trip_updates_to_create.append(
            TripUpdate(
                entity_id=entity.id,
                feed_message=feed_message,
                trip_trip_id=t.trip.trip_id if t.trip.HasField("trip_id") else None,
                trip_route_id=t.trip.route_id if t.trip.HasField("route_id") else None,
                trip_direction_id=t.trip.direction_id
                if t.trip.HasField("direction_id")
                else None,
                trip_start_time=gtfs_time(t.trip.start_time)
                if t.trip.HasField("start_time")
                else None,
                trip_start_date=gtfs_date(t.trip.start_date)
                if t.trip.HasField("start_date")
                else None,
                trip_schedule_relationship=t.trip.schedule_relationship
                if t.trip.HasField("schedule_relationship")
                else None,
                vehicle_id=t.vehicle.id if t.vehicle.HasField("id") else None,
                vehicle_label=t.vehicle.label if t.vehicle.HasField("label") else None,
                vehicle_license_plate=t.vehicle.license_plate
                if t.vehicle.HasField("license_plate")
                else None,
                timestamp=gtfs_timestamp(t.timestamp)
                if t.HasField("timestamp")
                else None,
                delay=t.delay if t.HasField("delay") else None,
            )
        )

        stop_time_updates_by_trip_index.append(list(t.stop_time_update))

    if trip_updates_to_create:
        with transaction.atomic():
            created_trip_updates = TripUpdate.objects.bulk_create(
                trip_updates_to_create,
                batch_size=1000,
            )

            stop_time_updates_to_create = []
            for trip_update, stop_time_updates in zip(
                created_trip_updates, stop_time_updates_by_trip_index
            ):
                for stu in stop_time_updates:
                    stop_time_updates_to_create.append(
                        StopTimeUpdate(
                            trip_update=trip_update,
                            stop_sequence=stu.stop_sequence
                            if stu.HasField("stop_sequence")
                            else None,
                            stop_id=stu.stop_id if stu.HasField("stop_id") else None,
                            arrival_delay=stu.arrival.delay
                            if stu.arrival.HasField("delay")
                            else None,
                            arrival_time=gtfs_timestamp(stu.arrival.time)
                            if stu.arrival.HasField("time")
                            else None,
                            arrival_uncertainty=stu.arrival.uncertainty
                            if stu.arrival.HasField("uncertainty")
                            else None,
                            departure_delay=stu.departure.delay
                            if stu.departure.HasField("delay")
                            else None,
                            departure_time=gtfs_timestamp(stu.departure.time)
                            if stu.departure.HasField("time")
                            else None,
                            departure_uncertainty=stu.departure.uncertainty
                            if stu.departure.HasField("uncertainty")
                            else None,
                            schedule_relationship=stu.schedule_relationship
                            if stu.HasField("schedule_relationship")
                            else None,
                        )
                    )

            if stop_time_updates_to_create:
                StopTimeUpdate.objects.bulk_create(
                    stop_time_updates_to_create,
                    batch_size=2000,
                )


def has_optional_field(message: Message, field_name: str) -> bool:
    """Return whether a protobuf message declares and sets an optional field."""
    descriptor = getattr(message, "DESCRIPTOR", None)
    if descriptor is None or field_name not in descriptor.fields_by_name:
        return False
    try:
        return message.HasField(field_name)
    except ValueError:
        return False


def save_alerts_to_database(
    feed_publisher: FeedPublisher,
    alerts: gtfs_rt.FeedMessage,
) -> None:
    """Persist an alerts feed message and any previously unseen alerts with their nested data."""
    # Save FeedMessage object
    feed_message = FeedMessage(
        feed_message_id=f"{feed_publisher.code}-alerts-{alerts.header.timestamp}",
        publisher=feed_publisher,
        entity_type="alert",
        timestamp=gtfs_timestamp(
            alerts.header.timestamp,
            timezone=pytz.timezone(feed_publisher.timezone),
        ),
        incrementality=alerts.header.incrementality,
        gtfs_realtime_version=alerts.header.gtfs_realtime_version,
    )
    feed_message.save()

    # Save Alert entities and their related InformedEntity, TripDescriptor, ModifiedTripSelector, TranslatedString, Translation, and TranslatedImage objects
    entities = alerts.entity
    incoming_entity_ids = [entity.id for entity in entities]
    existing_entity_ids = set(
        Alert.objects.filter(entity_id__in=incoming_entity_ids).values_list(
            "entity_id", flat=True
        )
    )

    for entity in entities:
        if entity.id in existing_entity_ids:
            continue

        a = entity.alert
        with transaction.atomic():
            alert = Alert.objects.create(
                entity_id=entity.id,
                feed_message=feed_message,
                cause=a.cause if a.HasField("cause") else None,
                effect=a.effect if a.HasField("effect") else None,
                severity_level=a.severity_level
                if a.HasField("severity_level")
                else None,
            )

            # active_period can contain multiple ranges per alert.
            time_ranges_to_create = [
                TimeRange(
                    alert=alert,
                    field_name="active_period",
                    start=gtfs_timestamp(period.start)
                    if period.HasField("start")
                    else None,
                    end=gtfs_timestamp(period.end) if period.HasField("end") else None,
                )
                for period in a.active_period
            ]
            if time_ranges_to_create:
                TimeRange.objects.bulk_create(time_ranges_to_create, batch_size=500)

            # informed_entity can contain multiple selectors per alert.
            entity_selectors_to_create = []
            trip_protos = []
            for ie in a.informed_entity:
                entity_selectors_to_create.append(
                    EntitySelector(
                        alert=alert,
                        field_name="informed_entity",
                        agency_id=ie.agency_id if ie.HasField("agency_id") else None,
                        route_id=ie.route_id if ie.HasField("route_id") else None,
                        route_type=ie.route_type if ie.HasField("route_type") else None,
                        direction_id=ie.direction_id
                        if ie.HasField("direction_id")
                        else None,
                        stop_id=ie.stop_id if ie.HasField("stop_id") else None,
                    )
                )
                trip_protos.append(ie.trip if ie.HasField("trip") else None)

            if entity_selectors_to_create:
                created_selectors = EntitySelector.objects.bulk_create(
                    entity_selectors_to_create, batch_size=500
                )

                trip_descriptors_to_create = []
                modified_trip_protos = []
                for es, trip_proto in zip(created_selectors, trip_protos):
                    if trip_proto is None:
                        continue
                    trip_descriptors_to_create.append(
                        TripDescriptor(
                            entity_selector=es,
                            field_name="trip",
                            trip_id=trip_proto.trip_id
                            if trip_proto.HasField("trip_id")
                            else None,
                            route_id=trip_proto.route_id
                            if trip_proto.HasField("route_id")
                            else None,
                            direction_id=trip_proto.direction_id
                            if trip_proto.HasField("direction_id")
                            else None,
                            start_time=gtfs_time(trip_proto.start_time)
                            if trip_proto.HasField("start_time")
                            else None,
                            start_date=gtfs_date(trip_proto.start_date)
                            if trip_proto.HasField("start_date")
                            else None,
                            schedule_relationship=trip_proto.schedule_relationship
                            if trip_proto.HasField("schedule_relationship")
                            else None,
                        )
                    )
                    try:
                        modified_trip_protos.append(
                            trip_proto.modified_trip
                            if trip_proto.HasField("modified_trip")
                            else None
                        )
                    except ValueError:
                        modified_trip_protos.append(None)

                if trip_descriptors_to_create:
                    created_trip_descriptors = TripDescriptor.objects.bulk_create(
                        trip_descriptors_to_create, batch_size=500
                    )

                    modified_trip_selectors_to_create = [
                        ModifiedTripSelector(
                            trip_descriptor=td,
                            field_name="modified_trip",
                            modifications_id=mts.modifications_id
                            if mts.HasField("modifications_id")
                            else None,
                            affected_trip_id=mts.affected_trip_id
                            if mts.HasField("affected_trip_id")
                            else None,
                            start_time=gtfs_time(mts.start_time)
                            if mts.HasField("start_time")
                            else None,
                            start_date=gtfs_date(mts.start_date)
                            if mts.HasField("start_date")
                            else None,
                        )
                        for td, mts in zip(
                            created_trip_descriptors, modified_trip_protos
                        )
                        if mts is not None
                    ]
                    if modified_trip_selectors_to_create:
                        ModifiedTripSelector.objects.bulk_create(
                            modified_trip_selectors_to_create, batch_size=500
                        )

            # TranslatedString fields and their Translation children
            translated_string_fields = [
                ("cause_detail", getattr(a, "cause_detail", None)),
                ("effect_detail", getattr(a, "effect_detail", None)),
                ("url", getattr(a, "url", None)),
                ("header_text", getattr(a, "header_text", None)),
                ("description_text", getattr(a, "description_text", None)),
                ("tts_header_text", getattr(a, "tts_header_text", None)),
                (
                    "tts_description_text",
                    getattr(a, "tts_description_text", None),
                ),
                (
                    "image_alternative_text",
                    getattr(a, "image_alternative_text", None),
                ),
            ]
            for field_name, ts_proto in translated_string_fields:
                if ts_proto is None or not getattr(ts_proto, "translation", None):
                    continue
                ts = TranslatedString.objects.create(alert=alert, field_name=field_name)
                Translation.objects.bulk_create(
                    [
                        Translation(
                            translated_string=ts,
                            field_name="translation",
                            text=t.text,
                            language=t.language if t.HasField("language") else None,
                        )
                        for t in ts_proto.translation
                    ],
                    batch_size=500,
                )

            # TranslatedImage and its LocalizedImage children
            image_proto = getattr(a, "image", None)
            localized_images = (
                list(image_proto.localized_image)
                if image_proto is not None
                and has_optional_field(a, "image")
                and getattr(image_proto, "localized_image", None)
                else []
            )
            if localized_images:
                translated_image = TranslatedImage.objects.create(
                    alert=alert, field_name="image"
                )
                LocalizedImage.objects.bulk_create(
                    [
                        LocalizedImage(
                            translated_image=translated_image,
                            field_name="localized_image",
                            url=li.url,
                            media_type=li.media_type,
                            language=li.language if li.HasField("language") else None,
                        )
                        for li in localized_images
                    ],
                    batch_size=500,
                )
