/**
 * Grilling session — the JSON contract between the grilling model and the
 * renderers. The model authors ONLY this data; every user-facing form
 * (interactive artifact page, text fallback) is derived from it
 * mechanically, so the question format cannot drift.
 *
 * This module is the single authority for the schema: types define the
 * shape, `validateGrillingSession` enforces it. There is no separate
 * JSON-Schema file to keep in sync.
 *
 * Naming: question `S«session»Q«seq»`, answer `S«session»Q«seq»A«slot»`.
 */

/** One grilling session: every question asked so far, with answer state. */
export interface GrillingSession {
  /** Schema version; this module implements version 2. */
  version: 2;
  /** 1-based grilling session number (the S in S1Q1). */
  session: number;
  /**
   * Questions in the order they were asked, unique `seq` each. Follow-up
   * questions are appended and the session re-rendered with the answer
   * state carried forward.
   */
  questions: DecisionQuestion[];
  /**
   * The active preference set considered this session, in preference-file
   * order — earlier entries rank higher. Ranks turn into scoring weights
   * via rank-order-centroid (see view-model.ts). Required whenever any
   * option matches a preference.
   */
  preferences?: string[];
  /**
   * Promotion docs per preference: maps a preference name (an entry of
   * `preferences`) to the URL of the doc that promoted it (e.g. its
   * proposal file in the decision-memory repo). Not deducible from the
   * preference line itself — looked up when the set is injected and
   * recorded here explicitly. Lineage footnotes link it when present.
   */
  preferenceDocs?: Record<string, string>;
}

/** One decision put to the user, with full provenance and answer state. */
export interface DecisionQuestion {
  /** 1-based question number within the session (the Q in S1Q1). */
  seq: number;
  /** The decision being put to the user, phrased as a question. */
  question: string;
  /**
   * Session-local facts informing the recommendation, written BEFORE the
   * ruling (input side of the replay-ready record).
   */
  context?: string;
  /**
   * Listed options, slot A1..AN in order (1-3 entries). The free-text
   * slot is appended by the renderers automatically and must not be
   * listed.
   */
  options: DecisionOption[];
  /** Near-tie between listed slots (1-based) and what they differ on. */
  nearTie?: NearTie;
  /**
   * The agent's estimate (0..1) that NONE of the listed options is the
   * right answer — the residual "none of the above" mass. Scores the
   * renderer-appended free-text slot through the same normalization,
   * capped by the top preference weight like agentScore.
   */
  noneScore?: number;
  /** Which preference rules were considered — the lineage display. */
  lineage: Lineage;
  /** The user's answer, once given; absent while open. */
  answer?: AnswerState;
}

/** A listed option (slot) of a grilling question. */
export interface DecisionOption {
  /** Short name of the option (the "X"). */
  label: string;
  /**
   * Slot semantics per the grilling skill:
   * "usual" = what the active preference set predicts,
   * "pick" = the agent's independent best,
   * "usual-and-pick" = the merged slot when prediction and recommendation
   * coincide, "wildcard" = exploratory branch, "alternative" = a plain
   * runner-up (e.g. slot 2 when prediction and recommendation merged).
   */
  kind: "usual" | "pick" | "usual-and-pick" | "wildcard" | "alternative";
  /** Condition under which this option beats the recommendation. */
  ifClause?: string;
  /**
   * What choosing this option entails. Matched preferences are appended
   * as footnote refs by the renderer — do not restate them here.
   */
  entails: string;
  /**
   * Names of preferences (entries of session.preferences) this option
   * satisfies — one option may match several. Required non-empty for
   * "usual" and "usual-and-pick" slots. Rendered as footnote refs
   * anchored to the ranked lineage entries, and drives the option's
   * preference score.
   */
  matches?: string[];
  /**
   * The agent's own leaning toward this option, 0..1. Contributes to the
   * score capped by the top preference weight so agent judgment can
   * never outvote the user's highest-ranked preference.
   */
  agentScore?: number;
  /**
   * Preferences the agent formulates as inspiration — candidate rules
   * not (yet) in the preference file, listed separately with the option.
   */
  proposedPreferences?: string[];
  /**
   * Why this option is not recommended — only when the reason differs
   * from the negated if-clause.
   */
  whyNotRecommended?: string;
}

/** Near-tie marker between listed slots. */
export interface NearTie {
  /** 1-based slot numbers that are roughly equivalent (at least two). */
  slots: number[];
  /** What the tied slots differ on. */
  differsOn: string;
}

/** Provenance of the recommendation: preference rules considered. */
export interface Lineage {
  /** True when no active preference rule applies (cold recommendation). */
  cold: boolean;
  /** Active preference rules considered, matching or set aside. */
  rulesConsidered: ConsideredRule[];
}

/** One preference rule weighed while forming the recommendation. */
export interface ConsideredRule {
  /** Rule name as it appears in the active preference set. */
  name: string;
  /** Why the rule matched or was set aside for this decision. */
  disposition: string;
}

/**
 * The user's answer to one question — mirrors the interactive page's
 * exported state so a copied answer JSON can be re-injected verbatim on
 * re-render.
 */
export interface AnswerState {
  /** Chosen slot number, free-text slot included; absent when skipped. */
  chosen?: number;
  /** The free-text ruling, when the free-text slot was chosen. */
  freeText?: string;
  /**
   * Rejection reasons confirmed for the non-chosen options (checkbox
   * selections — several may apply), recorded verbatim.
   */
  rejectionReasons?: string[];
  /**
   * Correction affordance ("N, but actually because …" / "N, BAB …"):
   * the chosen option accepted, its stated if-clause overridden by this
   * text. Highest-signal event type.
   */
  correction?: string;
  /**
   * Cited preferences the decider disconfirms ("that rule isn't relevant
   * here") — recorded distinctly so the extraction tally counts them as
   * neither a win nor a loss (record-level rules_disconfirmed).
   */
  disconfirmedPreferences?: string[];
  /** True when the user skipped the question. */
  skipped?: boolean;
}

/**
 * Validate an untyped value as a version-2 GrillingSession.
 *
 * @param value - Parsed JSON of unknown shape.
 * @returns The same value, typed, when it satisfies the schema.
 * @throws Error naming the offending field and its value on the first
 *   violation found.
 */
export function validateGrillingSession(value: unknown): GrillingSession {
  const session = requireRecord(value, "grilling session");
  requireKnownKeys(session, ["version", "session", "questions", "preferences", "preferenceDocs"], "grilling session");
  if (session.version !== 2) {
    throw new Error(`version must be 2, got: ${JSON.stringify(session.version)}`);
  }
  requirePositiveInteger(session.session, "session");
  if (!Array.isArray(session.questions) || session.questions.length === 0) {
    throw new Error(`questions must be a non-empty array, got: ${JSON.stringify(session.questions)}`);
  }
  let preferences: string[] = [];
  if (session.preferences !== undefined) {
    if (!Array.isArray(session.preferences) || session.preferences.length === 0) {
      throw new Error(`preferences must be a non-empty array when present, got: ${JSON.stringify(session.preferences)}`);
    }
    session.preferences.forEach((name, i) => requireNonEmptyString(name, `preferences[${i}]`));
    preferences = session.preferences as string[];
    requireUnique(preferences, "preferences");
  }
  if (session.preferenceDocs !== undefined) {
    const docs = requireRecord(session.preferenceDocs, "preferenceDocs");
    for (const [name, url] of Object.entries(docs)) {
      if (!preferences.includes(name)) {
        throw new Error(`preferenceDocs names a preference not in session.preferences: ${JSON.stringify(name)}`);
      }
      requireNonEmptyString(url, `preferenceDocs[${JSON.stringify(name)}]`);
    }
  }
  session.questions.forEach((question, i) => {
    const q = validateQuestion(question, `questions[${i}]`, preferences);
    // Contiguity subsumes uniqueness: seqs are exactly 1..N in order, so
    // a re-authored session cannot silently drop or renumber a question.
    if (q.seq !== i + 1) {
      throw new Error(`questions[${i}].seq must be ${i + 1} (seqs are contiguous 1..N in order), got: ${q.seq}`);
    }
  });
  return value as GrillingSession;
}

/**
 * Validate one question.
 *
 * @param value - Untyped question entry.
 * @param path - Field path for error messages, e.g. "questions[0]".
 * @param preferences - The session's ordered preference names.
 * @returns The question, typed.
 * @throws Error naming the offending field and value.
 */
function validateQuestion(value: unknown, path: string, preferences: string[]): DecisionQuestion {
  const q = requireRecord(value, path);
  requireKnownKeys(q, ["seq", "question", "context", "options", "nearTie", "lineage", "answer", "noneScore"], path);
  requirePositiveInteger(q.seq, `${path}.seq`);
  requireNonEmptyString(q.question, `${path}.question`);
  if (q.context !== undefined) requireNonEmptyString(q.context, `${path}.context`);

  if (!Array.isArray(q.options) || q.options.length < 1 || q.options.length > 3) {
    throw new Error(`${path}.options must list 1-3 slots (free text is appended automatically), got: ${JSON.stringify(q.options)}`);
  }
  const options = q.options.map((option, i) => validateOption(option, `${path}.options[${i}]`, preferences));
  requireUnique(options.map((o) => `label ${o.label}`), `${path}.options`);

  if (q.noneScore !== undefined) {
    if (typeof q.noneScore !== "number" || q.noneScore < 0 || q.noneScore > 1) {
      throw new Error(`${path}.noneScore must be a number in 0..1, got: ${JSON.stringify(q.noneScore)}`);
    }
  }
  const lineage = requireRecord(q.lineage, `${path}.lineage`);
  if (typeof lineage.cold !== "boolean") {
    throw new Error(`${path}.lineage.cold must be a boolean, got: ${JSON.stringify(lineage.cold)}`);
  }
  if (!Array.isArray(lineage.rulesConsidered)) {
    throw new Error(`${path}.lineage.rulesConsidered must be an array, got: ${JSON.stringify(lineage.rulesConsidered)}`);
  }
  lineage.rulesConsidered.forEach((rule, i) => {
    const record = requireRecord(rule, `${path}.lineage.rulesConsidered[${i}]`);
    requireKnownKeys(record, ["name", "disposition"], `${path}.lineage.rulesConsidered[${i}]`);
    requireNonEmptyString(record.name, `${path}.lineage.rulesConsidered[${i}].name`);
    requireNonEmptyString(record.disposition, `${path}.lineage.rulesConsidered[${i}].disposition`);
    if (!preferences.includes(record.name as string)) {
      throw new Error(`${path}.lineage.rulesConsidered[${i}] names a rule outside the active preference set: ${JSON.stringify(record.name)}`);
    }
  });
  requireUnique(lineage.rulesConsidered.map((r) => (r as { name: string }).name), `${path}.lineage.rulesConsidered`);

  const usualSlots = options.filter((o) => o.kind === "usual" || o.kind === "usual-and-pick");
  if (lineage.cold && usualSlots.length > 0) {
    throw new Error(`${path}.lineage.cold is true but slot "${usualSlots[0].label}" claims a usual kind — a cold recommendation has no applying rule`);
  }
  const matchingSlots = options.filter((o) => (o.matches ?? []).length > 0);
  if (lineage.cold && matchingSlots.length > 0) {
    throw new Error(`${path}.lineage.cold is true but slot "${matchingSlots[0].label}" carries matches — cold excludes "matches N" on every slot`);
  }
  const matchingWildcard = options.find((o) => o.kind === "wildcard" && (o.matches ?? []).length > 0);
  if (matchingWildcard) {
    throw new Error(`${path} slot "${matchingWildcard.label}" is a wildcard citing matches — wildcard excludes "matches N"`);
  }
  if (usualSlots.length > 1) {
    throw new Error(`${path} carries ${usualSlots.length} prediction-role slots — exactly one option may carry the prediction role`);
  }
  if (usualSlots.length === 1 && options[0].kind !== "usual" && options[0].kind !== "usual-and-pick") {
    throw new Error(`${path} prediction-role slot "${usualSlots[0].label}" must sit in slot 1 — scoring and the why-block key off A1`);
  }
  for (const matched of new Set(options.flatMap((o) => o.matches ?? []))) {
    if (!lineage.rulesConsidered.some((r) => (r as { name: string }).name === matched)) {
      throw new Error(`${path}.lineage.rulesConsidered is missing matched preference ${JSON.stringify(matched)} — every match needs its disposition on record`);
    }
  }

  if (q.nearTie !== undefined) {
    const nearTie = requireRecord(q.nearTie, `${path}.nearTie`);
    requireKnownKeys(nearTie, ["slots", "differsOn"], `${path}.nearTie`);
    if (
      !Array.isArray(nearTie.slots) ||
      nearTie.slots.length < 2 ||
      nearTie.slots.some((s) => typeof s !== "number" || s < 1 || s > options.length) ||
      new Set(nearTie.slots).size !== nearTie.slots.length
    ) {
      throw new Error(`${path}.nearTie.slots must name at least two DISTINCT listed slots (1-${options.length}), got: ${JSON.stringify(nearTie.slots)}`);
    }
    requireNonEmptyString(nearTie.differsOn, `${path}.nearTie.differsOn`);
  }

  if (q.answer !== undefined) validateAnswer(q.answer, options.length, `${path}.answer`, preferences);
  return value as DecisionQuestion;
}

/**
 * Validate one answer state.
 *
 * @param value - Untyped answer entry.
 * @param listedCount - Number of listed options (free-text slot is
 *   listedCount + 1).
 * @param path - Field path for error messages.
 * @param preferences - The session's ordered preference names.
 * @throws Error naming the offending field and value.
 */
function validateAnswer(value: unknown, listedCount: number, path: string, preferences: string[]): void {
  const answer = requireRecord(value, path);
  requireKnownKeys(answer, ["chosen", "freeText", "rejectionReasons", "correction", "skipped", "disconfirmedPreferences"], path);
  const freeTextSlot = listedCount + 1;
  if (answer.chosen !== undefined) {
    if (typeof answer.chosen !== "number" || !Number.isInteger(answer.chosen) || answer.chosen < 1 || answer.chosen > freeTextSlot) {
      throw new Error(`${path}.chosen must be a slot number 1-${freeTextSlot}, got: ${JSON.stringify(answer.chosen)}`);
    }
  }
  if (answer.skipped !== undefined && typeof answer.skipped !== "boolean") {
    throw new Error(`${path}.skipped must be a boolean, got: ${JSON.stringify(answer.skipped)}`);
  }
  if (answer.chosen === undefined && answer.skipped !== true) {
    throw new Error(`${path} must either choose a slot or be skipped, got: ${JSON.stringify(answer)}`);
  }
  if (answer.skipped === true) {
    for (const excluded of ["chosen", "freeText", "rejectionReasons", "correction"]) {
      if (answer[excluded] !== undefined) {
        throw new Error(`${path} is skipped but carries ${excluded} — a skipped answer records no choice`);
      }
    }
  }
  if (answer.chosen === freeTextSlot && answer.freeText === undefined) {
    throw new Error(`${path}.freeText is required when the free-text slot (${freeTextSlot}) is chosen — an empty ruling records nothing`);
  }
  if (answer.chosen !== undefined && answer.chosen !== freeTextSlot && answer.freeText !== undefined) {
    throw new Error(`${path}.freeText belongs only to the free-text slot (${freeTextSlot}), but slot ${answer.chosen} was chosen`);
  }
  if (answer.freeText !== undefined) requireNonEmptyString(answer.freeText, `${path}.freeText`);
  if (answer.correction !== undefined) requireNonEmptyString(answer.correction, `${path}.correction`);
  if (answer.rejectionReasons !== undefined) {
    if (!Array.isArray(answer.rejectionReasons)) {
      throw new Error(`${path}.rejectionReasons must be an array, got: ${JSON.stringify(answer.rejectionReasons)}`);
    }
    answer.rejectionReasons.forEach((reason, i) => requireNonEmptyString(reason, `${path}.rejectionReasons[${i}]`));
  }
  if (answer.disconfirmedPreferences !== undefined) {
    if (!Array.isArray(answer.disconfirmedPreferences)) {
      throw new Error(`${path}.disconfirmedPreferences must be an array, got: ${JSON.stringify(answer.disconfirmedPreferences)}`);
    }
    for (const name of answer.disconfirmedPreferences) {
      if (typeof name !== "string" || !preferences.includes(name)) {
        throw new Error(`${path}.disconfirmedPreferences names a preference not in session.preferences: ${JSON.stringify(name)}`);
      }
    }
  }
}

/**
 * Validate one listed option.
 *
 * @param value - Untyped option entry.
 * @param path - Field path for error messages, e.g. "questions[0].options[0]".
 * @param preferences - The session's ordered preference names.
 * @returns The option, typed.
 * @throws Error naming the offending field and value.
 */
function validateOption(value: unknown, path: string, preferences: string[]): DecisionOption {
  const option = requireRecord(value, path);
  requireKnownKeys(option, ["label", "kind", "ifClause", "entails", "matches", "agentScore", "proposedPreferences", "whyNotRecommended"], path);
  requireNonEmptyString(option.label, `${path}.label`);
  requireNonEmptyString(option.entails, `${path}.entails`);
  if ((option.entails as string).split("`").length % 2 === 0) {
    throw new Error(`${path}.entails has an unbalanced backtick — inline code spans must close`);
  }
  const kinds = ["usual", "pick", "usual-and-pick", "wildcard", "alternative"];
  if (typeof option.kind !== "string" || !kinds.includes(option.kind)) {
    throw new Error(`${path}.kind must be one of ${kinds.join("|")}, got: ${JSON.stringify(option.kind)}`);
  }
  if (option.matches !== undefined) {
    if (!Array.isArray(option.matches) || option.matches.length === 0) {
      throw new Error(`${path}.matches must be a non-empty array when present, got: ${JSON.stringify(option.matches)}`);
    }
    for (const name of option.matches) {
      if (typeof name !== "string" || !preferences.includes(name)) {
        throw new Error(`${path}.matches names a preference not in session.preferences: ${JSON.stringify(name)}`);
      }
    }
  }
  if (option.matches !== undefined) requireUnique(option.matches as string[], `${path}.matches`);
  if ((option.kind === "wildcard" || option.kind === "alternative") && option.ifClause === undefined) {
    throw new Error(`${path}.ifClause is required for a "${option.kind}" slot — the condition under which it beats the recommendation is what makes the rejection recordable`);
  }
  if ((option.kind === "usual" || option.kind === "usual-and-pick") && !option.matches) {
    throw new Error(`${path}.matches must name at least one preference for a "${option.kind}" slot, got: ${JSON.stringify(option.matches)}`);
  }
  if (option.agentScore !== undefined) {
    if (typeof option.agentScore !== "number" || option.agentScore < 0 || option.agentScore > 1) {
      throw new Error(`${path}.agentScore must be a number in 0..1, got: ${JSON.stringify(option.agentScore)}`);
    }
  }
  if (option.proposedPreferences !== undefined) {
    if (!Array.isArray(option.proposedPreferences)) {
      throw new Error(`${path}.proposedPreferences must be an array, got: ${JSON.stringify(option.proposedPreferences)}`);
    }
    option.proposedPreferences.forEach((p, i) => requireNonEmptyString(p, `${path}.proposedPreferences[${i}]`));
  }
  if (option.ifClause !== undefined) requireNonEmptyString(option.ifClause, `${path}.ifClause`);
  if (option.whyNotRecommended !== undefined) requireNonEmptyString(option.whyNotRecommended, `${path}.whyNotRecommended`);
  return value as DecisionOption;
}

/**
 * Reject fields outside a level's declared key set — a typo'd optional
 * field must fail loudly, not silently vanish from the page.
 *
 * @param record - The object to check.
 * @param allowed - Every key this level may carry.
 * @param path - Field path for error messages.
 * @throws Error naming the first unknown key.
 */
function requireKnownKeys(record: Record<string, unknown>, allowed: string[], path: string): void {
  for (const key of Object.keys(record)) {
    if (!allowed.includes(key)) {
      throw new Error(`${path} carries unknown field "${key}" — allowed: ${allowed.join(", ")}`);
    }
  }
}

/**
 * Reject duplicate entries in a list of strings.
 *
 * @param values - The strings to check.
 * @param path - Field path for error messages.
 * @throws Error naming the first duplicate.
 */
function requireUnique(values: string[], path: string): void {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) {
      throw new Error(`${path} carries a duplicate entry: ${JSON.stringify(value)}`);
    }
    seen.add(value);
  }
}

/**
 * Require a value to be a plain object.
 *
 * @param value - The value to check.
 * @param path - Field path for error messages.
 * @returns The value as a string-keyed record.
 * @throws Error naming the field and value otherwise.
 */
function requireRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${path} must be an object, got: ${JSON.stringify(value)}`);
  }
  return value as Record<string, unknown>;
}

/**
 * Require a value to be a positive integer.
 *
 * @param value - The value to check.
 * @param path - Field path for error messages.
 * @throws Error naming the field and value otherwise.
 */
function requirePositiveInteger(value: unknown, path: string): void {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1) {
    throw new Error(`${path} must be a positive integer, got: ${JSON.stringify(value)}`);
  }
}

/**
 * Require a value to be a non-empty string.
 *
 * @param value - The value to check.
 * @param path - Field path for error messages.
 * @throws Error naming the field and value otherwise.
 */
function requireNonEmptyString(value: unknown, path: string): void {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${path} must be a non-empty string, got: ${JSON.stringify(value)}`);
  }
}
