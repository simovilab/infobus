from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasApiKey(BasePermission):
        """API key check for write operations.

        POST endpoints accept user content and are protected via ApiKeyAuth per the
        OpenAPI contract. An `X-API-Key` header matching `DATAHUB_API_KEY` is required.
        If the key is not configured, write requests are denied by default.
        """


        message = "No autorizado"

        def has_permission(self, request, view):
                expected = getattr(settings, "DATAHUB_API_KEY", None)
                if not expected:
                        return False

                provided = request.headers.get("X-API-Key")
                return bool(provided) and provided == expected
