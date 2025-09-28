from __future__ import annotations

from typing import List

from .interfaces import Departure, ScheduleRepository


class FusekiScheduleRepository(ScheduleRepository):
    """Optional Fuseki-backed schedule repository.

    This is a stub implementation. It outlines the expected interface and can be
    filled in later to execute SPARQL queries against a Jena Fuseki endpoint.
    """

    def __init__(self, *, endpoint: str):
        self._endpoint = endpoint

    def get_next_departures(self, **kwargs) -> List[Departure]:
        raise NotImplementedError(
            "FusekiScheduleRepository is not yet implemented. Set FUSEKI_ENABLED=false to use Postgres."
        )