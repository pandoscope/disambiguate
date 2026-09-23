/**
 * Markdown projection of the grilling session view model — the pure-text
 * fallback used when publishing an artifact is not possible.
 */

import type { SessionViewModel, QuestionViewModel, OptionView } from "./view-model.ts";

/**
 * Render a session view model as markdown.
 *
 * @param vm - The view model of one grilling session.
 * @returns Markdown text ending in a newline.
 */
export function renderMarkdown(vm: SessionViewModel): string {
  const lines: string[] = [`# ${vm.title}`, ""];
  for (const question of vm.questions) lines.push(...questionLines(question));
  lines.push(`*${vm.answerHint}*`, "");
  return lines.join("\n");
}

/**
 * Format one question as markdown lines.
 *
 * @param q - The question view model.
 * @returns Lines for the question section, trailing blank line included.
 */
function questionLines(q: QuestionViewModel): string[] {
  const lines: string[] = [`## ${q.id} — ${q.question}`, ""];
  if (q.context) lines.push(q.context, "");
  for (const option of q.options) lines.push(optionBlock(option));
  if (q.nearTieNote) lines.push("", q.nearTieNote);
  lines.push("", "### Lineage", "");
  if (q.lineage.coldNote) lines.push(q.lineage.coldNote);
  for (const note of q.lineage.footnotes) {
    const disposition = note.disposition ? ` — ${note.disposition}` : "";
    const name = note.url ? `[${note.name}](${note.url})` : note.name;
    lines.push(`- [${note.marker}] ${name} (rank ${note.rank}, weight ${note.weightPct}%)${disposition}`);
  }
  for (const rule of q.lineage.rules) lines.push(`- ${rule.name} — ${rule.disposition}`);
  if (q.answered) {
    lines.push("", `> ${q.answered.line}`);
    for (const rejected of q.answered.rejected) lines.push(`> ${rejected}`);
    for (const disconfirmed of q.answered.disconfirmed) lines.push(`> ${disconfirmed}`);
  }
  lines.push("");
  return lines;
}

/**
 * Format one slot as a scannable list block: a header line carrying
 * id · label, tag chips, and the bold total score, with the if-clause,
 * entails, score breakdown, proposals, and why-not as hard-wrapped
 * continuation lines — one fact per line instead of one run-on
 * paragraph.
 *
 * @param option - The slot to format.
 * @returns One markdown list item with trailing-space line breaks.
 */
function optionBlock(option: OptionView): string {
  const tags = option.badges.length ? ` (${option.badges.map((b) => `\`${b}\``).join(" ")})` : "";
  const score = option.score ? ` — **${option.score.pct}%**` : "";
  const refs = option.footnotes.length ? ` [${option.footnotes.map((f) => f.marker).join("][")}]` : "";
  const parts = [`- **${option.id} · ${option.label}**${tags}${score}`];
  if (option.ifClause) parts.push(`*if ${option.ifClause}*`);
  parts.push(`${option.entails}${refs}`);
  if (option.score) {
    parts.push(`score: ${option.score.breakdown.map((b) => `${b.label} ${b.pct}%`).join(" · ")}`);
  }
  for (const proposed of option.proposedPreferences) parts.push(`proposed preference: ${proposed}`);
  if (option.whyNotRecommended) parts.push(`why not recommended: ${option.whyNotRecommended}`);
  // Two trailing spaces force a hard break; the indent keeps every
  // continuation line inside the list item.
  return parts.join("  \n  ");
}
