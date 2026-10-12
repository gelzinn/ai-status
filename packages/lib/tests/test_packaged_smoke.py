"""Exercise packaged smoke diagnostics against real credential-free subprocesses."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import packaged_smoke


class PackagedSmokeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="packaged smoke ")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def command(self, code, *arguments):
        script = self.root / "synthetic CLI.py"
        script.write_text(code, encoding="utf-8")
        return [sys.executable, str(script), *arguments]

    def test_failed_cli_prints_phase_command_and_both_streams_without_changing_failure(self):
        command = self.command(
            "import sys\n"
            "print('Runtime initialized')\n"
            "print('QueryError: HTTP 403', file=sys.stderr)\n"
            "sys.exit(7)\n", "doctor", "--http-smoke",
        )
        diagnostics = io.StringIO()
        with contextlib.redirect_stderr(diagnostics), self.assertRaises(subprocess.CalledProcessError) as caught:
            packaged_smoke.run_process(command, phase="runtime and native HTTPS", timeout=5)
        error = caught.exception
        self.assertEqual(error.returncode, 7)
        self.assertEqual(error.cmd, command)
        self.assertEqual(error.stdout.strip(), "Runtime initialized")
        self.assertEqual(error.stderr.strip(), "QueryError: HTTP 403")
        output = diagnostics.getvalue()
        for detail in ("runtime and native HTTPS", "exit status 7", "Command:", command[1],
                       "doctor", "--http-smoke", "Captured stdout:", "Runtime initialized",
                       "Captured stderr:", "QueryError: HTTP 403"):
            self.assertIn(detail, output)

    def test_timeout_prints_partial_utf8_streams_and_preserves_timeout_exception(self):
        command = self.command(
            "import sys, time\n"
            "sys.stdout.reconfigure(encoding='utf-8')\n"
            "sys.stderr.reconfigure(encoding='utf-8')\n"
            "print('Snapshot parcial: quota · 95%', flush=True)\n"
            "print('Conexão interrompida', file=sys.stderr, flush=True)\n"
            "time.sleep(30)\n",
        )
        diagnostics = io.StringIO()
        with contextlib.redirect_stderr(diagnostics), self.assertRaises(subprocess.TimeoutExpired) as caught:
            packaged_smoke.run_process(command, phase="GUI launcher", timeout=1)
        error = caught.exception
        self.assertEqual(error.cmd, command)
        self.assertEqual(error.timeout, 1)
        self.assertTrue(error.stdout)
        self.assertTrue(error.stderr)
        output = diagnostics.getvalue()
        for detail in ("GUI launcher", "timeout after 1s", command[1],
                       "Snapshot parcial: quota · 95%", "Conexão interrompida"):
            self.assertIn(detail, output)

    def test_successful_json_is_parsed_without_diagnostic_noise(self):
        expected = {"providers": [], "errors": {"codex": "Sign in to Codex"}}
        command = self.command("import json\nprint(json.dumps(" + repr(expected) + "))\n")
        output, diagnostics = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(diagnostics):
            result = packaged_smoke.run(command[0], *command[1:], phase="status with a clean profile")
        self.assertEqual(result, expected)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(diagnostics.getvalue(), "")

    def test_expected_invalid_arguments_keep_nonzero_status_without_failure_noise(self):
        command = self.command("import sys\nprint('Usage: ai-status --query PROVIDER', file=sys.stderr)\nsys.exit(2)\n")
        diagnostics = io.StringIO()
        with contextlib.redirect_stderr(diagnostics):
            result = packaged_smoke.run_process(command, phase="invalid CLI arguments", timeout=5, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)
        self.assertEqual(diagnostics.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
