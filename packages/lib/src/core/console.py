"""Windows ConPTY interaction for terminal-only usage commands."""
import re
import select
import time
from .provider_http import QueryError, cli_path

ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-Z\\-_])")


def query_antigravity():
    from winpty import Backend, PtyProcess

    executable = cli_path("agy")
    proc = PtyProcess.spawn([executable], dimensions=(80, 120), backend=Backend.ConPTY)
    deadline = time.monotonic() + 15
    text = ""
    sent = False
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([proc.fileobj], [], [], 0.1)
            if not ready:
                if not proc.isalive():
                    break
                continue
            try:
                text += proc.read(4096)
            except EOFError:
                break
            clean = ANSI_ESCAPE.sub("", text).replace("\r", "")
            if not sent and "Welcome to the Antigravity CLI" in clean and ">" in clean:
                proc.write("/usage\r")
                sent = True
            if sent and "Weekly Limit" in clean and re.search(r"(?:Quota available|\d+\s*(?:d|h|m|hour|minute))", clean, re.I):
                deadline = min(deadline, time.monotonic() + 0.7)
        if not sent or "Weekly Limit" not in text:
            raise QueryError("Antigravity usage was unavailable; sign in to agy and check its CLI version.")
        return ANSI_ESCAPE.sub("", text).replace("\r", "")
    finally:
        proc.close(force=True)
