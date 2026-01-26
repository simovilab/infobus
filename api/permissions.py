from __future__ import annotations

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ApiKeyAuthentication(BaseAuthentication):
    """API key authentication for write operations.

    POST endpoints accept user content and are protected via ApiKeyAuth per the
    OpenAPI contract. An `X-API-Key` header matching `DATAHUB_API_KEY` is required.
    If the key is not configured or invalid, raises AuthenticationFailed (401).
    """

    def authenticate(self, request):
        expected = getattr(settings, "DATAHUB_API_KEY", None)
        if not expected:
            raise AuthenticationFailed("API key no configurada en el servidor")

        provided = request.headers.get("X-API-Key")
        if not provided:
            raise AuthenticationFailed("Falta API key en el header X-API-Key")

        if provided != expected:
            raise AuthenticationFailed("API key inválida")

        # Return (user, auth) tuple - using None for user since API key doesn't identify a user
        return (None, provided)
