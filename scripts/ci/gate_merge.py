"""The `merge` subcommand (bot-merge.yml, agentic-engineering-template#260):
the release bot merges a private repo's PR once every job of every PR
workflow on its head succeeded. Not one of ci-ok.yml's jobs.

Ruled on pandoscope/meta#132. GitHub Free enforces no rulesets on a
private repo. There ci-ok is advisory and the merge button works on
red. Repository permissions still hold, so the plan uses them: no human
holds write to main, and this job, acting as the bot, is the one path
in. The job re-judges live data with the aggregate's own verdict. It
never fabricates green: a PR that the gate rejects stays open.
"""

import base64
import os
import time
import urllib.error

from gate_aggregate import aggregate_verdict, expects_pr_run
from gate_api import fetch, paginate, put_json

SWITCH = "BOT_MERGE_ENABLED"
WORKFLOWS = ".github/workflows"
PERMISSIONS = "contents: write and pull_requests: write"


def eligibility(repo_private, switch):
    """Why the bot does not merge in this repository, or None.

    Two conditions hold the bot back, and each names itself, so a run
    that does nothing says which one held it. First, the repository
    must be private: a public repo keeps its rulesets, and this job
    must never double as a second gate there. Second, the org variable
    BOT_MERGE_ENABLED must be "true": meta's credential sync sets it on
    exactly the private repos that need branch protection, and excludes
    session-memory there by name.
    """
    if str(repo_private).lower() != "true":
        return "repository is public — rulesets gate it, the bot does not merge here"
    if str(switch).lower() != "true":
        return f"{SWITCH} is not 'true' — the bot does not merge in this repository"
    return None


def merge_candidates(pulls, head_sha):
    """The open, non-draft PRs whose head is `head_sha`, oldest first.

    A draft means the author said "not yet", and no green overrides
    that. A PR whose head moved on waits for its next event; this one
    does not judge it.
    """
    return sorted(
        (
            pr
            for pr in pulls
            if pr.get("state") == "open"
            and not pr.get("draft")
            and (pr.get("head") or {}).get("sha") == head_sha
        ),
        key=lambda pr: pr["number"],
    )


def expected_workflows(repo, sha, token):
    """The PR workflows of the head under judgement, read from the head.

    A workflow_run fires on the default branch and checks that branch
    out, so the files on disk are not the head's. From those files the
    bot would await forever a workflow that the head removed, and never
    await one that the head added. The contents API at the head SHA
    serves the head itself.
    """
    expected = []
    for entry in fetch(f"/repos/{repo}/contents/{WORKFLOWS}?ref={sha}", token):
        if not entry["name"].endswith((".yml", ".yaml")):
            continue
        blob = fetch(f"/repos/{repo}/contents/{entry['path']}?ref={sha}", token)
        text = base64.b64decode(blob["content"]).decode("utf-8")
        if expects_pr_run(text):
            expected.append(entry["path"])
    return sorted(expected)


def run_merge():
    """Merge each candidate PR once its head is green. Exit 0 on every
    orderly path: a red head is the gate's verdict, not this job's
    failure, and a still-pending head waits for the next event."""
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["HEAD_SHA"]
    reason = eligibility(os.environ.get("REPO_PRIVATE", ""), os.environ.get(SWITCH, ""))
    if reason:
        print(f"Not merging: {reason}.")
        return 0
    deadline = time.monotonic() + int(os.environ.get("BOT_MERGE_TIMEOUT", "1500"))

    pulls = fetch(f"/repos/{repo}/commits/{sha}/pulls", token)
    candidates = merge_candidates(pulls, sha)
    if not candidates:
        print(f"Not merging: no open non-draft PR has head {sha[:7]}.")
        return 0

    expected = expected_workflows(repo, sha, token)

    def jobs_of(run_id):
        return paginate(f"/repos/{repo}/actions/runs/{run_id}/jobs", token, "jobs")

    while True:
        # List every run at this head, whatever event produced it. The
        # push's run keeps `merge approval` red for good; the approval's
        # own pull_request_review run holds the live verdict. Per
        # workflow, the newest run wins.
        try:
            listed = paginate(
                f"/repos/{repo}/actions/runs?head_sha={sha}", token, "workflow_runs"
            )
            runs = {}
            for run in sorted(listed, key=lambda r: r["id"]):
                runs[run["path"]] = run
            pending, failures = aggregate_verdict(expected, runs, jobs_of)
        except urllib.error.HTTPError as error:
            # Reading runs and jobs needs actions: read on the app token.
            # Without it GitHub answers 403; name the permission (#280).
            if error.code != 403:
                raise
            print(
                "::error::Listing the runs at this head was refused — a missing "
                "permission: the release bot needs actions: read on this "
                f"repository (HTTP {error.code})."
            )
            return 1
        if failures:
            for failure in failures:
                print(f"Not merging: {failure}")
            return 0
        if not pending:
            break
        if time.monotonic() > deadline:
            print("::warning::PR workflows still pending at the bot-merge timeout.")
            return 0
        print("waiting:", "; ".join(pending))
        time.sleep(15)

    for pr in candidates:
        number = pr["number"]
        try:
            status = put_json(
                f"/repos/{repo}/pulls/{number}/merge",
                {"merge_method": "merge", "sha": sha},
                token,
            )
        except urllib.error.HTTPError as error:
            # A refused merge is the bot's own failure, not the gate's
            # verdict: the token lacks a permission, or the PR changed
            # under us. The message names the permission first (#260).
            print(
                f"::error::Merge of #{number} refused — a missing permission: the "
                f"release bot needs {PERMISSIONS} on this repository "
                f"(HTTP {error.code})."
            )
            return 1
        print(f"Merged #{number} at {sha[:7]} (HTTP {status}).")
    return 0
