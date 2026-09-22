"""The `approval` subcommand: an allowlisted human's latest review
APPROVES the current head commit — or the PR is authored by one (#187).
"""

import json
import os

from gate_api import paginate
from gate_ticket import live_pr


def latest_reviews(reviews):
    """Each reviewer's latest state-bearing review, in submission order.

    COMMENTED reviews carry no verdict and are skipped; everything else
    (APPROVED, CHANGES_REQUESTED, DISMISSED) overwrites the reviewer's
    earlier entry — GitHub returns reviews chronologically, so the last
    one standing is the reviewer's current word.
    """
    current = {}
    for review in reviews:
        if review.get("state") == "COMMENTED":
            continue
        user = (review.get("user") or {}).get("login")
        if user:
            current[user] = review
    return current


def approval_violations(reviews, approvers, author, labels, head_sha):
    """Why the PR lacks a current human approval, and whether the
    escape held.

    The pass conditions, in order:
    - `automated` label on a bot-authored PR — the same escape as the
      ticket gate, so release and template-update PRs do not wait on a
      human click (#187 records this as a deliberate hole).
    - the PR's AUTHOR is an allowlisted approver — an author cannot
      approve their own PR, and authorship is approval by the same
      party.
    - some approver's latest review is APPROVED on the current head
      commit. An approval on an older commit is stale and named as
      such: whatever was approved is not what would merge.

    A CHANGES_REQUESTED from an approver is named explicitly — it is
    not merely "no approval", it is a standing objection.
    """
    if "automated" in labels and str(author).endswith("[bot]"):
        return [], True
    if author in approvers:
        return [], False

    problems = []
    stale = []
    for user, review in latest_reviews(reviews).items():
        if user not in approvers:
            continue
        state = review.get("state")
        if state == "APPROVED":
            if review.get("commit_id") == head_sha:
                return [], False
            stale.append(
                f"approval by {user} is stale — it approved "
                f"{str(review.get('commit_id'))[:7]}, the head is now "
                f"{str(head_sha)[:7]}; re-approve the current state"
            )
        elif state == "CHANGES_REQUESTED":
            problems.append(
                f"{user} requested changes — address them or have the review dismissed"
            )
    problems.extend(stale)
    if not problems:
        problems.append(
            "no approving review from an allowlisted human "
            f"({'/'.join(sorted(approvers)) or 'none configured'}) — "
            "an approver clicks Approve, or authors the PR"
        )
    return problems, False


def approvers_config():
    """The central approvers file — required, never defaulted (#144).

    An empty list is as loud as a missing file: a gate that waved
    through every PR because nobody was listed would read absence as
    approval.
    """
    with open(os.environ["MERGE_APPROVERS"], encoding="utf-8") as handle:
        approvers = json.load(handle)["approvers"]
    if not approvers or not all(isinstance(a, str) and a for a in approvers):
        raise ValueError(
            f"{os.environ['MERGE_APPROVERS']} lists no approvers — "
            "name at least one human login"
        )
    return approvers


def run_approval():
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    pr = live_pr(event["pull_request"], token)
    reviews = paginate(f"/repos/{repo}/pulls/{pr['number']}/reviews", token)
    problems, escaped = approval_violations(
        reviews,
        approvers_config(),
        pr["user"]["login"],
        [label["name"] for label in pr.get("labels", [])],
        pr["head"]["sha"],
    )
    if escaped:
        print("automated escape: bot-authored PR carries the automated label.")
        return 0
    for problem in problems:
        print(f"::error::{problem}")
    if not problems:
        print("A current human approval covers this head.")
    return 1 if problems else 0
