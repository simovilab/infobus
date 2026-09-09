"""Purge expired realtime, schedule, and Parquet data with a dry-run default."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection
from django.utils import timezone


REALTIME_STEPS: tuple[tuple[str, str, str], ...] = (
    (
        "feed_timerange",
        """
        DELETE FROM feed_timerange WHERE id IN (
            SELECT tr.id FROM feed_timerange tr
            JOIN feed_alert a ON tr.alert_id = a.id
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_timerange tr
        JOIN feed_alert a ON tr.alert_id = a.id
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_modifiedtripselector",
        """
        DELETE FROM feed_modifiedtripselector WHERE id IN (
            SELECT mts.id FROM feed_modifiedtripselector mts
            JOIN feed_tripdescriptor td ON mts.trip_descriptor_id = td.id
            JOIN feed_entityselector es ON td.entity_selector_id = es.id
            JOIN feed_alert a ON es.alert_id = a.id
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_modifiedtripselector mts
        JOIN feed_tripdescriptor td ON mts.trip_descriptor_id = td.id
        JOIN feed_entityselector es ON td.entity_selector_id = es.id
        JOIN feed_alert a ON es.alert_id = a.id
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_localizedimage",
        """
        DELETE FROM feed_localizedimage WHERE id IN (
            SELECT li.id FROM feed_localizedimage li
            JOIN feed_translatedimage ti ON li.translated_image_id = ti.id
            JOIN feed_alert a ON ti.alert_id = a.id
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_localizedimage li
        JOIN feed_translatedimage ti ON li.translated_image_id = ti.id
        JOIN feed_alert a ON ti.alert_id = a.id
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_translation",
        """
        DELETE FROM feed_translation WHERE id IN (
            SELECT t.id FROM feed_translation t
            JOIN feed_translatedstring ts ON t.translated_string_id = ts.id
            JOIN feed_alert a ON ts.alert_id = a.id
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_translation t
        JOIN feed_translatedstring ts ON t.translated_string_id = ts.id
        JOIN feed_alert a ON ts.alert_id = a.id
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_stoptimeupdate",
        """
        DELETE FROM feed_stoptimeupdate WHERE id IN (
            SELECT stu.id FROM feed_stoptimeupdate stu
            JOIN feed_tripupdate tu ON stu.trip_update_id = tu.id
            JOIN feed_feedmessage fm ON tu.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_stoptimeupdate stu
        JOIN feed_tripupdate tu ON stu.trip_update_id = tu.id
        JOIN feed_feedmessage fm ON tu.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_tripdescriptor",
        """
        DELETE FROM feed_tripdescriptor WHERE id IN (
            SELECT td.id FROM feed_tripdescriptor td
            JOIN feed_entityselector es ON td.entity_selector_id = es.id
            JOIN feed_alert a ON es.alert_id = a.id
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_tripdescriptor td
        JOIN feed_entityselector es ON td.entity_selector_id = es.id
        JOIN feed_alert a ON es.alert_id = a.id
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_translatedimage",
        """
        DELETE FROM feed_translatedimage WHERE id IN (
            SELECT ti.id FROM feed_translatedimage ti
            JOIN feed_alert a ON ti.alert_id = a.id
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_translatedimage ti
        JOIN feed_alert a ON ti.alert_id = a.id
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_translatedstring",
        """
        DELETE FROM feed_translatedstring WHERE id IN (
            SELECT ts.id FROM feed_translatedstring ts
            JOIN feed_alert a ON ts.alert_id = a.id
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_translatedstring ts
        JOIN feed_alert a ON ts.alert_id = a.id
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_entityselector",
        """
        DELETE FROM feed_entityselector WHERE id IN (
            SELECT es.id FROM feed_entityselector es
            JOIN feed_alert a ON es.alert_id = a.id
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_entityselector es
        JOIN feed_alert a ON es.alert_id = a.id
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_alert",
        """
        DELETE FROM feed_alert WHERE id IN (
            SELECT a.id FROM feed_alert a
            JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_alert a
        JOIN feed_feedmessage fm ON a.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_tripupdate",
        """
        DELETE FROM feed_tripupdate WHERE id IN (
            SELECT tu.id FROM feed_tripupdate tu
            JOIN feed_feedmessage fm ON tu.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_tripupdate tu
        JOIN feed_feedmessage fm ON tu.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "feed_vehicleposition with a feed message",
        """
        DELETE FROM feed_vehicleposition WHERE id IN (
            SELECT vp.id FROM feed_vehicleposition vp
            JOIN feed_feedmessage fm ON vp.feed_message_id = fm.feed_message_id
            WHERE fm.timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_vehicleposition vp
        JOIN feed_feedmessage fm ON vp.feed_message_id = fm.feed_message_id
        WHERE fm.timestamp < %s
        """,
    ),
    (
        "orphan feed_vehicleposition",
        """
        DELETE FROM feed_vehicleposition WHERE id IN (
            SELECT id FROM feed_vehicleposition
            WHERE feed_message_id IS NULL AND timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_vehicleposition
        WHERE feed_message_id IS NULL AND timestamp < %s
        """,
    ),
    (
        "feed_feedmessage",
        """
        DELETE FROM feed_feedmessage WHERE feed_message_id IN (
            SELECT feed_message_id FROM feed_feedmessage
            WHERE timestamp < %s LIMIT %s
        )
        """,
        """
        SELECT COUNT(*) FROM feed_feedmessage
        WHERE timestamp < %s
        """,
    ),
)

SCHEDULE_TABLES: tuple[str, ...] = (
    "feed_triptime",
    "feed_tripduration",
    "feed_routestop",
    "feed_geoshape",
    "feed_feedinfo",
    "feed_farerule",
    "feed_fareattribute",
    "feed_stoptime",
    "feed_trip",
    "feed_calendardate",
    "feed_calendar",
    "feed_shape",
    "feed_route",
    "feed_stop",
    "feed_agency",
    "feed_feed",
)

SCHEDULE_CANDIDATES_SQL = """
WITH ranked_feeds AS (
    SELECT
        feed_id,
        feed_publisher_id,
        ROW_NUMBER() OVER (
            PARTITION BY feed_publisher_id
            ORDER BY retrieved_at DESC NULLS LAST, feed_id
        ) AS recency_rank
    FROM feed_feed
)
SELECT feed.feed_id
FROM feed_feed feed
JOIN ranked_feeds ranked ON ranked.feed_id = feed.feed_id
WHERE feed.retrieved_at < %s
  AND feed.is_current IS NOT TRUE
  AND ranked.recency_rank > 1
ORDER BY feed.feed_publisher_id NULLS FIRST, feed.feed_id
"""

SCHEDULE_UNSAFE_PUBLISHERS_SQL = """
WITH ranked_feeds AS (
    SELECT
        feed_id,
        feed_publisher_id,
        ROW_NUMBER() OVER (
            PARTITION BY feed_publisher_id
            ORDER BY retrieved_at DESC NULLS LAST, feed_id
        ) AS recency_rank
    FROM feed_feed
),
candidates AS (
    SELECT feed.feed_id, feed.feed_publisher_id
    FROM feed_feed feed
    JOIN ranked_feeds ranked ON ranked.feed_id = feed.feed_id
    WHERE feed.retrieved_at < %s
      AND feed.is_current IS NOT TRUE
      AND ranked.recency_rank > 1
)
SELECT candidates.feed_publisher_id
FROM candidates
GROUP BY candidates.feed_publisher_id
HAVING COUNT(*) = (
    SELECT COUNT(*)
    FROM feed_feed feed
    WHERE feed.feed_publisher_id IS NOT DISTINCT FROM candidates.feed_publisher_id
)
"""


class Command(BaseCommand):
    """Report or purge historical realtime, schedule, and Parquet data."""

    help = "Report or purge historical realtime, schedule, and Parquet data."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register purge mode, scope, retention, and batch-size options."""
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument(
            "--scope",
            choices=("realtime", "schedule", "parquet", "all"),
            default="all",
        )
        parser.add_argument("--realtime-days", type=int, default=None)
        parser.add_argument("--schedule-days", type=int, default=None)
        parser.add_argument("--parquet-days", type=int, default=None)
        parser.add_argument("--batch-size", type=int, default=None)

    def handle(self, *args: object, **options: object) -> None:
        """Run the selected purge scopes in dry-run mode unless --apply is set."""
        apply = bool(options["apply"])
        scope = str(options["scope"])
        summaries: list[str] = []

        if scope in ("realtime", "all"):
            realtime_days = self._resolve_days(
                options["realtime_days"],
                settings.REALTIME_RETENTION_DAYS,
                "--realtime-days",
            )
            batch_size = self._resolve_batch_size(options["batch_size"])
            cutoff = timezone.now() - timedelta(days=realtime_days)
            deleted = self._purge_realtime(cutoff, batch_size, apply)
            summaries.append(f"realtime={deleted}")

        if scope in ("schedule", "all"):
            schedule_days = self._resolve_days(
                options["schedule_days"],
                settings.SCHEDULE_RETENTION_DAYS,
                "--schedule-days",
            )
            batch_size = self._resolve_batch_size(options["batch_size"])
            cutoff = timezone.now() - timedelta(days=schedule_days)
            deleted = self._purge_schedule(cutoff, batch_size, apply)
            summaries.append(f"schedule={deleted}")

        if scope in ("parquet", "all"):
            parquet_days = self._resolve_days(
                options["parquet_days"],
                settings.PARQUET_RETENTION_DAYS,
                "--parquet-days",
            )
            cutoff_date = (timezone.now() - timedelta(days=parquet_days)).date()
            removed = self._purge_parquet(cutoff_date, apply)
            summaries.append(f"parquet={removed}")

        mode = "Applied" if apply else "Dry run completed"
        self.stdout.write(self.style.SUCCESS(f"{mode}: {', '.join(summaries)}."))

    def _resolve_days(self, value: object, default: int, option_name: str) -> int:
        """Return a non-negative retention value from an option or its setting."""
        resolved = default if value is None else value
        if (
            not isinstance(resolved, int)
            or isinstance(resolved, bool)
            or resolved < 0
        ):
            raise CommandError(f"{option_name} must be a non-negative integer.")
        return resolved

    def _resolve_batch_size(self, value: object) -> int:
        """Return a positive batch size from an option or the configured setting."""
        resolved = settings.PURGE_BATCH_SIZE if value is None else value
        if (
            not isinstance(resolved, int)
            or isinstance(resolved, bool)
            or resolved <= 0
        ):
            raise CommandError("--batch-size must be a positive integer.")
        return resolved

    def _query_count(self, sql: str, params: Sequence[object]) -> int:
        """Return the count from a SQL statement that selects one aggregate."""
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
        return int(row[0]) if row is not None else 0

    def _fetch_rows(
        self, sql: str, params: Sequence[object]
    ) -> list[tuple[object, ...]]:
        """Return rows from a SQL statement as tuples."""
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def _delete_in_batches(
        self, sql: str, params: Sequence[object], batch_size: int
    ) -> int:
        """Execute a parameterized DELETE repeatedly until a batch deletes no rows."""
        total = 0
        while True:
            with connection.cursor() as cursor:
                cursor.execute(sql, [*params, batch_size])
                deleted = cursor.rowcount
            total += deleted
            if deleted == 0:
                return total

    def _purge_realtime(self, cutoff: datetime, batch_size: int, apply: bool) -> int:
        """Report or delete aged realtime rows in dependency-safe order."""
        total = 0
        for label, delete_sql, count_sql in REALTIME_STEPS:
            if apply:
                deleted = self._delete_in_batches(delete_sql, [cutoff], batch_size)
                self.stdout.write(f"Realtime deleted from {label}: {deleted} rows.")
            else:
                deleted = self._query_count(count_sql, [cutoff])
                self.stdout.write(
                    f"Realtime dry-run count for {label}: {deleted} rows."
                )
            total += deleted

        action = "deleted" if apply else "would delete"
        self.stdout.write(f"Realtime total {action}: {total} rows.")
        return total

    def _schedule_candidates(self, cutoff: datetime) -> list[str]:
        """Return schedule feed identifiers eligible for retention cleanup."""
        rows = self._fetch_rows(SCHEDULE_CANDIDATES_SQL, [cutoff])
        return [str(row[0]) for row in rows]

    def _assert_schedule_safeguard(self, cutoff: datetime) -> None:
        """Reject a selection that would remove every feed for a publisher."""
        rows = self._fetch_rows(SCHEDULE_UNSAFE_PUBLISHERS_SQL, [cutoff])
        if rows:
            publisher_ids = ", ".join(
                "NULL" if row[0] is None else str(row[0]) for row in rows
            )
            raise CommandError(
                "Refusing schedule purge because it would remove every feed for "
                f"publisher(s): {publisher_ids}."
            )

    def _schedule_table_count(self, table: str, feed_ids: Sequence[str]) -> int:
        """Return the rows in one schedule table linked to candidate feeds."""
        if not feed_ids:
            return 0
        placeholders = ", ".join("%s" for _ in feed_ids)
        sql = f"SELECT COUNT(*) FROM {table} WHERE feed_id IN ({placeholders})"
        return self._query_count(sql, feed_ids)

    def _schedule_delete_sql(self, table: str) -> str:
        """Build a PostgreSQL batch DELETE scoped to a single schedule feed."""
        return f"""
        DELETE FROM {table}
        WHERE ctid IN (
            SELECT ctid FROM {table}
            WHERE feed_id = %s
            LIMIT %s
        )
        """

    def _purge_schedule(self, cutoff: datetime, batch_size: int, apply: bool) -> int:
        """Report or delete aged schedule feeds after enforcing publisher safeguards."""
        self._assert_schedule_safeguard(cutoff)
        feed_ids = self._schedule_candidates(cutoff)
        rendered_ids = ", ".join(feed_ids) if feed_ids else "none"
        self.stdout.write(f"Schedule candidates: {len(feed_ids)}.")
        self.stdout.write(f"Schedule candidate feed IDs: {rendered_ids}.")

        totals: dict[str, int] = {}
        if apply:
            for feed_id in feed_ids:
                for table in SCHEDULE_TABLES:
                    deleted = self._delete_in_batches(
                        self._schedule_delete_sql(table),
                        [feed_id],
                        batch_size,
                    )
                    totals[table] = totals.get(table, 0) + deleted
            action = "deleted"
        else:
            totals = {
                table: self._schedule_table_count(table, feed_ids)
                for table in SCHEDULE_TABLES
            }
            action = "would delete"

        for table in SCHEDULE_TABLES:
            self.stdout.write(
                f"Schedule {action} from {table}: {totals.get(table, 0)} rows."
            )

        total = sum(totals.values())
        self.stdout.write(f"Schedule total {action}: {total} rows.")
        return total

    def _parquet_directories(self, cutoff_date: date) -> list[Path]:
        """Return dated Parquet directories older than the supplied cutoff date."""
        directories: list[Path] = []
        for directory in sorted(Path("/app/data").glob("*/date=*")):
            if not directory.is_dir():
                continue
            try:
                directory_date = date.fromisoformat(directory.name.removeprefix("date="))
            except ValueError:
                self.stdout.write(
                    f"Ignoring unparsable parquet date directory: {directory}."
                )
                continue
            if directory_date < cutoff_date:
                directories.append(directory)
        return directories

    def _directory_size(self, directory: Path) -> int:
        """Return the aggregate byte size of regular files below a directory."""
        return sum(
            path.stat().st_size
            for path in directory.rglob("*")
            if path.is_file()
        )

    def _purge_parquet(self, cutoff_date: date, apply: bool) -> int:
        """Report or remove Parquet directories that predate the retention cutoff."""
        directories = self._parquet_directories(cutoff_date)
        total_size = sum(self._directory_size(directory) for directory in directories)

        if apply:
            for directory in directories:
                shutil.rmtree(directory)
                self.stdout.write(f"Removed parquet directory: {directory}.")
            action = "removed"
        else:
            for directory in directories:
                self.stdout.write(f"Would remove parquet directory: {directory}.")
            action = "would remove"

        self.stdout.write(
            f"Parquet directories {action}: {len(directories)}; "
            f"total size: {total_size} bytes."
        )
        return len(directories)
