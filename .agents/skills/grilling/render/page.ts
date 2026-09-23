/**
 * Client-side renderer of the grilling artifact page. Runs inside the
 * pre-built template: reads the injected grilling-session JSON from the
 * data script tag and builds the interactive DOM from the view model —
 * next/previous navigation across questions, clickable answers whose
 * state persists while navigating, rejection-reason checkboxes, a
 * free-text box, a skip control, and a copy-answers-as-JSON export the
 * user pastes back into chat (and into decision memory).
 *
 * Compiled and inlined into template.html by build.ts — the template is
 * static; data arrives only as JSON, never as concatenated HTML.
 */

import { buildViewModel } from "./view-model.ts";
import type { QuestionViewModel } from "./view-model.ts";
import type { GrillingSession, AnswerState } from "./decision-context.ts";

/**
 * Create an element with a class and optional text.
 *
 * @param tag - Element tag name.
 * @param className - CSS class to set.
 * @param text - Text content (set via textContent; data is never markup).
 * @returns The created element.
 */
function el(tag: string, className: string, text?: string): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/**
 * Build the segmented-donut score marker: one arc segment per
 * contribution, sized by its share of THIS option's score (purple for
 * the user's preferences, the second accent for agent judgment), with
 * the option's share of the question total in the center.
 *
 * @param score - The option's score view (pct + breakdown).
 * @returns An inline SVG element.
 */
function scoreDonut(score: {
  pct: number;
  breakdown: { label: string; pct: number; ofOptionPct: number; source: "preference" | "agent" }[];
}): SVGSVGElement {
  const NS = "http://www.w3.org/2000/svg";
  const size = 34;
  const c = size / 2;
  const r = 14;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
  svg.setAttribute("class", "score-donut");

  const colorFor = (source: "preference" | "agent") =>
    source === "preference" ? "var(--accent)" : "var(--accent2)";
  const shares = score.breakdown.filter((b) => b.ofOptionPct > 0);
  if (shares.length === 1) {
    const ring = document.createElementNS(NS, "circle");
    ring.setAttribute("cx", String(c));
    ring.setAttribute("cy", String(c));
    ring.setAttribute("r", String(r));
    ring.setAttribute("fill", "none");
    ring.setAttribute("stroke", colorFor(shares[0].source));
    ring.setAttribute("stroke-width", "3.5");
    svg.append(ring);
  } else {
    // Segmented ring: proportional arcs with a fixed gap between them.
    const totalShare = shares.reduce((sum, b) => sum + b.ofOptionPct, 0);
    const gap = 0.16;
    const available = 2 * Math.PI - gap * shares.length;
    let angle = -Math.PI / 2;
    for (const share of shares) {
      const sweep = (share.ofOptionPct / totalShare) * available;
      const x0 = c + r * Math.cos(angle);
      const y0 = c + r * Math.sin(angle);
      const x1 = c + r * Math.cos(angle + sweep);
      const y1 = c + r * Math.sin(angle + sweep);
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", `M ${x0} ${y0} A ${r} ${r} 0 ${sweep > Math.PI ? 1 : 0} 1 ${x1} ${y1}`);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", colorFor(share.source));
      path.setAttribute("stroke-width", "3.5");
      svg.append(path);
      angle += sweep + gap;
    }
  }

  const text = document.createElementNS(NS, "text");
  text.setAttribute("x", String(c));
  text.setAttribute("y", String(c));
  text.setAttribute("class", "score-donut-text");
  text.setAttribute("text-anchor", "middle");
  text.setAttribute("dominant-baseline", "central");
  text.textContent = `${score.pct}`;
  svg.append(text);
  return svg;
}

/**
 * Build the corner marker for the free-text slot — a muted ringed "+"
 * occupying the same corner slot a scored option's donut sits in, so the
 * "Something else…" card is not left visually bare.
 *
 * @returns An inline SVG element.
 */
function writeMarker(): SVGSVGElement {
  const NS = "http://www.w3.org/2000/svg";
  const size = 34;
  const c = size / 2;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
  svg.setAttribute("class", "write-marker");
  // Same geometry and stroke weight as the score donut, dotted, in the
  // soft secondary accent; the + uses the donut's own text style so the
  // two corner marks read as one family.
  const ring = document.createElementNS(NS, "circle");
  ring.setAttribute("cx", String(c));
  ring.setAttribute("cy", String(c));
  ring.setAttribute("r", "14");
  ring.setAttribute("fill", "none");
  ring.setAttribute("stroke", "var(--accent-soft)");
  ring.setAttribute("stroke-width", "3.5");
  ring.setAttribute("stroke-dasharray", "1 4");
  ring.setAttribute("stroke-linecap", "round");
  svg.append(ring);
  const plus = document.createElementNS(NS, "text");
  plus.setAttribute("x", String(c));
  plus.setAttribute("y", String(c));
  plus.setAttribute("class", "score-donut-text");
  plus.setAttribute("text-anchor", "middle");
  plus.setAttribute("dominant-baseline", "central");
  plus.textContent = "+";
  svg.append(plus);
  return svg;
}

/**
 * Append text that may carry `backtick` spans, rendering them as <code>.
 *
 * @param parent - Element to append into.
 * @param text - The text, with backticks delimiting verbatim rules.
 */
function appendWithInlineCode(parent: HTMLElement, text: string): void {
  text.split("`").forEach((part, i) => {
    if (i % 2 === 0) {
      parent.append(document.createTextNode(part));
    } else {
      const code = document.createElement("code");
      code.textContent = part;
      parent.append(code);
    }
  });
}

/** The whole interactive page: state, navigation, and rendering. */
class GrillingPage {
  private readonly session: GrillingSession;
  private readonly vm: ReturnType<typeof buildViewModel>;
  /** Answer state per question seq — the single mutable state store. */
  private readonly answers: Map<number, AnswerState>;
  private current = 0;
  private readonly root: HTMLElement;

  /**
   * @param session - The injected grilling session.
   * @param root - Container element to render into.
   */
  constructor(session: GrillingSession, root: HTMLElement) {
    this.session = session;
    this.vm = buildViewModel(session);
    this.root = root;
    this.answers = new Map(session.questions.flatMap((q) => (q.answer ? [[q.seq, { ...q.answer }]] : [])));
    const firstOpen = session.questions.findIndex((q) => !q.answer);
    this.current = firstOpen === -1 ? session.questions.length - 1 : firstOpen;
    this.render();
  }

  /** Answer state of the question at the current index, created lazily. */
  private answerAt(index: number): AnswerState {
    const seq = this.session.questions[index].seq;
    let state = this.answers.get(seq);
    if (!state) {
      state = {};
      this.answers.set(seq, state);
    }
    return state;
  }

  /** Re-render the whole page from state. */
  private render(): void {
    this.root.replaceChildren();
    this.renderHeader();
    this.renderQuestion(this.vm.questions[this.current], this.answerAt(this.current));
    this.renderFooter();
  }

  /** Session title plus previous/next navigation. */
  private renderHeader(): void {
    const header = el("header", "session-header");
    header.append(el("span", "session-title", this.vm.title));

    const nav = el("nav", "question-nav");
    const prev = el("button", "nav-button", "‹ Previous");
    prev.onclick = () => this.goto(this.current - 1);
    if (this.current === 0) prev.setAttribute("disabled", "");
    const next = el("button", "nav-button", "Next ›");
    next.onclick = () => this.goto(this.current + 1);
    if (this.current === this.vm.questions.length - 1) next.setAttribute("disabled", "");
    nav.append(prev, el("span", "nav-position", `${this.current + 1} / ${this.vm.questions.length}`), next);
    header.append(nav);
    this.root.append(header);
  }

  /**
   * Move to another question. State needs no saving here — every control
   * writes into the answers map as it is used.
   */
  private goto(index: number): void {
    this.current = Math.min(Math.max(index, 0), this.vm.questions.length - 1);
    this.render();
  }

  /** One question: options, why-block, skip, near-tie, lineage. */
  private renderQuestion(q: QuestionViewModel, state: AnswerState): void {
    const header = el("div", "question-header");
    header.append(el("span", "question-seq", q.id + (state.skipped ? " — skipped" : "")));
    header.append(el("h1", "question-text", q.question));
    this.root.append(header);

    if (q.context) {
      const context = el("section", "context");
      context.append(el("h2", "section-heading", "Context"));
      context.append(el("p", "context-text", q.context));
      this.root.append(context);
    }

    const list = el("ol", "options");
    for (const option of q.options) {
      const item = el("li", "option" + (state.chosen === option.number ? " selected" : ""));
      item.onclick = () => {
        // Clicking the selected option again unselects it.
        if (state.chosen === option.number) {
          delete state.chosen;
        } else {
          state.chosen = option.number;
          delete state.skipped;
        }
        this.render();
      };
      // Row 1: the slot id and its tags sit together, closest to the eye;
      // the title drops onto its own line underneath.
      const head = el("div", "option-head");
      head.append(el("span", "option-number", option.id));
      if (option.badges.length) {
        const tags = el("div", "option-tags");
        for (const badge of option.badges) tags.append(el("span", "option-badge", badge));
        head.append(tags);
      }
      item.append(head);
      item.append(el("div", "option-label", option.label));
      // Corner marker: the score donut for scored slots, else a "write
      // your own" ring on the free-text slot so it is never left bare.
      if (option.score) {
        const chip = el("span", "option-mark", "");
        // Hover still reveals each contribution as percent of the
        // QUESTION total; the donut segments show each contribution's
        // share of THIS option's score.
        chip.title = option.score.breakdown.map((b) => `${b.label}: ${b.pct}% of total`).join("\n");
        chip.append(scoreDonut(option.score));
        item.append(chip);
      } else if (option.freeText) {
        const chip = el("span", "option-mark", "");
        chip.title = "Write your own answer";
        chip.append(writeMarker());
        item.append(chip);
      }
      if (option.ifClause) item.append(el("p", "option-if", `if ${option.ifClause}`));
      const entails = el("p", "option-entails");
      appendWithInlineCode(entails, option.entails);
      for (const note of option.footnotes) {
        const sup = document.createElement("sup");
        const link = document.createElement("a");
        link.href = `#${note.anchorId}`;
        link.textContent = `[${note.marker}]`;
        link.onclick = (e) => e.stopPropagation();
        sup.append(link);
        entails.append(" ", sup);
      }
      item.append(entails);
      for (const proposed of option.proposedPreferences) {
        item.append(el("p", "option-proposed", `proposed preference: ${proposed}`));
      }
      if (option.whyNotRecommended) {
        item.append(el("p", "option-why-not", `why not recommended: ${option.whyNotRecommended}`));
      }
      if (option.freeText && state.chosen === option.number) {
        const input = document.createElement("textarea");
        input.className = "free-text-input";
        input.placeholder = "Your choice or reasoning …";
        input.value = state.freeText ?? "";
        input.onclick = (e) => e.stopPropagation();
        input.oninput = () => {
          state.freeText = input.value || undefined;
        };
        item.append(input);
      }
      list.append(item);
    }
    this.root.append(list);

    if (state.chosen !== undefined && state.chosen !== 1) this.renderWhyBlock(q, state);

    const controls = el("div", "question-controls");
    const skip = el("button", "skip-button", state.skipped ? "Skipped — undo" : "Skip this question");
    skip.onclick = () => {
      if (state.skipped) {
        delete state.skipped;
        this.render();
      } else {
        state.skipped = true;
        delete state.chosen;
        // Skipping moves straight on to the next question.
        this.goto(this.current + 1);
      }
    };
    controls.append(skip);
    this.root.append(controls);

    if (q.nearTieNote) this.root.append(el("p", "near-tie", q.nearTieNote));

    const lineage = el("section", "lineage");
    lineage.append(el("h2", "section-heading", "Lineage"));
    if (q.lineage.coldNote) lineage.append(el("p", "lineage-cold", q.lineage.coldNote));
    const rules = el("ul", "lineage-rules");
    for (const note of q.lineage.footnotes) {
      const item = el("li", "lineage-rule");
      item.id = note.anchorId;
      item.append(el("span", "lineage-rule-marker", `[${note.marker}] `));
      if (note.url) {
        const link = document.createElement("a");
        link.className = "lineage-rule-name";
        link.href = note.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = note.name;
        item.append(link);
      } else {
        item.append(el("span", "lineage-rule-name", note.name));
      }
      item.append(el("span", "lineage-rule-weight", ` (rank ${note.rank}, weight ${note.weightPct}%)`));
      if (note.disposition) item.append(el("span", "lineage-rule-disposition", ` — ${note.disposition}`));
      item.append(this.disconfirmToggle(note.name, state));
      rules.append(item);
    }
    for (const rule of q.lineage.rules) {
      const item = el("li", "lineage-rule");
      item.append(el("span", "lineage-rule-name", rule.name));
      item.append(el("span", "lineage-rule-disposition", ` — ${rule.disposition}`));
      item.append(this.disconfirmToggle(rule.name, state));
      rules.append(item);
    }
    lineage.append(rules);
    this.root.append(lineage);
  }

  /**
   * "Not relevant here" toggle for a presented rule — records the rule as
   * disconfirmed: it counts as neither a win nor a loss in extraction.
   *
   * @param name - The preference name as presented.
   * @param state - The current question's answer state.
   * @returns The toggle element.
   */
  private disconfirmToggle(name: string, state: AnswerState): HTMLElement {
    const label = el("label", "disconfirm-toggle");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = (state.disconfirmedPreferences ?? []).includes(name);
    box.onchange = () => {
      const names = new Set(state.disconfirmedPreferences ?? []);
      if (box.checked) {
        names.add(name);
      } else {
        names.delete(name);
      }
      state.disconfirmedPreferences = names.size ? [...names] : undefined;
    };
    label.append(box, el("span", "disconfirm-text", "not relevant here"));
    return label;
  }

  /**
   * Rejection-reason checkboxes plus the correction field — shown once
   * the selection diverges from slot 1 (the prediction/recommendation),
   * because that is when rejection reasons carry signal. Several reasons
   * may apply; each checked one is recorded verbatim.
   */
  private renderWhyBlock(q: QuestionViewModel, state: AnswerState): void {
    const block = el("section", "why-block");
    block.append(el("h2", "section-heading", "Why not A1? (check all that apply)"));
    for (const candidate of q.candidateReasons) {
      const label = el("label", "why-reason");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = (state.rejectionReasons ?? []).includes(candidate.reason);
      box.onchange = () => {
        const reasons = new Set(state.rejectionReasons ?? []);
        if (box.checked) {
          reasons.add(candidate.reason);
        } else {
          reasons.delete(candidate.reason);
        }
        state.rejectionReasons = reasons.size ? [...reasons] : undefined;
      };
      label.append(box, el("span", "why-reason-text", `${candidate.slot}: ${candidate.reason}`));
      block.append(label);
    }
    const correction = document.createElement("input");
    correction.type = "text";
    correction.className = "correction-input";
    correction.placeholder = "but actually because … (overrides the stated reason)";
    correction.value = state.correction ?? "";
    correction.oninput = () => {
      state.correction = correction.value || undefined;
    };
    block.append(correction);
    this.root.append(block);
  }

  /** Copy-answers export plus the answer hint. */
  private renderFooter(): void {
    const footer = el("footer", "session-footer");
    const copy = el("button", "copy-button", "Copy answers as JSON");
    const exportBox = document.createElement("textarea");
    exportBox.className = "export-box";
    exportBox.readOnly = true;
    exportBox.hidden = true;
    const note = el("p", "copy-note", "");
    note.hidden = true;
    copy.onclick = () => {
      const json = this.exportJson();
      exportBox.value = json;
      exportBox.hidden = false;
      navigator.clipboard.writeText(json).then(
        () => {
          note.textContent = "Copied — paste into chat (and decision memory).";
          note.hidden = false;
        },
        () => {
          // Clipboard access can be blocked in the sandbox; the failure
          // must be observable, never a silent no-op.
          note.textContent = "Clipboard blocked here — copy from the box below.";
          note.hidden = false;
          exportBox.select();
        },
      );
    };
    footer.append(copy, note, exportBox);
    footer.append(el("p", "answer-hint", this.vm.answerHint));
    this.root.append(footer);
  }

  /**
   * Serialize the answer state for pasting into chat / decision memory.
   *
   * @returns Pretty-printed JSON keyed by question id, e.g.
   *   {"session": 1, "answers": {"S1Q1": {"answer": "A3", ...}}}.
   */
  private exportJson(): string {
    const answers: Record<string, unknown> = {};
    this.session.questions.forEach((q, i) => {
      const state = this.answers.get(q.seq);
      if (!state || (state.chosen === undefined && !state.skipped)) return;
      const id = this.vm.questions[i].id;
      answers[id] = {
        ...(state.chosen !== undefined && { answer: `A${state.chosen}` }),
        ...(state.freeText && { freeText: state.freeText }),
        ...(state.rejectionReasons?.length && { rejectionReasons: state.rejectionReasons }),
        ...(state.correction && { correction: state.correction }),
        ...(state.disconfirmedPreferences?.length && { disconfirmedPreferences: state.disconfirmedPreferences }),
        ...(state.skipped && { skipped: true }),
      };
    });
    return JSON.stringify({ session: this.session.session, answers }, null, 2);
  }
}

const dataTag = document.getElementById("decision-context");
const rootNode = document.getElementById("app");
if (!dataTag || !rootNode) {
  throw new Error(`template is missing required nodes: decision-context=${!!dataTag}, app=${!!rootNode}`);
}
new GrillingPage(JSON.parse(dataTag.textContent ?? "") as GrillingSession, rootNode);
