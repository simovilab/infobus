"""Shared utility helpers."""

from urllib.parse import urlsplit, urlunsplit


def redact_url(url: str) -> str:
    """Return a URL safe for logging, without credentials or query string."""
    if not isinstance(url, str):
        return "<redacted url>"

    try:
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return "<redacted url>"

        netloc = parts.netloc.rsplit("@", 1)[-1]
        if not netloc:
            return "<redacted url>"

        return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
    except Exception:
        return "<redacted url>"
