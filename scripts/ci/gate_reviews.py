"""The `reviews` subcommand: every human review thread is answered with
a verified commit URL or a line starting with the central file's
`no_commit_marker`, or resolved by the reviewer.
"""

import json
import os
import re

from gate_api import SERVER, graphql, paginate
from gate_ticket import reference_config


def thread_of(comments):
    """REST review comments grouped into threads by their root."""
    threads = {}
    for comment in comments:
        root = comment.get("in_reply_to_id") or comment["id"]
        threads.setdefault(root, []).append(comment)
    return list(threads.values())


def review_violations(
    threads, pr_author, pr_shas, base_url, marker, resolved=frozenset()
):
    """The agent's worklist: human threads still needing a response.

    Each violation names its exact thread — opener, path, a quote of
    the comment and its URL — because the reader is the agent deciding
    what to do next, not a human who already knows which comment they
    left.

    Answered: the reply names a commit that is one of this PR's own —
    as a commit URL under `base_url`, the PR's own /commits/<sha> URL,
    or a bare sha of seven or more hex digits; the gate already holds
    the PR's shas, so any spelling it can match is proof enough and
    demanding one spelling only cost a round-trip (#205). A sha not on
    the PR fails whatever wraps it. Or a line starting exactly with the
    central file's `no_commit_marker`. A thread the reviewer RESOLVED is off
    the worklist regardless: resolution is the reviewer's own sign-off
    that nothing more is needed, and demanding a reply on top of it
    gated pandoscope/skills#30 on wording nobody was waiting for
    (agentic-engineering-template#166).
    """
    # Any hex run of 7-40 digits is a candidate; only a prefix of one of
    # the PR's own shas answers, so hex-looking prose cannot pass by
    # accident and a pasted-but-wrong sha still fails.
    sha_re = re.compile(r"\b([0-9a-f]{7,40})\b")
    problems = []
    for comments in threads:
        first = comments[0]
        opener = first["user"]["login"]
        if opener == pr_author or opener.endswith("[bot]"):
            continue
        if first.get("id") in resolved:
            continue
        answered = False
        for reply in comments[1:]:
            if reply["user"]["login"] != pr_author:
                continue
            body = reply.get("body") or ""
            linked = any(
                any(sha.startswith(match.group(1)) for sha in pr_shas)
                for match in sha_re.finditer(body)
            )
            marked = any(line.strip().startswith(marker) for line in body.splitlines())
            if linked or marked:
                answered = True
                break
        if not answered:
            where = first.get("path") or "(general)"
            quote = " ".join((first.get("body") or "").split())
            if len(quote) > 90:
                quote = quote[:87] + "..."
            link = first.get("html_url") or ""
            problems.append(
                f'unanswered review thread by {opener} at {where}: "{quote}"'
                + (f" ({link})" if link else "")
                + " — reply naming a commit on this PR (its URL or sha; a sha"
                " not on the PR fails, and amending the commit invalidates"
                f" the reference), or a '{marker} <why>' line, or the reviewer"
                " resolves the thread"
            )
    return problems


RESOLVED_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { isResolved comments(first: 1) { nodes { databaseId } } }
      }
    }
  }
}
"""


def resolved_roots(nodes):
    """Root-comment ids of resolved threads, from reviewThreads nodes.

    The databaseId is the same id the REST comments endpoint returns,
    which is what lets resolution — GraphQL-only — exempt threads built
    from REST data.
    """
    roots = set()
    for node in nodes:
        if not node.get("isResolved"):
            continue
        for comment in (node.get("comments") or {}).get("nodes") or []:
            if comment.get("databaseId") is not None:
                roots.add(comment["databaseId"])
    return roots


def resolved_thread_roots(repo, number, token):
    """Every resolved thread's root id, paged."""
    owner, name = repo.split("/", 1)
    nodes = []
    cursor = None
    while True:
        data = graphql(
            RESOLVED_QUERY,
            {"owner": owner, "name": name, "number": number, "cursor": cursor},
            token,
        )
        threads = data["repository"]["pullRequest"]["reviewThreads"]
        nodes.extend(threads["nodes"])
        if not threads["pageInfo"]["hasNextPage"]:
            return resolved_roots(nodes)
        cursor = threads["pageInfo"]["endCursor"]


def run_reviews():
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    pr = event["pull_request"]
    number = pr["number"]
    comments = paginate(f"/repos/{repo}/pulls/{number}/comments", token)
    shas = [c["sha"] for c in paginate(f"/repos/{repo}/pulls/{number}/commits", token)]
    marker = reference_config()["no_commit_marker"]
    problems = review_violations(
        thread_of(comments),
        pr["user"]["login"],
        shas,
        SERVER,
        marker,
        resolved=resolved_thread_roots(repo, number, token),
    )
    for problem in problems:
        print(f"::error::{problem}")
    if not problems:
        print("Every human review thread is answered.")
    return 1 if problems else 0
