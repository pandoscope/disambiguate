#!/usr/bin/env bash
# Seed the drift baseline once, for every repo the template stamps
# (AET#267, AET#269).
#
# The disambiguate-drift hook fails on every finding a repo carries the
# day the hook arrives. .drift-baseline.json grandfathers them: a new
# finding fails, a fixed one fails until `--drift --write-baseline`
# shrinks the file and the shrink is committed. This script writes the
# file when it is missing and never touches an existing one, so the
# copier task and the template-update workflow can both run it on
# every stamp without rewriting a repo's list.
#
# The pin comes from scripts/ci/disambiguate-version, the roots from
# the agentic_disambiguate_roots answer, exactly as the prek hook gets
# them. Exit 0 when the file exists afterwards, 1 when disambiguate
# could not write it.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

baseline=.drift-baseline.json
if [ -f "$baseline" ]; then
    echo "drift_baseline: $baseline exists, left alone"
    exit 0
fi

if [ ! -f scripts/ci/disambiguate-version ]; then
    echo "drift_baseline: no pin in scripts/ci/disambiguate-version" >&2
    exit 1
fi
pin="$(tr -d '[:space:]' < scripts/ci/disambiguate-version)"

roots=""
if [ -f .copier-answers.agentic.yml ]; then
    roots="$(awk -F': ' '$1 == "agentic_disambiguate_roots" { sub(/^[^:]*: /, ""); gsub(/^['"'"'"]|['"'"'"]$/, ""); print }' \
        .copier-answers.agentic.yml)"
fi

# shellcheck disable=SC2086 # roots is a space-separated argument list by contract
uvx "disambiguate==$pin" --drift --write-baseline $roots
[ -f "$baseline" ] || { echo "drift_baseline: $baseline was not written" >&2; exit 1; }
echo "drift_baseline: wrote $baseline"
