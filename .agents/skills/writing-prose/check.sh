#!/usr/bin/env bash
# writing-prose check. F rules fail the run; H rules print candidates
# for the agent to confirm or dismiss; the run ends with the M rules
# of the surface, which only the agent can judge. The code-checkable
# rules live in patterns.awk; the rules files under rules/ are the
# authority for every rule's wording and tier.
# Usage: check.sh <surface> <file|-> [--before <file>] [--style]
#        check.sh --rules <surface>   rules files the surface reads
#        check.sh --list              F and H rules patterns.awk implements
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
surfaces="chat ticket tracker markdown skill primed comment commit"

usage() {
    echo "usage: check.sh <surface> <file|-> [--before <file>] [--style]" >&2
    echo "       check.sh --rules <surface> | --list" >&2
    echo "surface is one of: $surfaces" >&2
    exit 2
}

valid_surface() { case " $surfaces " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

# Mirrors the opening line of each rules file, which names its
# surfaces; change both together.
rules_for() {
    case $1 in
        chat) set -- shared chat ;;
        ticket | tracker) set -- shared docs tracker ;;
        markdown) set -- shared docs markdown layout ;;
        skill) set -- shared docs markdown layout skill ;;
        primed) set -- shared docs markdown layout primed ;;
        comment) set -- shared docs code layout ;;
        commit) set -- shared docs code ;;
    esac
    for r in "$@"; do echo "$here/rules/$r.md"; done
}

# Tier and id of every f(...)/h(...) call in patterns.awk.
list_rules() {
    grep -oE '(^|[^a-z_])(f|h)(_at)?\([^"]*"[a-z-]+"' "$here/patterns.awk" \
        | sed -E 's/^[^a-z]*(f|h)(_at)?\([^"]*"([a-z-]+)"$/\1 \3/' \
        | sed -e 's/^f /F /' -e 's/^h /H /' | sort -u
}

[ $# -ge 1 ] || usage
case $1 in
    --list) list_rules; exit 0 ;;
    --rules) valid_surface "${2:-}" || usage; rules_for "$2"; exit 0 ;;
esac

[ $# -ge 2 ] || usage
surface=$1 file=$2
shift 2
valid_surface "$surface" || usage

before="" style=0
while [ $# -gt 0 ]; do
    case $1 in
        --before) before=${2:?--before needs a file}; shift 2 ;;
        --style) style=1; shift ;;
        *) usage ;;
    esac
done

name=$file
if [ "$file" = - ]; then
    file=$(mktemp)
    trap 'rm -f "$file"' EXIT
    cat > "$file"
    name=stdin
fi
[ -f "$file" ] || { echo "check.sh: no such file: $file" >&2; exit 2; }

status=0
awk -v surface="$surface" -v name="$name" -v style="$style" \
    -v before="$before" -f "$here/patterns.awk" "$file" || status=$?

echo "Judge by reading, M rules for $surface:"
rules_for "$surface" | while read -r r; do
    # shellcheck disable=SC2016 # backticks are literal Markdown here
    sed -n 's/^- `\([a-z-]*\)` \[M\] \(.*\)/M \1: \2/p' "$r"
done
exit "$status"
