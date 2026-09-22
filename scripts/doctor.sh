#!/usr/bin/env bash
# Host-tool checks for agentic-engineering repos.
# Default: report only. --install / --fix: bootstrap missing host CLIs (never project deps).
set -euo pipefail

INSTALL=false
if [[ "${1:-}" == "--install" || "${1:-}" == "--fix" ]]; then
    INSTALL=true
fi

# Required host tools for this generated project.
REQUIRED_TOOLS=(git npx uvx gh)
REQUIRED_TOOLS+=(prek)

pass=0
fail=0

check_tool() {
    local tool=$1
    if command -v "$tool" >/dev/null 2>&1; then
        echo "✓ $tool"
        pass=$((pass + 1))
        return 0
    fi
    echo "✗ $tool"
    fail=$((fail + 1))
    return 1
}

warn_tool() {
    local tool=$1
    local message=$2
    if command -v "$tool" >/dev/null 2>&1; then
        echo "✓ $tool"
        pass=$((pass + 1))
    else
        echo "⚠ $tool — $message"
    fi
}

# shellcheck source=scripts/lib/doctor-install.sh disable=SC1091
. "$(dirname "$0")/lib/doctor-install.sh"

echo "agentic doctor — host tool check"
echo

missing=()
for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! check_tool "$tool"; then
        missing+=("$tool")
    fi
done



# prek only bites if its git hook is installed, and hooks do not survive
# git clone. No-op when the repo carries no prek config.
if [[ -f .pre-commit-config.yaml ]] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo
    hook_path="$(git rev-parse --git-path hooks/pre-commit 2>/dev/null || echo .git/hooks/pre-commit)"
    if [[ -f "$hook_path" ]]; then
        echo "✓ prek git hook"
        pass=$((pass + 1))
    elif [[ "$INSTALL" == true ]] && command -v prek >/dev/null 2>&1; then
        if prek install --install-hooks >/dev/null 2>&1; then
            echo "✓ prek git hook (just installed)"
            pass=$((pass + 1))
        else
            echo "✗ prek git hook — 'prek install' failed"
            fail=$((fail + 1))
        fi
    else
        echo "⚠ prek git hook — not installed; lint-dirty commits are not blocked (run scripts/ensure-prek.sh or doctor --install)"
    fi
fi

# Decision-memory contract (grilling skill + the store's recorder): warn when the env var is unset;
# when set, a cheap ls-remote surfaces bad URLs / missing credentials now
# instead of mid-session. No clone here — session-start shallow-clone is the
# recorder's job, per-session and ephemeral by design — and the recorder
# lives in the store, not here.
decision_memory_failed=false
echo
if [[ -z "${DECISION_MEMORY_URL:-}" ]]; then
    echo "⚠ DECISION_MEMORY_URL — unset; grilling skill skips decision recording. Set it (full git URL) in your shell profile (local), the environment config (remote sessions), or a CI secret."
elif GIT_TERMINAL_PROMPT=0 git ls-remote "$DECISION_MEMORY_URL" >/dev/null 2>&1; then
    echo "✓ DECISION_MEMORY_URL (reachable)"
    pass=$((pass + 1))
else
    echo "✗ DECISION_MEMORY_URL — set but not reachable (bad URL or missing credentials): git ls-remote failed"
    fail=$((fail + 1))
    decision_memory_failed=true
fi

echo
echo "Summary: $pass ok, $fail failed"

if [[ ${#missing[@]} -eq 0 ]]; then
    if [[ "$decision_memory_failed" == true ]]; then
        exit 1
    fi
    exit 0
fi

if [[ "$INSTALL" != true ]]; then
    echo
    echo "Re-run with --install to bootstrap missing host tools."
    for tool in "${missing[@]}"; do
        manual_install_hint "$tool"
    done
    exit 1
fi

echo
echo "Installing missing tools..."
install_failed=false
for tool in "${missing[@]}"; do
    if ! install_tool "$tool"; then
        install_failed=true
    fi
done

if [[ "$install_failed" == true ]]; then
    exit 1
fi

echo
echo "Re-checking..."
exec "$0"
