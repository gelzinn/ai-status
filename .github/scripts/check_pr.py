"""Validate squash titles and the user-written notes consumed by Release Please."""

import json
import re
import sys


TITLE = re.compile(r"^(feat|fix|perf|revert|deps|docs|chore|refactor|test|build|ci)(\([\w./-]+\))?(!)?: (\S.*)$")
RELEASABLE = {"feat", "fix", "perf", "revert", "deps"}


def validate(pr):
    title = TITLE.fullmatch(pr.get("title", ""))
    if not title:
        raise ValueError("Use a Conventional Commit title, e.g. fix(codex): show the weekly reset time")
    body = re.sub(r"<!--.*?-->", "", pr.get("body") or "", flags=re.S)
    if title[1] not in RELEASABLE and not title[3] and "BEGIN_COMMIT_OVERRIDE" not in body:
        return
    section = re.search(r"^## User-facing changes\s*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    if not section:
        raise ValueError("Add a '## User-facing changes' section with your release-note entry")
    blocks = re.findall(r"^BEGIN_COMMIT_OVERRIDE\s*\n(.*?)\nEND_COMMIT_OVERRIDE\s*$", section[1], re.M | re.S)
    if len(blocks) != 1 or body.count("BEGIN_COMMIT_OVERRIDE") != 1 or body.count("END_COMMIT_OVERRIDE") != 1:
        raise ValueError("Put exactly one BEGIN_COMMIT_OVERRIDE / END_COMMIT_OVERRIDE block in User-facing changes")
    note = blocks[0].strip()
    first = TITLE.fullmatch(note.splitlines()[0]) if note else None
    if not first or first[1] != title[1]:
        raise ValueError("The first release-note entry must use the same commit type as the PR title")
    if re.search(r"\b(todo|tbd|replace|placeholder)\b", note, re.I):
        raise ValueError("Replace placeholder text with a concrete change users will notice")
    if title[3] and not (first[3] or re.search(r"^BREAKING[ -]CHANGE:", note, re.M)):
        raise ValueError("Describe the breaking change in the release-note block, using ! or BREAKING CHANGE:")


if __name__ == "__main__":
    event = json.load(open(sys.argv[1], encoding="utf-8"))
    try:
        validate(event["pull_request"])
    except ValueError as error:
        print(f"::error::{error}")
        sys.exit(1)
    print("PR title and release notes are valid")
