#!/usr/bin/env python3
"""The uniform CI gate (agentic-engineering-template#137, #143).

One subcommand per job in ci-ok.yml:

  ticket     the PR names its tickets in the canonical ALL-CAPS form
  reviews    every human review thread is answered with a verified
             commit URL or a line starting with the central file's
             `no_commit_marker`, or resolved by the reviewer
  approval   an allowlisted human's latest review APPROVES the current
             head commit — or the PR is authored by one (#187)
  aggregate  every job of every pull_request-triggered workflow on
             this head SHA succeeded — the one required context
  rerun      stale non-green gate runs on this head SHA are re-run in
             place, so a superseded red stops blocking merge (#190) —
             gate-rerun.yml's job, not ci-ok.yml's
  leaks      no PUSH_BLOCKLIST value appears on any surface this PR
  payload    no PUSH_BLOCKLIST value in the one item an issue or
             comment event just published (#208; not a gate)
             publishes: title, body, commit messages, commit author
             and committer names/emails, the branch name, the diff,
             the PR's own comment and review threads, and the bodies
             and comments of every ticket the body references (#189)

One module per subcommand (`gate_ticket.py`, `gate_reviews.py`, ...);
this file is the entry the workflows call and the dispatch table they
reach the subcommands through. Decision logic lives in pure functions
over plain data so the tests exercise it without a network;
`gate_api.py` is the only door to the API. Exit 0 on green, 1 with
each violation named on red.
"""

import sys

from gate_aggregate import run_aggregate
from gate_approval import run_approval
from gate_leaks import run_leaks
from gate_payload import run_payload
from gate_rerun import run_rerun
from gate_reviews import run_reviews
from gate_ticket import run_ticket


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    runners = {
        "ticket": run_ticket,
        "reviews": run_reviews,
        "approval": run_approval,
        "aggregate": run_aggregate,
        "rerun": run_rerun,
        "leaks": run_leaks,
        "payload": run_payload,
    }
    if verb not in runners:
        print(f"usage: check_gate.py {{{'|'.join(runners)}}}", file=sys.stderr)
        return 2
    return runners[verb]()


if __name__ == "__main__":
    sys.exit(main())
