from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from feed.models import TransitSystem
from runs.domain.lifecycle import RunLifecycleStates
from runs.models import Run
from runs.services.lifecycle import ACTIVE_STATES, active_runs_key, r
from runs.services.stop_index import clear_remaining_stops


class Command(BaseCommand):
    """Provide a guarded command that reports or interrupts aged active runs absent from canonical Redis sets."""
    help = (
        "Reconcile legacy in-progress runs after canonical heartbeat tracking "
        "has completed at least one successful polling cycle."
    )

    def add_arguments(self, parser) -> None:
        """Register dry-run and age-safety command options."""
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--minimum-age-minutes", type=int, default=60)
        parser.add_argument("--allow-empty-canonical", action="store_true")

    def handle(self, *args, **options) -> None:
        """Report or interrupt legacy runs absent from canonical active sets."""
        canonical_ids: set[str] = set()
        for system_code in TransitSystem.objects.values_list("code", flat=True):
            canonical_ids.update(r.smembers(active_runs_key(system_code)))

        if not canonical_ids and not options["allow_empty_canonical"]:
            raise CommandError(
                "Canonical active sets are empty. Wait for successful realtime "
                "polls or pass --allow-empty-canonical explicitly."
            )

        cutoff = timezone.now() - timedelta(minutes=options["minimum_age_minutes"])
        candidates = Run.objects.filter(
            run_lifecycle_state__in=ACTIVE_STATES,
            request_timestamp__lt=cutoff,
        ).exclude(id__in=canonical_ids)
        candidate_runs = list(
            candidates.values_list(
                "id",
                "feed_publisher__transit_system__code",
            )
        )
        candidate_ids = [run_id for run_id, _ in candidate_runs]

        self.stdout.write(
            f"Canonical active runs: {len(canonical_ids)}; "
            f"legacy candidates: {len(candidate_ids)}."
        )
        if not options["apply"]:
            self.stdout.write("Dry run only; pass --apply to persist changes.")
            return

        occurred_at = timezone.now()
        candidates.update(
            run_lifecycle_state=RunLifecycleStates.INTERRUPTED.value,
            missing_since=occurred_at,
            ended_at=occurred_at,
            last_event_at=occurred_at,
            completion_reason="Legacy active-set reconciliation.",
        )
        for run_id, system_code in candidate_runs:
            clear_remaining_stops(system_code, run_id)

        r.delete("trip:in_progress")
        self.stdout.write(
            self.style.SUCCESS(
                f"Interrupted {len(candidate_ids)} legacy runs and removed "
                "trip:in_progress."
            )
        )
