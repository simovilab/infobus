import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROD_SCRIPT = Path(__file__).resolve().parents[1] / "prod.sh"


class ProductionReadinessTests(unittest.TestCase):
    def run_deployment(self, scenario):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "bin").mkdir()
            (root / "scripts" / "prod.sh").write_text(PROD_SCRIPT.read_text())
            keys = (
                "ORCHESTRATOR_DOMAIN UI_DOMAIN LAKE_DOMAIN SECRET_KEY "
                "DB_PASSWORD REDIS_PASSWORD RABBITMQ_PASS MINIO_ROOT_USER "
                "MINIO_ROOT_PASSWORD"
            ).split()
            (root / ".env").write_text("".join(f"{key}=test-value\n" for key in keys))
            for name in (".env.prod", "compose.prod.yml", "minio.license"):
                (root / name).touch()

            docker = root / "bin" / "docker"
            docker.write_text(
                f"#!{sys.executable}\n"
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "with open(os.environ['DOCKER_CALLS'], 'a') as calls:\n"
                "    calls.write(json.dumps(args) + '\\n')\n"
                "scenario = os.environ['SCENARIO']\n"
                "if args[0] == 'compose' and 'ps' in args and '-q' in args:\n"
                "    print('fake-' + args[-1])\n"
                "elif args[0] == 'inspect':\n"
                "    if '.State.Status' in args[1]:\n"
                "        print('running')\n"
                "    else:\n"
                "        print('unhealthy' if scenario == 'infra-failure' else 'healthy')\n"
                "elif args[0] == 'exec':\n"
                "    sys.exit(1 if scenario == 'app-failure' else 0)\n"
            )
            docker.chmod(0o755)
            sleep = root / "bin" / "sleep"
            sleep.write_text("#!/bin/sh\ntrue\n")
            sleep.chmod(0o755)

            calls_path = root / "calls.jsonl"
            env = os.environ.copy()
            env.update(
                PATH=f"{root / 'bin'}:{env['PATH']}",
                SCENARIO=scenario,
                DOCKER_CALLS=str(calls_path),
            )
            result = subprocess.run(
                ["bash", str(root / "scripts" / "prod.sh")],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
            return result, calls

    def test_success_uses_python_socket_probe(self):
        result, calls = self.run_deployment("success")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        probes = [call for call in calls if call[0] == "exec"]
        self.assertEqual(len(probes), 1)
        self.assertEqual(probes[0][2:4], ["/home/app/.venv/bin/python", "-c"])
        self.assertIn("socket.create_connection", probes[0][4])
        self.assertIn("Orchestrator responding", result.stdout)

    def test_orchestrator_timeout_fails_deployment(self):
        result, calls = self.run_deployment("app-failure")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Orchestrator did not respond", result.stdout)
        self.assertTrue(any(call[0] == "exec" for call in calls))
        self.assertNotIn("Production URLs", result.stdout)

    def test_unhealthy_infrastructure_prevents_application_start(self):
        result, calls = self.run_deployment("infra-failure")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Aborting deployment", result.stdout)
        self.assertFalse(any("--remove-orphans" in call for call in calls))
        self.assertFalse(any(call[0] == "exec" for call in calls))


if __name__ == "__main__":
    unittest.main()
