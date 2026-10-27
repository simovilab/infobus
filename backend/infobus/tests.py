import os
import subprocess
import sys
from pathlib import Path
from django.test import SimpleTestCase

from .utils import redact_url


class AsgiStartupTests(SimpleTestCase):
    def test_application_import_initializes_django_in_a_fresh_process(self):
        env = os.environ.copy()
        env.pop("DJANGO_SETTINGS_MODULE", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from infobus.asgi import application; "
                    "from django.apps import apps; "
                    "assert apps.ready; "
                    "assert set(application.application_mapping) == "
                    "{'http', 'websocket'}"
                ),
            ],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class RedactUrlTests(SimpleTestCase):
    def test_removes_credentials_and_query_string(self):
        redacted = redact_url("http://user:pass@host/path?token=secret")

        self.assertEqual(redacted, "http://host/path")
        self.assertNotIn("user", redacted)
        self.assertNotIn("pass", redacted)
        self.assertNotIn("token=secret", redacted)

    def test_rejects_url_without_scheme(self):
        self.assertEqual(redact_url("not a url"), "<redacted url>")

    def test_rejects_non_string_input(self):
        self.assertEqual(redact_url(None), "<redacted url>")
        self.assertEqual(redact_url(123), "<redacted url>")

    def test_preserves_ipv6_host_and_port_without_credentials(self):
        self.assertEqual(
            redact_url("http://user:pass@[::1]:8080/x"),
            "http://[::1]:8080/x",
        )

    def test_preserves_normal_url_without_sensitive_parts(self):
        self.assertEqual(
            redact_url("https://example.com/path"),
            "https://example.com/path",
        )
