#!/usr/bin/env bash
# The glossary prune, one script for every repo the template stamps
# (AET#67, AET#203, AET#210).
#
# Every stamp re-delivers the shared term set and `disambiguate prune`
# removes what nothing links, so a repo keeps exactly the shared terms
# it references. The post-stamp task, the template-update workflow and
# the drift job all run this same script, and what it removed is
# committed with the update. The template repo runs it too, on every
# commit, with --fail-on-removal: there the glossary is render output
# the self-application test pins and README.md's index keeps reachable,
# so a removal is a defect, not convergence. The script then names the
# terms, restores the tracked ones so a commit hook never leaves the
# tree mutated, and exits 1.
#
# The pin is agentic_disambiguate_version, rendered into
# scripts/ci/disambiguate-version in a stamped repo (#269); the template
# root reads copier.yml's default instead. The answers file is never
# read: the question is `when: false`, so a key left there is stale.
# disambiguate is pre-alpha; an unpinned run would float across
# breaking releases.
set -euo pipefail

fail_on_removal=0
for arg in "$@"; do
    case "$arg" in
        --fail-on-removal) fail_on_removal=1 ;;
        *)
            echo "prune_glossary: unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

cd "$(git rev-parse --show-toplevel)"

pin=""
if [ -f scripts/ci/disambiguate-version ]; then
    pin="$(tr -d '[:space:]' < scripts/ci/disambiguate-version)"
elif [ -f copier.yml ]; then
    pin="$(awk '
        $1 == "agentic_disambiguate_version:" { in_q = 1; next }
        in_q && $1 == "default:" { gsub(/"/, "", $2); print $2; exit }
        in_q && /^[^ #]/ { in_q = 0 }
    ' copier.yml)"
fi
if [ -z "$pin" ]; then
    echo "prune_glossary: no agentic_disambiguate_version pin in scripts/ci/disambiguate-version or copier.yml" >&2
    exit 1
fi

glossary=docs/glossary
if [ ! -d "$glossary" ]; then
    echo "prune_glossary: no $glossary here, nothing to prune"
    exit 0
fi
list_terms() { find "$glossary" -maxdepth 1 -name '*.md' | sort; }

before="$(list_terms)"
uvx "disambiguate==$pin" prune
removed="$(comm -23 <(printf '%s\n' "$before") <(list_terms))"
[ -n "$removed" ] || exit 0

if [ "$fail_on_removal" -eq 0 ]; then
    echo "prune_glossary: removed unlinked term(s):"
    while IFS= read -r file; do echo "  $file"; done <<< "$removed"
    exit 0
fi

{
    echo "GLOSSARY PRUNE REMOVED TERMS FROM THE TEMPLATE ROOT"
    while IFS= read -r file; do
        if git checkout --quiet -- "$file" 2>/dev/null; then
            echo "  $file  (restored)"
        else
            echo "  $file  (untracked: not restorable, re-create it)"
        fi
    done <<< "$removed"
    echo "Nothing reachable from README.md links them. On this root the"
    echo "glossary is render output pinned by tests/test_self_application.py,"
    echo "so a removal is a defect, not convergence: link each term from the"
    echo "Glossary index in README.md (or from the doc that should reach it),"
    echo "or drop it from template/docs/glossary/ and restamp."
} >&2
exit 1
