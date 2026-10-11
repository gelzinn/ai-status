#!/usr/bin/env python3
import os
import sys
import time
import select
import re
import struct
import base64
import json
from pathlib import Path
from datetime import datetime, timezone
from core.paths import IS_WINDOWS
from core.metered import json_request, number
from core.provider_http import QueryError, output as query_output, require_token

if not IS_WINDOWS:
    import pty
    import fcntl
    import termios

ANSI_ESCAPE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def query():
    token = os.environ.get("ANTIGRAVITY_ACCESS_TOKEN")
    if not token:
        path = os.environ.get("AI_STATUS_AUTH_FILE")
        if not path and os.environ.get("AI_STATUS_ACCOUNT_ID"):
            raise QueryError("Configure an Antigravity account authentication file or ANTIGRAVITY_ACCESS_TOKEN.")
        path = Path(path) if path else Path.home() / ".gemini/antigravity-cli/antigravity-oauth-token"
        try:
            raw = path.read_text(encoding="utf-8-sig").strip()
            if raw.startswith("go-keyring-base64:"):
                raw = base64.b64decode(raw.split(":", 1)[1], validate=True).decode("utf-8")
            credentials = json.loads(raw)
            credentials = credentials.get("token") if isinstance(credentials.get("token"), dict) else credentials
            token = next((credentials[key] for key in ("access_token", "accessToken", "token", "id_token", "idToken", "bearerToken", "auth_token", "authToken")
                          if isinstance(credentials.get(key), str) and credentials[key].strip()), None)
            expiry = next((credentials[key] for key in ("expiry", "expires_at", "expiresAt") if key in credentials), None)
            if expiry is not None:
                stamp = number(expiry)
                if stamp is None:
                    expiry_date = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
                    if expiry_date.tzinfo is None:
                        expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                    stamp = expiry_date.timestamp()
                elif stamp >= 1e11:
                    stamp /= 1000
                if stamp <= time.time():
                    raise QueryError("Antigravity account session expired; sign in again and update the credential reference.")
        except (OSError, ValueError, TypeError, AttributeError, UnicodeError, OverflowError):
            raise QueryError("Unable to read Antigravity account credentials; select a valid saved OAuth token file.") from None
    token = require_token(token, "Configure an Antigravity account authentication file or ANTIGRAVITY_ACCESS_TOKEN.")
    return json_request("https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary", {
        "Authorization": f"Bearer {token}", "User-Agent": "antigravity",
    }, method="POST", data={})

def strip_ansi(text):
    return ANSI_ESCAPE.sub('', text)

def set_size(fd, rows, cols):
    try:
        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except:
        pass

def get_agy_usage():
    pid, fd = pty.fork()
    if pid == 0:
        try:
            os.execvp("agy", ["agy"])
        except:
            sys.exit(1)
    else:
        set_size(fd, 80, 120)

        output = b""
        start_time = time.time()
        prompt_sent = False
        prompt_sent_time = 0
        enter_sent = False
        exit_sent = False

        while True:
            elapsed = time.time() - start_time
            if elapsed > 15:
                break

            if prompt_sent and not enter_sent and (time.time() - prompt_sent_time > 1.5):
                try:
                    os.write(fd, b"\r")
                except:
                    pass
                enter_sent = True

            r, w, x = select.select([fd], [], [], 0.1)
            if fd in r:
                try:
                    data = os.read(fd, 4096)
                    if not data:
                        break
                    output += data
                    clean = strip_ansi(output.decode('utf-8', errors='replace'))

                    if "Welcome to the Antigravity CLI" in clean and not prompt_sent:
                        idx = clean.find("Welcome to the Antigravity CLI")
                        if ">" in clean[idx:]:
                            time.sleep(2.0)
                            try:
                                os.write(fd, b"/usage")
                            except:
                                pass
                            prompt_sent = True
                            prompt_sent_time = time.time()
                            start_time = time.time()

                    if enter_sent and "Weekly Limit" in clean and not exit_sent:
                        time.sleep(0.5)
                        try:
                            os.write(fd, b"/exit\r")
                        except:
                            pass
                        exit_sent = True
                except OSError:
                    break
            else:
                if exit_sent:
                    break

        try:
            os.close(fd)
        except:
            pass
        try:
            os.kill(pid, 9)
        except:
            pass
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass

        return strip_ansi(output.decode('utf-8', errors='replace'))

def main():
    if (os.environ.get("AI_STATUS_ACCOUNT_ID") or os.environ.get("AI_STATUS_AUTH_FILE") or
            os.environ.get("ANTIGRAVITY_ACCESS_TOKEN")):
        query_output(query)
        return
    if IS_WINDOWS:
        from core.console import query_antigravity
        from core.provider_http import output
        output(query_antigravity)
        return
    try:
        raw_out = get_agy_usage()
        print(raw_out)
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    main()
