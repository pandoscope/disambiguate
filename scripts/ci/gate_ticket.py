"""The `ticket` subcommand: the PR names its tickets in the canonical
ALL-CAPS form (#137).

`REF` and `reference_config` live here because the keyword file is the
ticket gate's own, and the reviews and leaks jobs read them from here.
"""

import json
import os
import re

from gate_api import fetch, paginate


# `#123` or `owner/repo#123`.
REF = r"(?:[\w.-]+/[\w.-]+)?#\d+"


def ticket_violations(body, branch, labels, author, config):
    """Violations of the reference rules, and whether the escape held.

    The allow-list is exact ALL CAPS: the gate recognizes only the
    canonical forms, and separately REJECTS any of the forge's native
    closing keywords in any other casing — a `resolves #5` in prose
    would close the ticket on merge without the gate ever auditing it,
    which is the false-accept this deny scan exists for. The only
    escape is the `automated` label on a bot-authored PR: an agent
    doing manual work cannot honestly hold either half.
    """
    allowed = config["allowed"]
    native = {word.lower() for word in config["github_native"]}
    if "automated" in labels and str(author).endswith("[bot]"):
        return [], True

    problems = []
    text = body or ""
    found = re.findall(
        r"\b(" + "|".join(map(re.escape, allowed)) + r") (" + REF + r")", text
    )
    for match in re.finditer(r"\b([A-Za-z]+) (" + REF + r")", text):
        word, ref = match.group(1), match.group(2)
        if word in allowed:
            continue
        if word.lower() in native or word.upper() in allowed:
            problems.append(
                f"'{word} {ref}' is not canonical — write "
                f"{'/'.join(sorted(allowed))} in ALL CAPS, or drop the keyword"
            )
    if not found:
        problems.append(
            "the body carries no canonical ticket reference — "
            f"{'/'.join(sorted(allowed))} #n (or owner/repo#n) is required"
        )

    named = re.match(config["branch_pattern"], branch or "")
    if named:
        in_body = {re.search(r"#(\d+)$", ref).group(1) for _, ref in found}
        # A token may carry a lowercase repo shortcode before its
        # number (skills#147: one branch name for a cross-repo arc);
        # the ticket number is the token's trailing digit run, so
        # d10e76 names ticket 76, never 10.
        in_branch = {
            re.search(r"(\d+)$", token).group(1) for token in named.group(1).split("-")
        }
        for number in sorted(in_branch - in_body, key=int):
            problems.append(
                f"the branch names ticket {number} but the body never "
                f"references #{number} with a canonical keyword"
            )
    return problems, False


def closing_refs(body, config, repo):
    """The tickets this PR would close on merge, as owner/repo#n.

    Only keywords the central file tags `closing` count — ADVANCES is
    non-closing by design, and hardcoding the split here would be the
    second copy of a fact reference-keywords.json already owns. Bare
    `#n` is the merging repo's own ticket, so it normalizes against
    `repo` rather than staying ambiguous.
    """
    closers = sorted(w for w, kind in config["allowed"].items() if kind == "closing")
    refs = set()
    pattern = r"\b(?:" + "|".join(map(re.escape, closers)) + r") (" + REF + r")"
    for match in re.finditer(pattern, body or ""):
        ref = match.group(1)
        refs.add(ref if "/" in ref else f"{repo}{ref}")
    return sorted(refs)


def open_prs_of(events, exclude):
    """Open PRs among a ticket's cross-references, as owner/repo#n.

    The timeline is the forge's own reference index: no text search to
    miss a phrasing, cross-repo for free, and sources the token cannot
    read are simply absent rather than errors. `exclude` drops the PR
    under judgement — it always references its own tickets.
    """
    prs = set()
    for event in events:
        if event.get("event") != "cross-referenced":
            continue
        source = event.get("source", {}).get("issue") or {}
        if "pull_request" not in source or source.get("state") != "open":
            continue
        name = f"{source['repository']['full_name']}#{source['number']}"
        if name != exclude:
            prs.add(name)
    return sorted(prs)


def warn_premature_close(body, config, repo, number, token):
    """#150: closing a ticket other open PRs still reference is loud.

    A warning, never a failure — a shared mention is often legitimate
    (a see-also, a quoted changelog), and forcing ADVANCES onto a
    genuinely final PR would teach people to stop declaring closes.
    Anything unreadable is a notice for the same reason a consumer
    whose workflow lags the script by one release must not go red.
    """
    tickets = closing_refs(body, config, repo)
    if not tickets:
        return
    if not token:
        print("::notice::no GH_TOKEN — cannot check closing targets for other open PRs")
        return
    for ticket in tickets:
        ticket_repo, _, ticket_number = ticket.rpartition("#")
        try:
            events = paginate(
                f"/repos/{ticket_repo}/issues/{ticket_number}/timeline", token
            )
        except (OSError, ValueError) as error:
            print(f"::notice::could not check {ticket} for other open PRs: {error}")
            continue
        others = open_prs_of(events, exclude=f"{repo}#{number}")
        if others:
            print(
                f"::warning::merging closes {ticket}, but other open PRs still "
                f"reference it: {', '.join(others)}. If they share its work, "
                f"this PR should ADVANCES the ticket and the last one close it."
            )


def live_pr(payload, token):
    """The PR as it is NOW, falling back to the event's snapshot.

    The payload is frozen when the run is created, and a re-run replays
    that same payload — so a body corrected after a red run stays
    invisible to every re-run of it, and the gate fails forever for a
    reason that no longer exists (#159). Only the number is taken from
    the event; everything judged is read live.

    A read that fails leaves the payload in place: the gate judges a
    possibly-stale body rather than erroring, which is the same verdict
    it gave before this existed, and never a pass it did not earn.
    """
    if not token:
        return payload
    try:
        fresh = fetch(
            f"/repos/{os.environ['GITHUB_REPOSITORY']}/pulls/{payload['number']}", token
        )
    except OSError as err:
        print(
            f"::notice::could not read the live pull request ({err}) — judging the event payload"
        )
        return payload
    return fresh


def run_ticket():
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    pr = live_pr(event["pull_request"], os.environ.get("GH_TOKEN"))
    config = reference_config()
    problems, escaped = ticket_violations(
        pr.get("body"),
        pr["head"]["ref"],
        [label["name"] for label in pr.get("labels", [])],
        pr["user"]["login"],
        config,
    )
    if escaped:
        print("automated escape: bot-authored PR carries the automated label.")
        return 0
    for problem in problems:
        print(f"::error::{problem}")
    if not problems:
        print("Ticket references are canonical.")
    warn_premature_close(
        pr.get("body"),
        config,
        os.environ["GITHUB_REPOSITORY"],
        pr["number"],
        os.environ.get("GH_TOKEN"),
    )
    return 1 if problems else 0


def reference_config():
    """The central keyword file — required, never defaulted (#144).

    Every rule value is passed explicitly from the one central
    location; a missing file or key fails loudly rather than silently
    reverting to a built-in the file no longer controls. The store
    variants carry the same file for the same reason, byte-pinned.
    """
    with open(os.environ["REFERENCE_KEYWORDS"], encoding="utf-8") as handle:
        return json.load(handle)
