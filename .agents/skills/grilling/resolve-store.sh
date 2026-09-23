#!/usr/bin/env bash
# Locate the decision store the harness cloned, and report whether a
# previous session's records are still unmerged.
#
# Resolve, never clone. A session that clones a store of its own splits
# it into a written copy and a read copy; both are healthy git clones,
# so the split is silent and the tooling reads the stale half. Missing
# clone is therefore an error naming the fix, never a fallback that
# recreates the split.
#
# Derivation matches the environment's own store setup: SESSION_ROOT
# from ~/.claude/session.env, then the URL's basename under it.
set -euo pipefail

# Loud failure, the house shape (writing-skills, "Loud failures").
die() {
    local headline="$1"
    shift
    printf '\n⚠️  **GRILLING: %s**  ⚠️\n\n' "$headline" >&2
    printf '    %s\n' "$@" >&2
    printf '\n' >&2
    exit 1
}

store_path() {
    [ -n "${DECISION_MEMORY_URL:-}" ] || die "NO DECISION STORE IS NAMED" \
        "DECISION_MEMORY_URL is unset, so nothing can be recorded this session." \
        "Tell the user out loud: a silent skip is indistinguishable from a successful record."
    if [ -n "${DECISION_MEMORY_ROOT:-}" ]; then
        echo "$DECISION_MEMORY_ROOT"
        return
    fi
    local session_env="$HOME/.claude/session.env" root dir
    # `|| true`: a missing session.env must reach the message below, not
    # kill the script through pipefail with nothing said.
    root=$( (sed -n 's/^SESSION_ROOT=//p' "$session_env" 2>/dev/null || true) | head -1 | tr -d '[:space:]')
    [ -n "$root" ] || die "STORE CLONE CANNOT BE RESOLVED" \
        "No SESSION_ROOT in $session_env." \
        "Ask the user to rerun the environment setup, and record nothing until it resolves."
    dir="$root/$(basename "$DECISION_MEMORY_URL" .git)"
    [ -d "$dir/.git" ] || die "NO HARNESS CLONE OF THE DECISION STORE" \
        "Expected it at $dir." \
        "Ask the user to add the store repo to this environment's session sources" \
        "(name the variable, never its value). This session does NOT clone stores itself:" \
        "a second clone splits the store into a written copy and a read copy, silently."
    echo "$dir"
}

# Decision records that exist on some branch but have not reached the
# default branch. Empty output = the store is settled.
unmerged_records() {
    local dir base ref
    dir=$(store_path)
    base=$(git -C "$dir" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
    git -C "$dir" rev-parse --verify --quiet "$base" >/dev/null || return 0
    for ref in $(git -C "$dir" for-each-ref --format='%(refname)' refs/heads refs/remotes/origin); do
        [ "$ref" = "refs/remotes/$base" ] && continue
        git -C "$dir" diff --name-only --diff-filter=A "$base...$ref" -- decisions/ 2>/dev/null || true
    done | sort -u
}

# The active set as a JSON array, ready to paste into the session's
# `preferences` field. Citations are copied, never retyped: a rule
# rekeyed by hand loses a trailing period and scores nothing.
preferences_json() {
    local dir
    dir=$(store_path)
    [ -f "$dir/preferences.txt" ] || die "NO PREFERENCES.TXT IN THE STORE" \
        "Looked in $dir. There is no active set to cite." \
        "Say so out loud rather than citing rules from memory."
    node -e '
        const fs = require("fs");
        const lines = fs.readFileSync(process.argv[1], "utf8")
            .split("\n").map((l) => l.trim()).filter(Boolean);
        console.log(JSON.stringify(lines, null, 2));
    ' "$dir/preferences.txt"
}

case "${1:-path}" in
    path) store_path ;;
    unmerged) unmerged_records ;;
    preferences) preferences_json ;;
    *) die "UNKNOWN SUBCOMMAND" "usage: resolve-store.sh [path|unmerged|preferences]" ;;
esac
