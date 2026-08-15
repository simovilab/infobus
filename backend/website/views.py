from typing import TypedDict

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from feed.models import Feed, Stop
from updates.registry import PROJECTIONS, ProjectionSpec


class StopOption(TypedDict):
    stop_id: str
    stop_name: str


class TransitSystemOption(TypedDict):
    code: str
    name: str
    stops: list[StopOption]


# Create your views here.


def index(request: HttpRequest) -> HttpResponse:
    """Render the public landing-page template."""
    return render(request, "index.html")


def about(request: HttpRequest) -> HttpResponse:
    """Render the project information template."""
    return render(request, "about.html")


def profile(request: HttpRequest) -> HttpResponse:
    """Render the user profile template."""
    return render(request, "profile.html")


def _parameter_metadata(selector: str) -> dict[str, object]:
    """Describe a selector as JSON-safe console input metadata."""
    name = f"{selector.removeprefix('by_')}_id"
    metadata: dict[str, object] = {
        "name": name,
        "selector": selector,
        "label": name.replace("_", " ").title(),
        "input": "text",
    }
    if selector == "by_stop":
        metadata.update({"input": "select", "data_source": "current_stops"})
    elif selector == "by_direction":
        metadata.update(
            {
                "input": "select",
                "choices": [
                    {"value": "0", "label": "0"},
                    {"value": "1", "label": "1"},
                ],
            }
        )
    return metadata


def _projection_metadata(projection: ProjectionSpec) -> dict[str, object]:
    """Expose only JSON-safe topic structure derived from one registry entry."""
    pattern = projection.topic_pattern
    parameters = [_parameter_metadata(pattern.primary_selector)]
    if pattern.qualifier_selector is not None:
        parameters.append(_parameter_metadata(pattern.qualifier_selector))
    return {
        "name": projection.name,
        "description": projection.description,
        "entity": pattern.entity,
        "info": pattern.info,
        "primary_selector": pattern.primary_selector,
        "qualifier_selector": pattern.qualifier_selector,
        "parameters": parameters,
    }


def _current_schedule_systems() -> list[TransitSystemOption]:
    """Return systems with a current Schedule feed and their distinct stops."""
    system_rows = (
        Feed.objects.filter(
            is_current=True,
            feed_publisher__transit_system__isnull=False,
        )
        .values(
            "feed_publisher__transit_system__code",
            "feed_publisher__transit_system__name",
        )
        .order_by("feed_publisher__transit_system__name")
        .distinct()
    )
    systems: list[TransitSystemOption] = [
        {
            "code": row["feed_publisher__transit_system__code"],
            "name": row["feed_publisher__transit_system__name"],
            "stops": [],
        }
        for row in system_rows
    ]
    systems_by_code: dict[str, TransitSystemOption] = {
        system["code"]: system for system in systems
    }
    seen_stop_ids: dict[str, set[str]] = {code: set() for code in systems_by_code}

    stop_rows = (
        Stop.objects.filter(
            feed__is_current=True,
            feed__feed_publisher__transit_system__code__in=systems_by_code,
        )
        .exclude(stop_id="")
        .values(
            "feed__feed_publisher__transit_system__code",
            "stop_id",
            "stop_name",
        )
        .order_by(
            "feed__feed_publisher__transit_system__code",
            "stop_name",
            "stop_id",
        )
        .distinct()
    )
    for row in stop_rows:
        code = str(row["feed__feed_publisher__transit_system__code"])
        stop_id = str(row["stop_id"])
        if code not in systems_by_code or stop_id in seen_stop_ids[code]:
            continue
        seen_stop_ids[code].add(stop_id)
        systems_by_code[code]["stops"].append(
            {"stop_id": stop_id, "stop_name": row["stop_name"] or stop_id}
        )
    return systems


def updates(request: HttpRequest) -> HttpResponse:
    """Render the registry-driven manual WebSocket update console."""
    return render(
        request,
        "updates.html",
        {
            "projection_metadata": [
                _projection_metadata(projection) for projection in PROJECTIONS
            ],
            "transit_systems": _current_schedule_systems(),
        },
    )
