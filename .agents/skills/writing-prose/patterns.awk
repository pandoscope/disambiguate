# writing-prose rules the code can judge. check.sh runs this file on
# the text under check and states what each tier means. The file
# prints one line per finding:
#   <file>:<line>: <tier> <rule-id>: <message>
# Rule ids match the rules files beside SKILL.md.

function f_at(line, id, msg) { printf "%s:%d: F %s: %s\n", name, line, id, msg; failed = 1 }
function f(id, msg) { f_at(FNR, id, msg) }
function h_at(line, id, msg) { printf "%s:%d: H %s: %s\n", name, line, id, msg }
function h(id, msg) { h_at(FNR, id, msg) }

# True when alternation `words` occurs as a whole word in s.
function has_word(s, words) {
    return s ~ ("(^|[^a-z0-9_'-])(" words ")([^a-z0-9_'-]|$)")
}

function on(surfaces) { return index(" " surfaces " ", " " surface " ") > 0 }

function words(s,    n, w, i, out) {
    n = split(s, w)
    for (i = 1; i <= n; i++) out = out (i > 1 ? " " : "") w[i]
    return out
}

# The text a line contributes to a paragraph.
# On the comment surface, that is the comment without its marker.
# A code line returns "\001" and ends the paragraph like a blank line.
function para_text(line) {
    if (!on("comment")) return line
    if (line !~ /^[ \t]*(#|\/\/|\/\*|\*|--|;)/ || line ~ /^#!/) return "\001"
    sub(/^[ \t]*(#+|\/\/+|\/\*+|\*+|--|;+)[ \t]*/, "", line)
    return line
}

function para_break(t) { return t == "\001" || t ~ /^[ \t]*$/ }

# Reads the --before text: its code blocks in order, and each paragraph
# both as written and as a bare word sequence.
function read_before(    line, fence, code, para, n, t) {
    while ((getline line < before) > 0) {
        if (line ~ /^[ \t]*(```|~~~)/) {
            if (fence) bcode[++nb] = code
            fence = !fence; code = ""
            if (para != "") { bwords[words(para)] = 1; braw[para] = 1; para = "" }
            continue
        }
        if (fence) { code = code line "\n"; continue }
        t = para_text(line)
        if (para_break(t)) {
            if (para != "") { bwords[words(para)] = 1; braw[para] = 1 }
            para = ""
        } else { para = para t "\n"; bline[t] = 1 }
    }
    if (para != "") { bwords[words(para)] = 1; braw[para] = 1 }
    close(before)
}

# A paragraph ended: fails when it holds the same words as a paragraph
# of the old text but breaks its lines differently.
function end_para() {
    if (para == "") return
    if (before != "" && !style && on(LAYOUT) \
        && (words(para) in bwords) && !(para in braw))
        f_at(para_start, "reflow", "untouched words, new line breaks: restore the old lines, or reflow in a style commit")
    para = ""
}

BEGIN {
    if (before != "") read_before()
    DOCS = "ticket tracker markdown skill primed comment commit"
    MD = "markdown skill primed"
    LAYOUT = MD " comment"
    KNOWN = "ADR AGENTS API BATS CLAUDE LICENSE SKILL CI CLI CSS CSV DB DNS HTML HTTP HTTPS ID IDE JSON JWT LLM MCP OK OS PDF PR PRS README SDK SHA SQL SSH TDD TLS TODO TOML TTL UI URL URLS UTC UUID XML YAML"
}

# A line of running prose, as opposed to list, heading, table, quote or HTML.
function prose_line(s) { return s !~ /^[ \t]*$/ && s !~ /^[ \t]*([-*+>|#<]|[0-9]+[.)])/ }

# H rules: patterns that find candidates; the agent confirms or dismisses.
function candidates(    t, tok, lab, plain, rest, n, i, parts, comma) {
    if (low ~ /(^|[^a-z])(might|perhaps|possibly|probably|arguably|somewhat|seems to|appears to|i think|i believe|note that|it's worth noting|importantly|let's|in this section|as mentioned|as noted|first of all|in summary|to summarize|before we|as we'll see|in other words)([^a-z]|$)/)
        h("hedging", "cut the hedge, signpost or meta-comment")
    if (low ~ /not (just|only|merely|simply) [^.]* but /)
        h("not-just", "say what it is, without the escalation")
    if (low ~ /not because [^.]* but because|most people (think|assume|believe)|isn't about [^.]*it's about|widely misunderstood|here's the (thing|kicker)/)
        h("ai-pattern", "state the claim directly")
    n = split(prose, parts, /[^A-Za-z0-9_]+/)
    for (i = 1; i <= n; i++) {
        tok = parts[i]
        sub(/s$/, "", tok)
        if (parts[i - 1] ~ /^[A-Z][A-Z]+$/ || parts[i + 1] ~ /^[A-Z][A-Z]+$/) continue
        if (tok !~ /^[A-Z][A-Z]+$/ || length(tok) > 6 || index(" " KNOWN " ", " " tok " ") || (tok in seen_abbr)) continue
        seen_abbr[tok] = 1
        h("abbreviation", "spell out " tok " unless it is an established term")
    }
    if (on(DOCS)) {
        t = prose; comma = gsub(/,/, ",", t)
        if (comma >= 3 || (comma >= 1 && index(prose, ";")))
            h("one-fact", "one fact per clause: split the sentence")
        if (low ~ /^[ \t>*-]*(the |each |a |an )?(config|configuration|field|file|setting|key|option|value|flag|frontmatter|entry)s? (is|are|holds|contains|defines|sets|says|decides|controls|tells|lists)[ .,]/)
            h("actor-subject", "make the actor the subject")
        if (low ~ /^[ \t>*-]*(the|a|an|this|each|every) ([a-z0-9_-]+ ){0,3}[a-z0-9_-]+, [^.]*, /)
            h("verb-distance", "bring the verb within four words of its subject")
        if (low ~ /(the|a|an|each|every) [a-z]+ (named|called|built|made|written|created|stored|kept|held|found|given|sent|set|run|used|listed|passed) (by|in|from|with|under|on) /)
            h("relative-clause", "use that/which, or a sentence of its own")
        if (low ~ /[a-z]+(tion|m[e]nt|ance|ence|sion)s? of (the|a|an|its|each|every|this) /)
            h("event-noun", "make the event a verb")
        if (!on("commit") && low ~ /no longer|previously|used to|formerly|originally|anymore|(was|were) (changed|renamed|replaced|moved)|now (uses|is|does|takes)|(old|new) (behavior|behaviour)/)
            h("present-tense", "state the present; history goes to commits")
        if (!on("commit") && low ~ /no longer supported|deprecated|(was|were|has been|have been) removed|removed in /)
            h("removed-mention", "erase the removed feature; migration notes go in the BREAKING CHANGE footer")
        if (low ~ /(is|are) (optional|not required|ignored|tolerated|insignificant)|order (does not|doesn't) matter|may be omitted|need not|not necessary/)
            h("non-requirement", "drop the non-requirement unless it simplifies the solution")
        if (has_word(low, "powerful|seamless|seamlessly|robust|elegant|elegantly|effortless|effortlessly|blazing|cutting-edge|best-in-class|delightful|world-class|amazing|awesome|great"))
            h("pitch", "cut the value word")
        if (low ~ /(^|[^a-z])(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[0-9]+) [a-z-]+( [a-z-]+)? (above|below|that follow|following)([^a-z]|$)|see (the )?section|in section [0-9]/)
            h("drifting-ref", "link the target instead of restating its count or position")
    }
    if (on(MD)) {
        if (low ~ /(^|[^a-z])lines? [0-9]|(^|[^a-z])l[0-9]+([^0-9]|$)|[a-z0-9_]\.(md|py|sh|mjs|js|ts|awk|ya?ml|json):[0-9]/)
            h("line-ref", "quote anchor text instead of a line number")
        plain = low
        gsub(/\[[^]]*\]\([^)]*\)/, " ", plain)
        gsub(/\*\*[^*]+\*\*/, " ", plain)
        for (t in marked)
            if (!(t in flagged_term) && has_word(plain, t)) {
                flagged_term[t] = 1
                h("glossary-marking", "mark the term: bold it, or reword to the everyday word")
            }
        rest = prose
        while (match(rest, /\[[^]]+\]\([^)]*\.md[^)]*\)/)) {
            lab = tolower(substr(rest, RSTART + 1, index(substr(rest, RSTART), "]") - 2))
            if (lab ~ /^[a-z0-9 -]+$/) marked[lab] = FNR
            rest = substr(rest, RSTART + RLENGTH)
        }
    }
    if (on(LAYOUT)) {
        t = prose
        gsub(/\[[^]]*\]\([^)]*\)/, "LINK", t)
        gsub(/https?:\/\/[^ )>]*/, "URL", t)
        if (!(raw in bline) && length(t) > 120 && tolower(t) !~ /[,;:]| (and|but|or|so|because|which|that|while|when|if|where|then) /)
            h("long-line", "no clause to break at: split the sentence, or keep it on one line")
        if (!(raw in bline) && prose_line(raw) && raw !~ /^[ \t]*\|/) {
            if (prose ~ /[a-z0-9)][.!?] +[A-Z]/)
                h("sembr", "one sentence per line")
            else if (prev_prose && prev !~ /[.!?:;,)]$/ && raw ~ /^[ \t]*[a-z]/ \
                && raw !~ /^[ \t]*(and|but|or|nor|so|yet|because|since|while|whereas|although|though|unless|until|when|where|which|that|if|then)([^a-z]|$)/)
                h("sembr", "break at a sentence or clause, not mid-clause")
        }
    }
    if (on("ticket tracker") && prose_line(raw) && prev_prose && !wrap_run) {
        h_at(FNR - 1, "hard-wrap", "one paragraph per line; the tracker renders every newline")
        wrap_run = 1
    }
    if (!prose_line(raw) || !prev_prose) wrap_run = 0
    if (on("ticket") && raw ~ /[a-z0-9_.-]+\/[a-z0-9_.\/-]+\.(md|py|mjs|js|ts|sh|json|ya?ml|toml|awk)/)
        h("ticket-code", "no file paths in ticket prose; they go stale")
}

# Angle placeholders outside code in tracker text; HTML tags pass.
function tracker_placeholders(s,    tag) {
    while (match(s, /<[a-z][a-z0-9_-]*>/)) {
        tag = substr(s, RSTART + 1, RLENGTH - 2)
        if (tag !~ /^(a|b|i|u|s|p|br|hr|em|strong|code|pre|sub|sup|kbd|details|summary|ul|ol|li|img|table|tr|td|th|div|span|blockquote|del|ins|mark|small)$/)
            return 1
        s = substr(s, RSTART + RLENGTH)
    }
    return 0
}

# A commit hash standing alone: 7-40 hex digits with a letter and a digit,
# outside markdown links, bare URLs and owner/repo@sha references.
function bare_hash(s,    tok) {
    gsub(/`/, " ", s)
    gsub(/\[[^]]*\]\([^)]*\)/, " ", s)
    gsub(/https?:\/\/[^ )>]*/, " ", s)
    gsub(/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+@[0-9a-f]+/, " ", s)
    while (match(s, /(^|[^0-9A-Za-z_\/])[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]+/)) {
        tok = substr(s, RSTART, RLENGTH)
        sub(/^[^0-9a-f]/, "", tok)
        s = substr(s, RSTART + RLENGTH)
        if (s ~ /^[0-9A-Za-z_]/ || length(tok) > 40) continue
        if (tok ~ /[a-f]/ && tok ~ /[0-9]/) return 1
    }
    return 0
}

FNR == 1 && /^---[ \t]*$/ { in_front = 1; next }
in_front { if (/^---[ \t]*$/) in_front = 0; next }

{
    if (/^[ \t]*(```|~~~)/) {
        if (in_fence) acode[++na] = code
        else code_start[na + 1] = FNR
        in_fence = !in_fence; code = ""
        if (on("ticket") && in_fence) h("ticket-code", "no code in ticket prose, except a prototype snippet that encodes a decision")
        end_para()
        prev_prose = 0
        next
    }
    if (in_fence) { code = code $0 "\n"; next }
    t = para_text($0)
    if (para_break(t)) { prev_prose = 0; end_para() }
    else { if (para == "") para_start = FNR; para = para t "\n" }
    raw = $0
    if (on("comment") && raw ~ /«[^«» ]+»/)
        f("code-placeholder", "code takes <angle> placeholders, never guillemets")
    if (on("comment")) {
        if (raw !~ /^[ \t]*(#|\/\/|\/\*|\*|--|;)/ || raw ~ /^#!/) next
        sub(/^[ \t]*(#+|\/\/+|\/\*+|\*+|--|;+)[ \t]*/, "", raw)
    }
    low_all = low_all tolower(raw) " "
    prose = raw
    gsub(/`[^`]*`/, "", prose)
    # A quoted word is a mention, not a use.
    gsub(/“/, "\"", prose); gsub(/”/, "\"", prose)
    gsub(/"[^"]*"/, "\"\"", prose)
    low = tolower(prose)

    if (has_word(low, "just|really|basically|actually|simply"))
        f("filler", "cut the filler word")
    if (low ~ /(^|[.!?][ \t]+)(sure|certainly|of course|absolutely|great question)([ ,.!]|$)/ \
        || low ~ /(happy|glad) to help|i'd be happy|hope this helps|feel free to/)
        f("pleasantry", "cut the pleasantry")
    if (!on("chat") && raw ~ /[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z-[a-z0-9]/)
        f("store-id", "state the reason in plain words, not a private record id")
    if (on("ticket tracker") && tracker_placeholders(prose))
        f("tracker-placeholder", "tracker text takes guillemet placeholders")
    if (on("ticket tracker") && bare_hash(raw))
        f("commit-link", "link the commit: [short](repo-url/commit/full) or owner/repo@sha")
    candidates()
    prev = raw; prev_prose = prose_line(raw)
}

END {
    end_para()
    if (before == "") {
        print "skipped code-exact: no --before text to compare"
        if (on(LAYOUT)) print "skipped reflow: no --before text to compare"
    }
    else {
        for (i = 1; i <= (na > nb ? na : nb); i++)
            if (acode[i] != bcode[i]) {
                f_at(i in code_start ? code_start[i] : 1, "code-exact", "code blocks come through a rewrite byte-identical")
                break
            }
    }
    if (on("ticket") && low_all !~ /grill/)
        f_at(1, "ungrilled", "state whether the ticket was grilled")
    exit failed
}
