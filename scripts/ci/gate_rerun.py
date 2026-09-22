"""The `rerun` subcommand (gate-rerun.yml, #190): stale non-green gate
runs on this head SHA are re-run in place, so a superseded red stops
blocking merge. Not one of ci-ok.yml's jobs.
"""

import os
import time
import urllib.error

from gate_api import paginate, post


def stale_gate_runs(runs, gate_path):
    """Completed non-green runs of the gate workflow, oldest first.

    A re-judge event spawns a FRESH gate run; the prior red run's check
    runs stay `failure` on the same head SHA, and required-check
    evaluation counts that stale red over the newer green (#190 —
    observed blocking #188's merge). Only re-running the old run in
    place supersedes its verdict. `skipped` already passes evaluation,
    so it is not stale; anything else non-success is.
    """
    return [
        run
        for run in sorted(runs, key=lambda run: run["id"])
        if run["path"] == gate_path
        and run["status"] == "completed"
        and run["conclusion"] not in ("success", "skipped")
    ]


def gate_busy(runs, gate_path):
    """Is any run of the gate workflow still queued or in flight?

    Re-running an old run while a fresh one is in progress queues into
    the same `ci-ok-<pr>` concurrency group and cancel-in-progress
    kills the fresh run — trading one stale red for another. The rerun
    therefore waits for quiet first, which is also why it lives in its
    own workflow with its own group.
    """
    return any(
        run["path"] == gate_path and run["status"] != "completed" for run in runs
    )


def run_rerun():
    """Re-run each stale red gate run once, serially, then stop.

    This job SYNCS old runs with the gate's current verdict; it never
    judges. A rerun re-executes the gate's own jobs, which read live
    data (#159), so a red flips green only when the condition genuinely
    holds now — a still-unmet condition reruns red and keeps blocking,
    which is correct and not this job's failure. Hence exit 0 on every
    orderly path; each run is attempted at most once so a legitimately
    red gate cannot loop.
    """
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["HEAD_SHA"]
    gate_path = os.environ["GATE_WORKFLOW"]
    deadline = time.monotonic() + int(os.environ.get("GATE_RERUN_TIMEOUT", "1500"))

    attempted = set()
    while True:
        runs = paginate(
            f"/repos/{repo}/actions/runs?head_sha={sha}", token, "workflow_runs"
        )
        if not gate_busy(runs, gate_path):
            stale = [
                run
                for run in stale_gate_runs(runs, gate_path)
                if run["id"] not in attempted
            ]
            if not stale:
                done = f"re-ran {sorted(attempted)}" if attempted else "none found"
                print(f"No stale non-green gate runs left on {sha} ({done}).")
                return 0
            run = stale[0]
            attempted.add(run["id"])
            print(f"re-running failed jobs of run {run['id']} ({run['conclusion']})")
            try:
                post(f"/repos/{repo}/actions/runs/{run['id']}/rerun-failed-jobs", token)
            except urllib.error.HTTPError as err:
                # E.g. a cancelled run with nothing rerunnable (409) —
                # note it and move on; syncing must not go red itself.
                print(f"::warning::rerun of {run['id']} refused: {err}")
        if time.monotonic() > deadline:
            print("::warning::gate runs still in flight at the rerun timeout.")
            return 0
        time.sleep(15)
