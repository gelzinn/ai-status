from datetime import datetime, timezone
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import time

from core.metered import json_request, number, options
from core.provider_http import QueryError, cli_path, output, require_token, run_cli


def _credentials(path):
    try:
        if not path.is_file():
            raise QueryError("Configure a Kiro account authentication file or KIRO_ACCESS_TOKEN.")
        with path.open("rb") as stream:
            sqlite = stream.read(16) == b"SQLite format 3\0"
        if not sqlite:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError
            credentials = value.get("token") if isinstance(value.get("token"), dict) else value
            return {**credentials, "profile_arn": value.get("profile_arn") or (value.get("profile") or {}).get("arn") or credentials.get("profile_arn", "")}
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("BEGIN")
            row = connection.execute("SELECT value FROM auth_kv WHERE key=?", ("kirocli:odic:token",)).fetchone()
            credentials = json.loads(row[0]) if row else {}
            if not isinstance(credentials, dict):
                raise ValueError
            try:
                row = connection.execute("SELECT value FROM state WHERE key=?", ("api.codewhisperer.profile",)).fetchone()
                profile = json.loads(row[0]) if row else {}
                credentials["profile_arn"] = profile.get("arn", "")
            except (sqlite3.Error, ValueError, AttributeError):
                credentials["profile_arn"] = ""
            return credentials
    except (OSError, ValueError, TypeError, AttributeError, sqlite3.Error):
        raise QueryError("Unable to read Kiro account credentials; select a valid JSON file or Kiro CLI database.") from None


def _check_expiry(value):
    if value is None:
        return
    stamp = number(value)
    if stamp is None:
        try:
            stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            stamp = stamp.timestamp()
        except (ValueError, TypeError, OverflowError):
            raise QueryError("Kiro credentials have an invalid expiry; sign in again.") from None
    elif stamp >= 1e11:
        stamp /= 1000
    if stamp <= time.time():
        raise QueryError("Kiro account session expired; sign in again and update the credential reference.")


def _account_query():
    cfg = options()
    path = os.environ.get("AI_STATUS_AUTH_FILE")
    credentials = _credentials(Path(path)) if path else {}
    token = require_token(os.environ.get("KIRO_ACCESS_TOKEN") or credentials.get("access_token"),
                          "Configure a Kiro account authentication file or KIRO_ACCESS_TOKEN.")
    if not os.environ.get("KIRO_ACCESS_TOKEN"):
        _check_expiry(credentials.get("expires_at"))
    region = cfg.get("region") or credentials.get("region") or "us-east-1"
    if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d+", region):
        raise QueryError("Kiro region must be a valid AWS region identifier.")
    profile = cfg.get("profile_arn") or credentials.get("profile_arn") or ""
    if not isinstance(profile, str):
        raise QueryError("Kiro profile_arn must be a string.")
    return json_request(f"https://codewhisperer.{region}.amazonaws.com/", {
        "Authorization": f"Bearer {token}", "Content-Type": "application/x-amz-json-1.0",
        "x-amz-target": "AmazonCodeWhispererService.GetUsageLimits",
    }, method="POST", data={"origin": "AI_EDITOR", "profileArn": profile, "resourceType": "AGENTIC_REQUEST"})


def query():
    if os.environ.get("AI_STATUS_ACCOUNT_ID") or os.environ.get("AI_STATUS_AUTH_FILE") or os.environ.get("KIRO_ACCESS_TOKEN"):
        return _account_query()
    exe = cli_path("kiro-cli")
    run_cli([exe, "whoami", "--format", "json"], timeout=4)
    text = run_cli([exe, "chat", "--no-interactive", "/usage"], timeout=12)
    if not text.strip():
        raise QueryError("Kiro returned no usage; check CLI compatibility and sign-in.")
    return text


def main():
    output(query)


if __name__ == "__main__":
    main()
