#!/usr/bin/env bash
# Repo-local SessionStart bootstrap.
#
# Seeded once by the agentic template and never overwritten by
# `copier update`. The stamped .claude/settings.json is template-owned
# and runs this script after its own hooks, so tooling a fresh session
# needs in THIS repo goes here — never into the settings file.
#
# Best-effort and quiet: a failed bootstrap must never block a session.
set -u
