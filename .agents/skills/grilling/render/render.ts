/**
 * Grilling question renderer CLI.
 *
 * Usage:
 *   node --experimental-strip-types render.ts <session.json> --out <dir>
 *
 * Reads a grilling-session JSON file, validates it against the version-2
 * schema (see decision-context.ts), and writes:
 *   <dir>/session.html — the pre-built template with the JSON injected
 *                         (artifact form; rendering happens client-side)
 *   <dir>/session.md   — the pure-text fallback
 *
 * Exits 0 on success. Exits 1 with a field-naming message on stderr when
 * the input violates the schema or cannot be read.
 *
 * DECISION:IFACE — this CLI is the enforcement point for the question
 * format: the model authors only the JSON; both user-facing forms are
 * derived here, so format drift is impossible rather than discouraged.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { validateGrillingSession } from "./decision-context.ts";
import { buildViewModel } from "./view-model.ts";
import { renderMarkdown } from "./text.ts";

const JSON_PLACEHOLDER = "__DECISION_CONTEXT_JSON__";

/**
 * Entry point.
 *
 * @param argv - Process arguments after the script name:
 *   [contextPath, "--out", outDir].
 * @throws Error on invalid usage or invalid input.
 */
function main(argv: string[]): void {
  const [contextPath, outFlag, outDir] = argv;
  if (!contextPath || outFlag !== "--out" || !outDir) {
    throw new Error(`usage: render.ts <session.json> --out <dir> (got: ${JSON.stringify(argv)})`);
  }
  const session = validateGrillingSession(JSON.parse(readFileSync(contextPath, "utf8")));

  const template = readFileSync(join(import.meta.dirname, "template.html"), "utf8");
  if (!template.includes(JSON_PLACEHOLDER)) {
    throw new Error(`template.html is missing the ${JSON_PLACEHOLDER} placeholder — rebuild via build.ts`);
  }
  // DECISION:SEC — `<` is escaped as its unicode escape sequence inside the injected JSON so
  // no context text can close the data script tag and become markup; the
  // function replacer keeps `$`-sequences in the data from being
  // interpreted as replacement patterns.
  const json = JSON.stringify(session).replace(/</g, "\\u003c");
  writeFileSync(join(outDir, "session.html"), template.replace(JSON_PLACEHOLDER, () => json));

  writeFileSync(join(outDir, "session.md"), renderMarkdown(buildViewModel(session)));
}

try {
  main(process.argv.slice(2));
} catch (e) {
  console.error(String(e instanceof Error ? e.message : e));
  process.exit(1);
}
