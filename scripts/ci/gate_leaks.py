"""The `leaks` subcommand: no PUSH_BLOCKLIST value appears on any surface
this PR publishes (#189) — title, body, commit messages, commit author and
committer names and emails, the branch name, the added side of the diff,
the PR's own comment and review threads, and the bodies and comments of
every ticket the body references.
"""

import json
import os
import re

from gate_api import fetch, paginate
from gate_ticket import REF, live_pr


def parse_blocklist(value):
    """PUSH_BLOCKLIST env → (value, name) pairs, blanks dropped.

    `|`-separated values (pandoscope/skills#46); the variable carries
    WHAT to block and nothing else, so the committed side of the
    contract is just this parser and the variable's name. An entry may
    name its own placeholder (`value=pb:name`, `=` and `|` reserved):
    the name is what violations and scrub placeholders say, and it
    survives list edits where a positional index would drift. An
    unlabeled entry falls back to its raw field position.
    """
    if not value:
        return []
    pairs = []
    for position, entry in enumerate(value.split("|"), start=1):
        term, _, name = entry.partition("=")
        term = term.strip()
        if term:
            pairs.append((term, name.strip() or f"entry {position}"))
    return pairs


def leak_violations(surfaces, values):
    """Denylist hits over (label, text) surfaces — value-silent.

    Case-insensitive substring match, one violation per (surface,
    entry) pair; `values` is parse_blocklist output. The violation
    names WHERE and WHICH entry — by the entry's own placeholder name
    when it carries one — never WHAT: the values are the identifying
    material this gate keeps off public surfaces, and this gate's own
    log on a public repo is such a surface (#189).
    """
    problems = []
    for label, text in surfaces:
        lowered = (text or "").lower()
        for term, name in values:
            if term.lower() in lowered:
                problems.append(
                    f"{label} carries PUSH_BLOCKLIST {name} — "
                    "scrub it and rewrite the offending commit or text"
                )
    return problems


def referenced_tickets(body, repo):
    """Every ticket the body mentions, keyword or not, as owner/repo#n.

    Broader than closing_refs on purpose: a see-also reference leaks
    exactly like a CLOSES, so any `#n` / `owner/repo#n` occurrence
    puts that ticket's surfaces under the scan.
    """
    refs = set()
    for match in re.finditer(REF, body or ""):
        ref = match.group(0)
        refs.add(ref if "/" in ref else f"{repo}{ref}")
    return sorted(refs)


def added_lines(patch):
    """The published side of a unified diff: `+` lines, marker stripped.

    A removal cannot publish anything main does not already publish,
    and the PR that scrubs a value from main is exactly the one whose
    removal lines carry it — scanning them made a scrub unable to pass
    (#238). The `+++` header names a file, not content, and is skipped.
    """
    return "\n".join(
        line[1:]
        for line in (patch or "").splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def pr_surfaces(
    pr, commits, files, comments=(), reviews=(), review_comments=(), tickets=()
):
    """Every text surface this PR publishes, labeled for the verdict.

    Commit metadata is listed explicitly because no established
    scanner covers author/committer name and email (#189) — an agent's
    misconfigured git identity auto-publishes on merge with no
    approval step in between. The PR's own comment threads and the
    tickets it references (`tickets` is (ref, body, comments) tuples)
    are scanned too: those publish the instant they are posted, so
    this cannot prevent — but the gate re-runs on PR events, and a hit
    blocks merge and goes loud instead of lingering quietly.
    """
    surfaces = [("PR title", pr.get("title")), ("PR body", pr.get("body"))]
    if pr.get("head"):
        surfaces.append(("branch name", pr["head"].get("ref")))
    for ref, body, ticket_comments in tickets:
        surfaces.append((f"ticket {ref} body", body))
        for comment in ticket_comments:
            surfaces.append(
                (f"ticket {ref} comment {comment['id']}", comment.get("body"))
            )
    for entry in commits:
        sha = entry["sha"][:7]
        commit = entry["commit"]
        surfaces.append((f"commit {sha} message", commit.get("message")))
        for role in ("author", "committer"):
            who = commit.get(role) or {}
            surfaces.append((f"commit {sha} {role} name", who.get("name")))
            surfaces.append((f"commit {sha} {role} email", who.get("email")))
    for changed in files:
        surfaces.append(
            (f"diff of {changed['filename']}", added_lines(changed.get("patch")))
        )
    for comment in comments:
        surfaces.append((f"comment {comment['id']}", comment.get("body")))
    for review in reviews:
        surfaces.append((f"review {review['id']}", review.get("body")))
    for comment in review_comments:
        where = comment.get("path") or "(general)"
        surfaces.append(
            (f"review comment {comment['id']} on {where}", comment.get("body"))
        )
    return surfaces


def run_leaks():
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    values = parse_blocklist(os.environ.get("PUSH_BLOCKLIST"))
    if not values:
        # An unset org secret must not fail every fork and fresh
        # consumer, but silence would hide that the layer is off.
        print("::warning::PUSH_BLOCKLIST is empty — the denylist layer is inactive")
        return 0
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    pr = live_pr(event["pull_request"], token)
    number = pr["number"]
    commits = paginate(f"/repos/{repo}/pulls/{number}/commits", token)
    files = paginate(f"/repos/{repo}/pulls/{number}/files", token)
    tickets = []
    for ref in referenced_tickets(pr.get("body"), repo):
        ticket_repo, _, ticket_number = ref.rpartition("#")
        try:
            issue = fetch(f"/repos/{ticket_repo}/issues/{ticket_number}", token)
            ticket_comments = paginate(
                f"/repos/{ticket_repo}/issues/{ticket_number}/comments", token
            )
        except (OSError, ValueError) as error:
            # A ref the token cannot read (foreign or private repo) is
            # not this gate's to judge — say so and move on.
            print(f"::notice::could not scan referenced ticket {ref}: {error}")
            continue
        tickets.append((ref, issue.get("body"), ticket_comments))
    problems = leak_violations(
        pr_surfaces(
            pr,
            commits,
            files,
            comments=paginate(f"/repos/{repo}/issues/{number}/comments", token),
            reviews=paginate(f"/repos/{repo}/pulls/{number}/reviews", token),
            review_comments=paginate(f"/repos/{repo}/pulls/{number}/comments", token),
            tickets=tickets,
        ),
        values,
    )
    for problem in problems:
        print(f"::error::{problem}")
    if not problems:
        print("No blocklisted string on any surface this PR publishes.")
    return 1 if problems else 0
