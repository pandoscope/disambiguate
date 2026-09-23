/**
 * View model — the single presentation authority for a grilling session.
 * Both projections (page.ts → interactive DOM in the artifact, text.ts →
 * markdown fallback) render from this structure, so their content cannot
 * diverge.
 *
 * DECISION:ARCH — presentation content is computed once here rather than
 * separately in the DOM and markdown renderers; the projections only lay
 * out ViewModel fields, they never derive wording from the raw session.
 */

import type { GrillingSession, DecisionQuestion, AnswerState } from "./decision-context.ts";

/**
 * Lexicographic weights for an ordered list of n items: rank i gets
 * 2^-i, normalized to sum 1. The one numeric encoding faithful to the
 * preference set's earlier-rule-wins ordering (S1Q4 ruling): every rank
 * strictly outweighs all lower ranks combined, so no coalition of later
 * rules can outvote an earlier one — which rank-order-centroid allowed
 * (ranks 4-6 beat rank 1 at n=14), silently repealing the convention.
 *
 * @param n - Number of ranked items.
 * @returns Weights indexed by rank-1.
 */
export function lexicographicWeights(n: number): number[] {
  const raw = Array.from({ length: n }, (_, i) => 2 ** -(i + 1));
  const total = raw.reduce((a, b) => a + b, 0);
  return raw.map((w) => w / total);
}

/** Display-ready form of one grilling session. */
export interface SessionViewModel {
  /** Session title, e.g. "Grilling S1". */
  title: string;
  /** Questions in order. */
  questions: QuestionViewModel[];
  /** How to answer, including the correction affordance and shorthand. */
  answerHint: string;
}

/** Display-ready form of one question. */
export interface QuestionViewModel {
  /** Question id, e.g. "S1Q2". */
  id: string;
  /** The question put to the user. */
  question: string;
  /** Session-local facts informing the recommendation, when given. */
  context?: string;
  /** All slots in order, free-text slot included. */
  options: OptionView[];
  /** Near-tie note shown after the options, when the slots are near-tied. */
  nearTieNote?: string;
  /** Lineage display: which preference rules were considered. */
  lineage: LineageView;
  /**
   * Candidate rejection reasons for the checkbox UI: every listed slot's
   * if-clause, labeled by its slot id. Several may apply to one ruling.
   */
  candidateReasons: { slot: string; reason: string }[];
  /** Display of the recorded answer; absent while the question is open. */
  answered?: AnsweredView;
}

/** Display-ready form of one slot. */
export interface OptionView {
  /** 1-based slot number. */
  number: number;
  /** Slot id, e.g. "A1". */
  id: string;
  /** Short name of the option. */
  label: string;
  /**
   * Compact slot tags, at least one per slot: "matches N" (cites N
   * preferences), "my pick", "cold", "wildcard", "alternative",
   * "free text". Excluded combinations are enforced by the schema.
   */
  badges: string[];
  /** Condition under which this option beats the recommendation. */
  ifClause?: string;
  /** What choosing this option entails (may carry `inline code` spans). */
  entails: string;
  /** Footnote markers for matched preferences, shown after the entails. */
  footnotes: { marker: number; anchorId: string }[];
  /**
   * Normalized option score as percent of the question total (rounded),
   * with the per-contribution breakdown; absent when nothing scores.
   */
  score?: {
    pct: number;
    /**
     * One entry per contribution: pct = share of the question total
     * (hover display), ofOptionPct = share of this option's own score
     * (donut segment size), source distinguishes preference segments
     * from the agent-judgment segment.
     */
    breakdown: { label: string; pct: number; ofOptionPct: number; source: "preference" | "agent" }[];
  };
  /** Agent-formulated candidate preferences, listed with the option. */
  proposedPreferences: string[];
  /** Why not recommended, when it differs from the negated if-clause. */
  whyNotRecommended?: string;
  /** True for the renderer-appended free-text slot (gets a text box). */
  freeText?: boolean;
}

/** Display-ready lineage of the recommendation. */
export interface LineageView {
  /** Cold note when no active preference rule applies. */
  coldNote?: string;
  /**
   * Footnote entries for every preference matched by any option of the
   * question: marker number, anchor id, name, 1-based rank in the
   * session's preference order, ROC weight as percent, and the lineage
   * disposition when the rule was explicitly considered.
   */
  footnotes: {
    marker: number;
    anchorId: string;
    name: string;
    rank: number;
    weightPct: number;
    disposition?: string;
    /** Promotion-doc URL, when the session records one for this rule. */
    url?: string;
  }[];
  /** Rules considered but not matched by any option (e.g. set aside). */
  rules: { name: string; disposition: string }[];
}

/** Display of a recorded answer. */
export interface AnsweredView {
  /** Ruling line, e.g. "S1Q1A3: DuckDB, we already embed it elsewhere". */
  line: string;
  /** Confirmed rejection reasons, one line each, prefixed "Rejected:". */
  rejected: string[];
  /** Disconfirmed cited rules, one line each, prefixed "Disconfirmed:". */
  disconfirmed: string[];
}

/**
 * Build the display form of a grilling session.
 *
 * @param session - A validated version-2 grilling session.
 * @returns The view model, with the free-text slot appended to every
 *   question so no renderer (or model) can forget it.
 */
export function buildViewModel(session: GrillingSession): SessionViewModel {
  return {
    title: `Grilling S${session.session}`,
    questions: session.questions.map((q) => buildQuestion(q, session.session, session.preferences ?? [], session.preferenceDocs ?? {})),
    answerHint:
      'Reply in chat with the answer id ("S1Q2A1" or just "1"), or "N, but actually because …" ("N, BAB …") to accept an option while overriding its stated reason. In the artifact page: click your answers, then use "Copy answers as JSON" and paste the result into chat.',
  };
}

/**
 * Build the display form of one question.
 *
 * @param q - The question.
 * @param session - The session number (for the S«s»Q«q» id).
 * @param preferences - The session's ordered preference names.
 * @param preferenceDocs - Promotion-doc URLs per preference name.
 * @returns The question view model.
 */
function buildQuestion(q: DecisionQuestion, session: number, preferences: string[], preferenceDocs: Record<string, string>): QuestionViewModel {
  const id = `S${session}Q${q.seq}`;
  const weights = lexicographicWeights(preferences.length);
  const topWeight = weights[0] ?? 1;

  // Footnotes: one entry per preference matched by any option, ordered by
  // preference rank, anchored so entails prose can reference them.
  const matchedNames = [...new Set(q.options.flatMap((o) => o.matches ?? []))].sort(
    (a, b) => preferences.indexOf(a) - preferences.indexOf(b),
  );
  const footnotes = matchedNames.map((name, i) => {
    const rank = preferences.indexOf(name) + 1;
    return {
      marker: i + 1,
      anchorId: `${id}-pref-${i + 1}`,
      name,
      rank,
      weightPct: Math.round(weights[rank - 1] * 100),
      disposition: q.lineage.rulesConsidered.find((r) => r.name === name)?.disposition,
      url: preferenceDocs[name],
    };
  });

  // Raw score per listed option: matched preference weights plus the
  // agent's own term, capped by the top preference weight so agent
  // judgment can never outvote the user's highest-ranked preference.
  const raw = q.options.map(
    (o) =>
      (o.matches ?? []).reduce((sum, name) => sum + weights[preferences.indexOf(name)], 0) +
      (o.agentScore ?? 0) * topWeight,
  );
  // The residual term: the agent's estimate that none of the listed
  // options fit, scoring the free-text slot in the same pool.
  const noneRaw = (q.noneScore ?? 0) * topWeight;
  const total = raw.reduce((a, b) => a + b, 0) + noneRaw;

  const options: OptionView[] = q.options.map((option, i) => ({
    number: i + 1,
    id: `A${i + 1}`,
    label: option.label,
    badges: badgesFor(option.kind, q.lineage.cold, option.matches?.length ?? 0),
    ifClause: option.ifClause,
    entails: option.entails,
    footnotes: (option.matches ?? [])
      .map((name) => {
        const note = footnotes.find((f) => f.name === name)!;
        return { marker: note.marker, anchorId: note.anchorId };
      })
      .sort((a, b) => a.marker - b.marker),
    score:
      total > 0 && raw[i] > 0
        ? {
            pct: Math.round((raw[i] / total) * 100),
            breakdown: [
              ...(option.matches ?? []).map((name) => ({
                label: name,
                pct: Math.round((weights[preferences.indexOf(name)] / total) * 100),
                ofOptionPct: Math.round((weights[preferences.indexOf(name)] / raw[i]) * 100),
                source: "preference" as const,
              })),
              ...(option.agentScore
                ? [
                    {
                      label: "my judgment",
                      pct: Math.round(((option.agentScore * topWeight) / total) * 100),
                      ofOptionPct: Math.round(((option.agentScore * topWeight) / raw[i]) * 100),
                      source: "agent" as const,
                    },
                  ]
                : []),
            ],
          }
        : undefined,
    proposedPreferences: option.proposedPreferences ?? [],
    whyNotRecommended: option.whyNotRecommended,
  }));
  options.push({
    number: options.length + 1,
    id: `A${options.length + 1}`,
    label: "Something else…",
    badges: ["free text"],
    entails: "custom choice or custom rejection reasoning",
    footnotes: [],
    score:
      noneRaw > 0
        ? {
            pct: Math.round((noneRaw / total) * 100),
            breakdown: [
              { label: "my judgment", pct: Math.round((noneRaw / total) * 100), ofOptionPct: 100, source: "agent" as const },
            ],
          }
        : undefined,
    proposedPreferences: [],
    freeText: true,
  });
  return {
    id,
    question: q.question,
    context: q.context,
    options,
    nearTieNote: q.nearTie
      ? `Near tie: options ${q.nearTie.slots.join("/")} roughly equivalent — differ on ${q.nearTie.differsOn}.`
      : undefined,
    lineage: {
      coldNote: q.lineage.cold ? "Cold: no active preference rule applies." : undefined,
      footnotes,
      rules: q.lineage.rulesConsidered
        .filter((rule) => !matchedNames.includes(rule.name))
        .map((rule) => ({ name: rule.name, disposition: rule.disposition })),
    },
    candidateReasons: q.options.flatMap((option, i) => (option.ifClause ? [{ slot: `A${i + 1}`, reason: option.ifClause }] : [])),
    answered: q.answer ? buildAnswered(q.answer, id, options) : undefined,
  };
}

/**
 * Build the display of a recorded answer.
 *
 * @param answer - The recorded answer state.
 * @param id - The question id, e.g. "S1Q1".
 * @param options - The question's option views, free-text slot included.
 * @returns The answered view.
 */
function buildAnswered(answer: AnswerState, id: string, options: OptionView[]): AnsweredView {
  const disconfirmed = (answer.disconfirmedPreferences ?? []).map((name) => `Disconfirmed: ${name}`);
  if (answer.chosen === undefined) {
    return { line: `${id}: skipped`, rejected: [], disconfirmed };
  }
  const chosen = options[answer.chosen - 1];
  const ruling = chosen.freeText && answer.freeText ? answer.freeText : chosen.label;
  const correction = answer.correction ? ` — but actually because ${answer.correction}` : "";
  return {
    line: `${id}${chosen.id}: ${ruling}${correction}`,
    rejected: (answer.rejectionReasons ?? []).map((reason) => `Rejected: ${reason}`),
    disconfirmed,
  };
}

/**
 * Compact tags for a slot — every slot gets at least one. Combinations
 * that cannot co-occur ("cold" with "matches N", "wildcard" with
 * "matches N" or "my pick") are excluded by the schema, so this mapping
 * never has to resolve a contradiction.
 *
 * @param kind - The slot kind from the decision question.
 * @param cold - Whether the question's recommendation is cold.
 * @param matchCount - Number of preferences the slot matches.
 * @returns The tag texts shown next to the option label.
 */
function badgesFor(kind: DecisionQuestion["options"][number]["kind"], cold: boolean, matchCount: number): string[] {
  const tags: string[] = [];
  if (matchCount > 0) tags.push(`matches ${matchCount}`);
  if (kind === "pick" || kind === "usual-and-pick") tags.push("my pick");
  if (kind === "pick" && cold) tags.push("cold");
  if (kind === "wildcard") tags.push("wildcard");
  if (tags.length === 0) tags.push("alternative");
  return tags;
}
