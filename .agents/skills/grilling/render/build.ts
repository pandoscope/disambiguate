/**
 * Template build: compiles the client renderer (page.ts + view-model.ts)
 * with tsc and inlines it into template.src.html, producing template.html.
 *
 * Usage:
 *   node --experimental-strip-types build.ts
 *
 * template.html is committed (artifact pages must be self-contained, so
 * the script has to be inline); this build is its declared, mechanical
 * update path. Run it after changing page.ts, view-model.ts, or
 * template.src.html.
 *
 * DECISION:ARCH — the browser script is "bundled" by compiling with tsc
 * (already in the toolchain, hermetic) and concatenating the two known
 * modules with their import/export statements stripped, instead of adding
 * a bundler dependency fetched over the network. Acceptable because the
 * client graph is fixed at two files; revisit if it grows.
 */

import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const HERE = import.meta.dirname;

/**
 * Compile the client modules and return their concatenated script text.
 *
 * @returns Plain-JS IIFE source for inlining into the template.
 * @throws Error when tsc fails or emits unexpected module syntax.
 */
function compileClientScript(): string {
  const outDir = mkdtempSync(join(tmpdir(), "grilling-template-build-"));
  try {
    execFileSync(
      "tsc",
      [
        join(HERE, "page.ts"),
        "--target", "es2021",
        "--module", "es2015",
        "--lib", "es2021,dom",
        "--rewriteRelativeImportExtensions",
        "--strict",
        "--outDir", outDir,
      ],
      { encoding: "utf8" },
    );
    // Emitted order matters only for declarations page.ts uses at load
    // time; view-model.js must precede page.js in the concatenation.
    const script = ["view-model.js", "page.js"]
      .map((name) => stripModuleSyntax(readFileSync(join(outDir, name), "utf8"), name))
      .join("\n");
    return `(() => {\n"use strict";\n${script}\n})();`;
  } finally {
    rmSync(outDir, { recursive: true, force: true });
  }
}

/**
 * Remove import/export module syntax so compiled modules can be
 * concatenated into one classic inline script.
 *
 * @param source - Compiled JS of one module.
 * @param name - File name, for error messages.
 * @returns The source with import lines dropped and export keywords
 *   removed from declarations.
 * @throws Error when module syntax survives that stripping would corrupt.
 */
function stripModuleSyntax(source: string, name: string): string {
  const stripped = source
    .split("\n")
    .filter((line) => !/^\s*import[ {]/.test(line) && !/^\s*export \{/.test(line))
    .map((line) => line.replace(/^export (?=(const|let|function|class) )/, ""))
    .join("\n");
  if (/^\s*(import|export)\b/m.test(stripped)) {
    throw new Error(`${name}: module syntax survived stripping — adjust stripModuleSyntax:\n${stripped}`);
  }
  return stripped;
}

const src = readFileSync(join(HERE, "template.src.html"), "utf8");
const placeholder = "/*__PAGE_JS__*/";
if (!src.includes(placeholder)) {
  throw new Error(`template.src.html is missing the ${placeholder} placeholder`);
}
const banner = [
  "<!--",
  "  GENERATED FILE - do not edit.",
  "  Source: template.src.html + page.ts + view-model.ts.",
  "  Rebuild: make grilling-template (runs build.ts in this directory).",
  "-->",
  "",
].join("\n");
writeFileSync(join(HERE, "template.html"), banner + src.replace(placeholder, () => compileClientScript()));
console.log("template.html rebuilt");
