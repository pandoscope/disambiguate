"""The `payload` subcommand (#208; not a gate): no PUSH_BLOCKLIST value in
the one item an issue or comment event just published.
"""

import json
import os

from gate_leaks import leak_violations, parse_blocklist


def payload_surfaces(event):
    """The one item an issue/comment event just published, labeled.

    The event-driven net (#208) reads nothing but the event: an
    issue's title and body on `issues`, a comment's body on
    `issue_comment` (PR conversation comments included) and
    `pull_request_review_comment`. No repo walk, no API listing —
    layer 3 owns the full history; this catches the item that just
    went public, minutes instead of a day.
    """
    comment = event.get("comment")
    if comment:
        label = f"comment {comment.get('html_url')}"
        if comment.get("path"):
            label += f" on {comment['path']}"
        return [(label, comment.get("body"))]
    issue = event.get("issue") or event.get("pull_request") or {}
    where = issue.get("html_url")
    return [
        (f"issue {where} title", issue.get("title")),
        (f"issue {where} body", issue.get("body")),
    ]


def run_payload():
    values = parse_blocklist(os.environ.get("PUSH_BLOCKLIST"))
    if not values:
        print("::warning::PUSH_BLOCKLIST is empty — the denylist layer is inactive")
        return 0
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    problems = leak_violations(payload_surfaces(event), values)
    for problem in problems:
        print(f"::error::{problem}")
    if not problems:
        print("No blocklisted string in the item this event published.")
    return 1 if problems else 0
