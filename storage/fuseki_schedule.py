from __future__ import annotations

from typing import List, Optional
from datetime import date, time

import requests

from .interfaces import Departure, ScheduleRepository


class FusekiScheduleRepository(ScheduleRepository):
    """Fuseki-backed schedule repository using SPARQL queries.

    Minimal vocabulary expected for each ex:Departure resource:
      - ex:feed_id, ex:stop_id, ex:trip_id (xsd:string)
      - ex:arrival_time, ex:departure_time (xsd:string HH:MM:SS)
      - optional: ex:route_id, ex:headsign, ex:direction_id, ex:route_short_name, ex:route_long_name
      - optional: ex:service_date (xsd:string YYYY-MM-DD)

    PREFIX ex: <http://example.org/gtfs#>
    """

    def __init__(self, *, endpoint: str):
        self._endpoint = endpoint.rstrip("/")

    def get_next_departures(
        self,
        *,
        feed_id: str,
        stop_id: str,
        service_date: date,
        from_time: time,
        limit: int = 10,
    ) -> List[Departure]:
        date_str = service_date.isoformat()
        time_str = from_time.strftime("%H:%M:%S")
        query = f"""
        PREFIX ex: <http://example.org/gtfs#>
        SELECT ?route_id ?route_short_name ?route_long_name ?trip_id ?stop_id ?headsign ?direction_id ?arrival ?departure
        WHERE {{
          ?d a ex:Departure ;
             ex:feed_id "{feed_id}" ;
             ex:stop_id "{stop_id}" ;
             ex:trip_id ?trip_id ;
             ex:arrival_time ?arrival ;
             ex:departure_time ?departure .
          OPTIONAL {{ ?d ex:route_id ?route_id }}
          OPTIONAL {{ ?d ex:headsign ?headsign }}
          OPTIONAL {{ ?d ex:direction_id ?direction_id }}
          OPTIONAL {{ ?d ex:route_short_name ?route_short_name }}
          OPTIONAL {{ ?d ex:route_long_name ?route_long_name }}
          OPTIONAL {{ ?d ex:service_date ?svc_date }}
          FILTER ( ?departure >= "{time_str}" )
          FILTER ( !BOUND(?svc_date) || ?svc_date = "{date_str}" )
        }}
        ORDER BY ?departure
        LIMIT {int(limit)}
        """

        headers = {
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/sparql-query",
        }
        resp = requests.post(self._endpoint, data=query.encode("utf-8"), headers=headers, timeout=10)
        resp.raise_for_status()
        js = resp.json()
        results: List[Departure] = []
        for b in js.get("results", {}).get("bindings", []):
            def val(name: str) -> Optional[str]:
                v = b.get(name, {}).get("value")
                return v if v != "" else None

            results.append(
                {
                    "route_id": val("route_id") or "",
                    "route_short_name": val("route_short_name"),
                    "route_long_name": val("route_long_name"),
                    "trip_id": val("trip_id") or "",
                    "stop_id": val("stop_id") or stop_id,
                    "headsign": val("headsign"),
                    "direction_id": int(val("direction_id")) if val("direction_id") else None,
                    "arrival_time": val("arrival"),
                    "departure_time": val("departure"),
                }
            )
        return results
