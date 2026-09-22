"""The `aggregate` subcommand: every job of every pull_request-triggered
workflow on this head SHA succeeded — the one required context.
"""

import os
import time

import yaml

from gate_api import paginate


def triggers_of(doc):
    """The `on:` mapping of a parsed workflow. YAML 1.1 reads bare
    `on` as boolean True, so both spellings are looked up."""
    if not isinstance(doc, dict):
        return {}
    on = doc.get("on", doc.get(True, {}))
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return {name: None for name in on}
    return on if isinstance(on, dict) else {}


def expects_pr_run(text):
    """Does this workflow produce a run for every PR head SHA?

    True when it triggers on pull_request with default types or an
    explicit list containing `synchronize` — anything narrower (say
    `[opened]`) has no run for later pushes, so no run can be awaited.
    """
    triggers = triggers_of(yaml.safe_load(text))
    if "pull_request" not in triggers:
        return False
    spec = triggers["pull_request"] or {}
    types = spec.get("types") if isinstance(spec, dict) else None
    return types is None or "synchronize" in types


def aggregate_verdict(expected, runs, jobs_of):
    """(pending, failures) over the expected workflows' newest runs.

    A workflow with no run yet is pending, not failed — the poll loop
    waits it out. A completed job with any conclusion but success is a
    failure: a job that was cancelled or skipped did not pass, and a
    gate that shrugged there would read absence as health.
    """
    pending, failures = [], []
    for path in expected:
        run = runs.get(path)
        if run is None:
            pending.append(f"{path}: no run for this head SHA yet")
            continue
        if run["status"] != "completed":
            pending.append(f"{path}: run {run['id']} is {run['status']}")
            continue
        for job in jobs_of(run["id"]):
            if job["conclusion"] != "success":
                failures.append(
                    f"{path}: job '{job['name']}' concluded {job['conclusion']}"
                )
    return pending, failures


def own_verdict(jobs):
    """(pending, failures) over the gate's own run — judged job by job,
    because this run cannot complete while the gate is still inside it.
    The `ci-ok` job itself is the one exclusion, or it would wait for
    itself forever; its incomplete siblings are pending, not failed,
    since they are in flight exactly while this loop runs.
    """
    pending, failures = [], []
    for job in jobs:
        if job["name"] == "ci-ok":
            continue
        if job["status"] != "completed":
            pending.append(f"own run: job '{job['name']}' is {job['status']}")
        elif job["conclusion"] != "success":
            failures.append(
                f"own run: job '{job['name']}' concluded {job['conclusion']}"
            )
    return pending, failures


def own_workflow_path(workflow_ref, repo):
    """The gate's own workflow file, from GITHUB_WORKFLOW_REF.

    Static, never inferred from the run listing: the gate re-runs on
    review events, and those runs are invisible to a listing filtered
    to `event=pull_request` — the lookup then misses itself and judges
    its own workflow by a sibling run the concurrency group already
    cancelled, failing the head that is in fact green.
    """
    path = workflow_ref.split("@", 1)[0]
    prefix = f"{repo}/"
    return path[len(prefix) :] if path.startswith(prefix) else path


def run_aggregate():
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["HEAD_SHA"]
    own_run = int(os.environ["GITHUB_RUN_ID"])
    own_path = own_workflow_path(os.environ["GITHUB_WORKFLOW_REF"], repo)
    deadline = time.monotonic() + int(os.environ.get("CI_OK_TIMEOUT", "1500"))

    workflows = {}
    root = ".github/workflows"
    for name in sorted(os.listdir(root)):
        if name.endswith((".yml", ".yaml")):
            with open(os.path.join(root, name), encoding="utf-8") as handle:
                workflows[f"{root}/{name}"] = handle.read()
    expected = [path for path, text in workflows.items() if expects_pr_run(text)]
    print("Aggregating:", ", ".join(expected))

    while True:
        listed = paginate(
            f"/repos/{repo}/actions/runs?head_sha={sha}&event=pull_request",
            token,
            "workflow_runs",
        )
        # Newest run per workflow path. The gate's own workflow is
        # judged separately, job by job, since its run cannot complete
        # while this loop is inside it.
        runs = {}
        for run in sorted(listed, key=lambda r: r["id"]):
            runs[run["path"]] = run

        def jobs_of(run_id):
            return paginate(f"/repos/{repo}/actions/runs/{run_id}/jobs", token, "jobs")

        pending, failures = aggregate_verdict(
            [p for p in expected if p != own_path], runs, jobs_of
        )
        own_pending, own_failures = own_verdict(jobs_of(own_run))
        pending.extend(own_pending)
        failures.extend(own_failures)
        if failures:
            for failure in failures:
                print(f"::error::{failure}")
            return 1
        if not pending:
            print("Every job of every PR workflow succeeded.")
            return 0
        if time.monotonic() > deadline:
            for item in pending:
                print(f"::error::still pending at the gate's timeout — {item}")
            return 1
        print("waiting:", "; ".join(pending))
        time.sleep(15)
